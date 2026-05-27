from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import average_precision_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

from ai_tamperguard_v1.research.artifacts import assert_artifact_scores_match, export_linear_artifact
from ai_tamperguard_v1.research.feature_policy import FORBIDDEN_MODEL_FEATURES, resolve_feature_policy
from ai_tamperguard_v1.research.leakage_probes import negative_control_ap_drop, single_feature_auc_probe
from ai_tamperguard_v1.research.recipes import Recipe, candidate_scores, default_recipes
from ai_tamperguard_v1.research.report import render_markdown_report
from ai_tamperguard_v1.research.splits import assign_or_validate_splits
from ai_tamperguard_v1.safety import scan_paths

REQUIRED_COLUMNS = {
    "window_id",
    "scenario_run_id",
    "actor_id",
    "label_binary",
    "label_family",
    "label_source",
    "split_id",
    "reset_id",
    "window_type",
    "source_batch_id",
}


class BakeoffError(ValueError):
    """Raised when the external bakeoff cannot run safely."""


@dataclass(frozen=True)
class BakeoffResult:
    payload: dict[str, Any]
    output_dir: Path

    @property
    def selected_candidate(self) -> str | None:
        return self.payload.get("selected_candidate")


def run_external_bakeoff(
    *,
    features_path: str | Path,
    feature_policy_path: str | Path,
    output_dir: str | Path,
    split_strategy: str = "deterministic_hash",
    seed: int = 260527,
    allow_small_fixture: bool = False,
    leakage_probe_max_auc: float = 0.85,
    require_negative_control_drop: float = 0.15,
    min_delta_average_precision: float = 0.02,
    max_direct_spl_features: int = 80,
) -> BakeoffResult:
    features_path = Path(features_path)
    output_dir = Path(output_dir)
    frame = pd.read_csv(features_path)
    if frame.empty:
        raise BakeoffError("input CSV is empty")
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise BakeoffError(f"input CSV missing required columns: {missing}")
    labels = pd.to_numeric(frame["label_binary"], errors="raise").astype(int)
    if not set(labels).issubset({0, 1}):
        raise BakeoffError("label_binary must contain only 0/1 values")
    frame["label_binary"] = labels

    policy = resolve_feature_policy(feature_policy_path, csv_columns=frame.columns)
    _validate_selected_features(frame, policy.feature_order)
    split = assign_or_validate_splits(frame, strategy=split_strategy, seed=seed, allow_small_fixture=allow_small_fixture)
    frame = split.frame

    train_mask = frame["split_id"] == "train"
    validation_mask = frame["split_id"] == "validation"
    test_mask = frame["split_id"] == "test"
    leakage = single_feature_auc_probe(
        frame,
        feature_order=policy.feature_order,
        train_mask=train_mask,
        max_auc=leakage_probe_max_auc,
        overrides=policy.leakage_probe_overrides,
    )
    leakage["cross_split_correlation_probe_passed"] = _cross_split_probe(frame, policy.feature_order)
    leakage["verdict"] = "leakage_suspect" if leakage["single_feature_auc_failures"] else "honest"

    x_train = frame.loc[train_mask, policy.feature_order].astype(float)
    y_train = frame.loc[train_mask, "label_binary"].astype(int)
    x_val = frame.loc[validation_mask, policy.feature_order].astype(float)
    y_val = frame.loc[validation_mask, "label_binary"].astype(int)
    x_test = frame.loc[test_mask, policy.feature_order].astype(float)
    y_test = frame.loc[test_mask, "label_binary"].astype(int)

    candidates: list[dict[str, Any]] = []
    selected_artifact: dict[str, Any] | None = None
    for recipe in default_recipes():
        candidate = _run_candidate(
            recipe,
            x_train,
            y_train,
            x_val,
            y_val,
            x_test,
            y_test,
            seed=seed,
            leakage=leakage,
            require_negative_control_drop=require_negative_control_drop,
            policy=policy.to_dict(),
            features_path=features_path,
            max_direct_spl_features=max_direct_spl_features,
        )
        candidates.append(candidate)

    baseline = next(candidate for candidate in candidates if candidate["name"] == "logistic_regression/default_balanced")
    eligible = [c for c in candidates if c["status"] == "passed" and c.get("leakage_verdict") == "honest"]
    selected = _select_candidate(eligible, baseline, min_delta_average_precision=min_delta_average_precision)
    if selected and selected["artifact"]:
        selected_artifact = selected["artifact"]
        del selected["artifact"]
    for candidate in candidates:
        candidate.pop("artifact", None)

    if candidates:
        best = max(candidates, key=lambda c: c.get("score", -1.0))
        leakage.update(best.get("negative_control", {}))
        if leakage.get("negative_control_validation_ap_drop") is not None and leakage["negative_control_validation_ap_drop"] < require_negative_control_drop:
            leakage["verdict"] = "leakage_suspect"

    payload: dict[str, Any] = {
        "dataset": {
            "source_csv": _safe_rel(features_path),
            "source_csv_sha256": _sha256(features_path),
            "source_batch_ids": sorted(map(str, frame["source_batch_id"].dropna().unique().tolist())),
            "rows": int(len(frame)),
            "label_distribution": {str(k): int(v) for k, v in frame["label_binary"].value_counts().sort_index().items()},
            "split_strategy": split.strategy,
            "split_distribution": split.distribution,
            "smoke_test_sized_fixture": bool(allow_small_fixture or len(frame) < 100),
        },
        "feature_policy": policy.to_dict(),
        "gate_summary": [
            {"gate": "required_columns", "status": "passed", "notes": f"{len(REQUIRED_COLUMNS)} required columns present"},
            {"gate": "feature_policy", "status": "passed", "notes": "explicit allowlist resolved"},
            {"gate": "splits", "status": "passed", "notes": f"{split.strategy} by {split.group_key}"},
            {"gate": "leakage_probes", "status": "passed" if leakage["verdict"] == "honest" else "warning", "notes": leakage["verdict"]},
        ],
        "leakage_probes": leakage,
        "candidates": candidates,
        "selected_candidate": selected["name"] if selected else None,
        "decision": _decision_text(selected, baseline, leakage),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "bakeoff-results.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "bakeoff-report.md").write_text(render_markdown_report(payload), encoding="utf-8")
    _write_candidate_csv(output_dir / "candidate-summary.csv", candidates)
    if selected_artifact:
        (output_dir / "selected-model-artifact.json").write_text(
            json.dumps(selected_artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    findings = scan_paths([str(output_dir)])
    if findings:
        raise BakeoffError("public safety scan failed for generated bakeoff outputs: " + "; ".join(f"{f.path}: {f.reason}" for f in findings))
    return BakeoffResult(payload=payload, output_dir=output_dir)


def _run_candidate(
    recipe: Recipe,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_val: pd.DataFrame,
    y_val: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    *,
    seed: int,
    leakage: dict[str, Any],
    require_negative_control_drop: float,
    policy: dict[str, Any],
    features_path: Path,
    max_direct_spl_features: int,
) -> dict[str, Any]:
    notes: list[str] = []
    estimator = recipe.make_estimator(seed)
    candidate: dict[str, Any] = {
        "name": recipe.name,
        "technique": recipe.technique,
        "profile": recipe.profile,
        "deployability_class": recipe.deployability_class,
        "leakage_verdict": leakage["verdict"],
        "notes": notes,
    }
    try:
        estimator.fit(x_train, y_train)
        val_scores, val_probs = candidate_scores(estimator, x_val)
        val_pred = estimator.predict(x_val)
        if len(set(val_pred.tolist())) <= 1:
            notes.append("constant predictor on validation")
            candidate["status"] = "failed"
        else:
            candidate["status"] = "passed" if leakage["verdict"] == "honest" else "leakage_suspect"
            if candidate["status"] == "leakage_suspect":
                notes.append("leakage probe verdict blocks promotion")
        metrics = {
            "train": _metrics(y_train, *candidate_scores(estimator, x_train), estimator.predict(x_train)),
            "validation": _metrics(y_val, val_scores, val_probs, val_pred),
            "test": _metrics(y_test, *candidate_scores(estimator, x_test), estimator.predict(x_test)) if len(y_test) else {},
        }
        candidate["metrics"] = metrics
        neg = negative_control_ap_drop(
            lambda: recipe.make_estimator(seed + 1),
            x_train,
            y_train,
            x_val,
            y_val,
            real_validation_ap=metrics["validation"].get("average_precision"),
            seed=seed,
        )
        candidate["negative_control"] = neg
        if neg.get("negative_control_validation_ap_drop") is not None and neg["negative_control_validation_ap_drop"] < require_negative_control_drop:
            candidate["status"] = "leakage_suspect"
            candidate["leakage_verdict"] = "leakage_suspect"
            notes.append("negative control AP drop below required threshold")
        candidate["score"] = _candidate_score(candidate, recipe)
        if recipe.technique == "logistic_regression" and len(x_train.columns) <= max_direct_spl_features:
            artifact = export_linear_artifact(
                technique=recipe.technique,
                profile=recipe.profile,
                feature_order=list(x_train.columns),
                intercept=float(estimator.intercept_[0]),
                coefficients=[float(v) for v in estimator.coef_[0].tolist()],
                threshold=0.5,
                metadata={
                    "source_csv_sha256": _sha256(features_path),
                    "random_seed": seed,
                    "training_git_sha": _git_sha(),
                    "train_row_count": int(len(x_train)),
                    "validation_row_count": int(len(x_val)),
                    "test_row_count": int(len(x_test)),
                },
                feature_policy=policy,
                leakage_probes=leakage,
                metrics=metrics,
            )
            assert_artifact_scores_match(artifact, x_val, estimator.predict_proba(x_val)[:, 1])
            candidate["artifact"] = artifact
            notes.append("exported linear artifact matched estimator probabilities locally")
        return candidate
    except Exception as exc:  # noqa: BLE001 - candidate failures should be reported, not crash whole bakeoff.
        candidate["status"] = "failed"
        candidate["metrics"] = {}
        candidate["score"] = -1.0
        notes.append(f"candidate failed: {exc.__class__.__name__}: {exc}")
        return candidate


def _metrics(y_true: pd.Series, scores, probabilities, predictions) -> dict[str, Any]:
    y = y_true.astype(int).to_numpy()
    pred = pd.Series(predictions).astype(int).to_numpy()
    score_values = probabilities if probabilities is not None else scores
    out = {
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "unique_score_count": int(len(set(map(float, score_values)))),
    }
    if len(set(y.tolist())) > 1:
        out["average_precision"] = float(average_precision_score(y, score_values))
        out["roc_auc"] = float(roc_auc_score(y, score_values))
    else:
        out["average_precision"] = None
        out["roc_auc"] = None
    if probabilities is not None:
        out["probability_std"] = float(pd.Series(probabilities).std(ddof=0))
    return out


def _candidate_score(candidate: dict[str, Any], recipe: Recipe) -> float:
    val = candidate.get("metrics", {}).get("validation", {})
    ap = val.get("average_precision") or 0.0
    ba = val.get("balanced_accuracy") or 0.0
    deploy = {"direct_spl": 1.0, "linear_local_only": 0.7, "generated_spl_planned": 0.5, "offline_only": 0.3}.get(recipe.deployability_class, 0.0)
    return float(0.45 * ap + 0.25 * ba + 0.10 * deploy + 0.05 * recipe.simplicity_score)


def _select_candidate(candidates: list[dict[str, Any]], baseline: dict[str, Any], *, min_delta_average_precision: float) -> dict[str, Any] | None:
    if not candidates:
        return None
    base_ap = baseline.get("metrics", {}).get("validation", {}).get("average_precision") or 0.0
    best = max(candidates, key=lambda c: c.get("score", -1.0))
    best_ap = best.get("metrics", {}).get("validation", {}).get("average_precision") or 0.0
    if best["name"] == baseline["name"] or best_ap >= base_ap + min_delta_average_precision:
        return best
    return baseline if baseline.get("status") == "passed" else None


def _decision_text(selected: dict[str, Any] | None, baseline: dict[str, Any], leakage: dict[str, Any]) -> str:
    if leakage.get("verdict") != "honest":
        return "No candidate is promoted because leakage probes were suspect; metrics are diagnostics only."
    if not selected:
        return "No candidate passed gates; baseline not replaced."
    if selected["name"] == baseline["name"]:
        return "Baseline logistic regression stayed selected because no simpler eligible candidate justified replacement."
    return f"{selected['name']} selected after passing gates and improving enough over the baseline."


def _validate_selected_features(frame: pd.DataFrame, feature_order: list[str]) -> None:
    if set(feature_order) & FORBIDDEN_MODEL_FEATURES:
        raise BakeoffError("forbidden metadata columns were selected as features")
    for feature in feature_order:
        frame[feature] = pd.to_numeric(frame[feature], errors="raise").fillna(0.0)
        if frame[feature].astype(str).str.contains(r"/home/|https?://|password|secret|token", case=False, regex=True).any():
            raise BakeoffError(f"selected feature contains private/string marker: {feature}")


def _cross_split_probe(frame: pd.DataFrame, feature_order: list[str]) -> bool:
    groups_by_split = [set(frame.loc[frame["split_id"] == split, "scenario_run_id"].astype(str)) for split in ("train", "validation", "test")]
    return not (groups_by_split[0] & groups_by_split[1] or groups_by_split[0] & groups_by_split[2] or groups_by_split[1] & groups_by_split[2])


def _write_candidate_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    fields = ["name", "technique", "profile", "status", "deployability_class", "leakage_verdict", "score"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow({field: candidate.get(field) for field in fields})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[4], text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _safe_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name
