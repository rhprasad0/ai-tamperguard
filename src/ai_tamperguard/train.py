from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression

from ai_tamperguard.features import FEATURE_COLUMNS
from ai_tamperguard.labels import LABEL_RULE_DESCRIPTION, LABEL_RULE_ID
from ai_tamperguard.schema import validate_holdout_fixture, validate_model_artifact

PRIVATE_ARTIFACT_DEFAULT = "models/private/tamperguard_v0_model.json"
PRIVATE_EXPECTED_HOLDOUT_DEFAULT = "data/private/holdout/tamperguard_windows_holdout_proxy_expected.csv"
PRIVATE_REPORT_DEFAULT = "reports/private/v0-smoke-test-report.md"
DEFAULT_THRESHOLD = 0.5
NONZERO_COEFFICIENT_EPSILON = 1e-6


class TrainingError(ValueError):
    """Raised when v0 training inputs violate the smoke-test contract."""


@dataclass(frozen=True)
class TrainingResult:
    artifact: dict[str, Any]
    expected_holdout_rows: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def train_logistic_regression(
    train_rows: Iterable[Mapping[str, Any]],
    holdout_rows: Iterable[Mapping[str, Any]],
    *,
    feature_order: Sequence[str],
    seed: int,
    training_git_sha: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> TrainingResult:
    """Train the v0 local logistic-regression model and score the holdout rows locally."""
    feature_order = list(feature_order)
    if not feature_order or any(not feature.startswith("feature_") for feature in feature_order):
        raise TrainingError("feature_order must contain explicit feature_* columns")
    if not 0 <= threshold <= 1:
        raise TrainingError("threshold must be between 0 and 1")

    train_frame = _rows_to_frame(train_rows, feature_order=feature_order, require_label=True, role="train")
    holdout_frame = _rows_to_frame(holdout_rows, feature_order=feature_order, require_label=True, role="holdout")
    _assert_disjoint_window_ids(train_frame, holdout_frame)
    _assert_both_classes(train_frame, role="train")
    _assert_both_classes(holdout_frame, role="holdout")

    model = LogisticRegression(random_state=seed, solver="liblinear", max_iter=1000)
    x_train = train_frame[feature_order].astype(float)
    y_train = train_frame["label_binary"].astype(int)
    model.fit(x_train, y_train)

    intercept = float(model.intercept_[0])
    coefficients = [float(value) for value in model.coef_[0].tolist()]
    scores, probabilities, predictions = _score_rows(
        holdout_frame[feature_order].astype(float).to_numpy(),
        intercept=intercept,
        coefficients=coefficients,
        threshold=threshold,
    )

    expected_holdout_frame = holdout_frame.copy()
    expected_holdout_frame["score_local"] = scores
    expected_holdout_frame["probability_local"] = probabilities
    expected_holdout_frame["prediction_local"] = predictions

    data_fingerprint = _data_fingerprint(train_frame, holdout_frame, feature_order=feature_order)
    model_version = _model_version(
        data_fingerprint=data_fingerprint,
        label_rule_id=LABEL_RULE_ID,
        feature_order=feature_order,
        seed=seed,
        training_git_sha=training_git_sha,
    )
    diagnostics = _diagnostics(
        coefficients=coefficients,
        probabilities=probabilities,
        predictions=predictions,
        true_labels=holdout_frame["label_binary"].astype(int).tolist(),
        train_frame=train_frame,
        holdout_frame=holdout_frame,
    )
    artifact: dict[str, Any] = {
        "schema_version": "model_artifact_v0",
        "model_type": "logistic_regression_sklearn",
        "model_version": model_version,
        "feature_order": feature_order,
        "intercept": intercept,
        "coefficients": coefficients,
        "threshold": float(threshold),
        "label_rule_id": LABEL_RULE_ID,
        "label_rule_description": LABEL_RULE_DESCRIPTION,
        "training_metadata": {
            "python_version": platform.python_version(),
            "sklearn_version": sklearn.__version__,
            "random_seed": int(seed),
            "training_git_sha": training_git_sha,
            "data_fingerprint_sha256": data_fingerprint,
            "label_rule_fingerprint_sha256": _label_rule_fingerprint(),
            "train_row_count": int(len(train_frame)),
            "holdout_row_count": int(len(holdout_frame)),
        },
        "score_envelope": {
            "score_field": "score_local",
            "probability_field": "probability_local",
            "prediction_field": "prediction_local",
        },
        "diagnostics": diagnostics,
    }
    validate_model_artifact(artifact)
    expected_rows = expected_holdout_frame.to_dict(orient="records")
    validate_holdout_fixture(expected_rows, artifact, public=False)
    return TrainingResult(artifact=artifact, expected_holdout_rows=expected_rows, diagnostics=diagnostics)


def write_training_outputs(
    *,
    train_path: Path,
    holdout_path: Path,
    artifact_path: Path = Path(PRIVATE_ARTIFACT_DEFAULT),
    expected_holdout_path: Path = Path(PRIVATE_EXPECTED_HOLDOUT_DEFAULT),
    report_path: Path = Path(PRIVATE_REPORT_DEFAULT),
    seed: int,
    training_git_sha: str | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> TrainingResult:
    """Read private train/holdout CSVs, then write private artifact, expected holdout, and report."""
    train_path = Path(train_path)
    holdout_path = Path(holdout_path)
    artifact_path = Path(artifact_path)
    expected_holdout_path = Path(expected_holdout_path)
    report_path = Path(report_path)

    train_frame = pd.read_csv(train_path)
    holdout_frame = pd.read_csv(holdout_path)
    feature_order = list(FEATURE_COLUMNS)
    _assert_canonical_feature_manifest(train_frame.columns, feature_order, role="train")
    _assert_canonical_feature_manifest(holdout_frame.columns, feature_order, role="holdout")
    result = train_logistic_regression(
        train_frame.to_dict(orient="records"),
        holdout_frame.to_dict(orient="records"),
        feature_order=feature_order,
        seed=seed,
        training_git_sha=training_git_sha or current_git_sha(),
        threshold=threshold,
    )

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    expected_holdout_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(result.artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(result.expected_holdout_rows).to_csv(expected_holdout_path, index=False)
    report_path.write_text(generate_diagnostics_report(result), encoding="utf-8")
    return result


def generate_diagnostics_report(result: TrainingResult) -> str:
    """Render the private v0 diagnostics report without raw private evidence."""
    artifact = result.artifact
    metadata = artifact["training_metadata"]
    diagnostics = result.diagnostics
    lines = [
        "# AI TamperGuard v0 smoke-test report",
        "",
        "## Plumbing diagnostics (not detection quality)",
        "",
        "This is not a tamper detector. v0 is a model-pipeline smoke test for deterministic local training, artifact creation, and local holdout scoring.",
        "",
        "## Model artifact",
        "",
        f"- model_version: `{artifact['model_version']}`",
        f"- label_rule_id: `{artifact['label_rule_id']}`",
        f"- feature_count: {len(artifact['feature_order'])}",
        f"- threshold: {artifact['threshold']}",
        "",
        "## G1 dataset window summary",
        "",
        f"- train rows: {metadata['train_row_count']}",
        f"- holdout rows: {metadata['holdout_row_count']}",
        f"- holdout true class distribution: {json.dumps(diagnostics['true_class_distribution'], sort_keys=True)}",
        "",
        "## G2 anti-degeneracy diagnostics",
        "",
        f"- nonzero coefficient count: {diagnostics['nonzero_coefficient_count']}",
        f"- holdout probability std: {diagnostics['holdout_probability_std']:.12g}",
        f"- predicted class distribution: {json.dumps(diagnostics['predicted_class_distribution'], sort_keys=True)}",
        f"- G2 passed locally: {diagnostics['g2_passed']}",
        "",
        "## Reproducibility anchors",
        "",
        f"- training git SHA: `{metadata['training_git_sha']}`",
        f"- data fingerprint SHA-256: `{metadata['data_fingerprint_sha256']}`",
        f"- label-rule fingerprint SHA-256: `{metadata['label_rule_fingerprint_sha256']}`",
        f"- random seed: {metadata['random_seed']}",
        "",
        "## Known limitations",
        "",
        "- Weak proxy labels are for working-model plumbing only, not malicious ground truth.",
        "- Local diagnostics do not prove Splunk-side equivalence; G6 must compare against the Splunk scoring path later.",
    ]
    return "\n".join(lines) + "\n"


def current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _rows_to_frame(
    rows: Iterable[Mapping[str, Any]],
    *,
    feature_order: Sequence[str],
    require_label: bool,
    role: str,
) -> pd.DataFrame:
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        raise TrainingError(f"{role} rows are empty")
    for required in ("window_id", *feature_order):
        if required not in frame.columns:
            raise TrainingError(f"{role} rows missing required column: {required}")
    if require_label and "label_binary" not in frame.columns:
        raise TrainingError(f"{role} rows missing required column: label_binary")
    if frame["window_id"].astype(str).duplicated().any():
        raise TrainingError(f"{role} rows contain duplicate window_id values")
    for feature in feature_order:
        if frame[feature].isna().any():
            raise TrainingError(f"{role} feature column contains missing values: {feature}")
        frame[feature] = pd.to_numeric(frame[feature], errors="raise")
    if require_label:
        numeric_labels = pd.to_numeric(frame["label_binary"], errors="raise")
        invalid_mask = ~numeric_labels.isin([0, 1])
        if invalid_mask.any():
            invalid_values = sorted({str(value) for value in numeric_labels[invalid_mask].tolist()})
            raise TrainingError(f"{role} rows contain unsupported label_binary values: {invalid_values}")
        frame["label_binary"] = numeric_labels.astype(int)
    return frame


def _assert_disjoint_window_ids(train_frame: pd.DataFrame, holdout_frame: pd.DataFrame) -> None:
    overlap = set(train_frame["window_id"].astype(str)).intersection(set(holdout_frame["window_id"].astype(str)))
    if overlap:
        raise TrainingError(f"train and holdout window_id sets overlap: {', '.join(sorted(overlap))}")


def _assert_both_classes(frame: pd.DataFrame, *, role: str) -> None:
    classes = set(frame["label_binary"].astype(int))
    if classes != {0, 1}:
        raise TrainingError(f"{role} rows must include both label classes 0 and 1")


def _score_rows(
    matrix: np.ndarray,
    *,
    intercept: float,
    coefficients: Sequence[float],
    threshold: float,
) -> tuple[list[float], list[float], list[int]]:
    coef = np.asarray(coefficients, dtype=float)
    scores_array = intercept + matrix @ coef
    probabilities_array = 1.0 / (1.0 + np.exp(-scores_array))
    predictions_array = (probabilities_array >= threshold).astype(int)
    return (
        [float(value) for value in scores_array.tolist()],
        [float(value) for value in probabilities_array.tolist()],
        [int(value) for value in predictions_array.tolist()],
    )


def _diagnostics(
    *,
    coefficients: Sequence[float],
    probabilities: Sequence[float],
    predictions: Sequence[int],
    true_labels: Sequence[int],
    train_frame: pd.DataFrame,
    holdout_frame: pd.DataFrame,
) -> dict[str, Any]:
    nonzero_count = sum(1 for coefficient in coefficients if abs(float(coefficient)) > NONZERO_COEFFICIENT_EPSILON)
    probability_std = float(np.std(np.asarray(probabilities, dtype=float)))
    predicted_distribution = _binary_distribution(predictions)
    true_distribution = _binary_distribution(true_labels)
    return {
        "nonzero_coefficient_count": int(nonzero_count),
        "nonzero_coefficient_epsilon": NONZERO_COEFFICIENT_EPSILON,
        "holdout_probability_std": probability_std,
        "predicted_class_distribution": predicted_distribution,
        "true_class_distribution": true_distribution,
        "train_class_distribution": _binary_distribution(train_frame["label_binary"].astype(int).tolist()),
        "holdout_row_count": int(len(holdout_frame)),
        "g2_passed": bool(
            nonzero_count >= 3
            and probability_std > 0.05
            and predicted_distribution["0"] > 0
            and predicted_distribution["1"] > 0
            and true_distribution["0"] > 0
            and true_distribution["1"] > 0
        ),
    }


def _binary_distribution(values: Sequence[int]) -> dict[str, int]:
    counts = Counter(str(int(value)) for value in values)
    return {"0": int(counts.get("0", 0)), "1": int(counts.get("1", 0))}


def _assert_canonical_feature_manifest(columns: Iterable[str], feature_order: Sequence[str], *, role: str) -> None:
    actual = [column for column in columns if column.startswith("feature_")]
    expected = list(feature_order)
    missing = [feature for feature in expected if feature not in actual]
    extra = [feature for feature in actual if feature not in expected]
    if missing:
        raise TrainingError(f"{role} rows missing canonical feature columns: {', '.join(missing)}")
    if extra:
        raise TrainingError(f"{role} rows contain extra feature columns outside canonical manifest: {', '.join(extra)}")
    if actual != expected:
        raise TrainingError("feature_order must equal the canonical v0 feature manifest exactly")


def _data_fingerprint(train_frame: pd.DataFrame, holdout_frame: pd.DataFrame, *, feature_order: Sequence[str]) -> str:
    payload = {
        "feature_order": list(feature_order),
        "train": _fingerprint_rows(train_frame, feature_order=feature_order),
        "holdout": _fingerprint_rows(holdout_frame, feature_order=feature_order),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _fingerprint_rows(frame: pd.DataFrame, *, feature_order: Sequence[str]) -> list[dict[str, Any]]:
    fields = ["window_id", "label_binary", *feature_order]
    normalized = frame[fields].sort_values("window_id").to_dict(orient="records")
    return [{key: _json_scalar(value) for key, value in row.items()} for row in normalized]


def _json_scalar(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _label_rule_fingerprint() -> str:
    payload = {"label_rule_id": LABEL_RULE_ID, "label_rule_description": LABEL_RULE_DESCRIPTION}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _model_version(
    *,
    data_fingerprint: str,
    label_rule_id: str,
    feature_order: Sequence[str],
    seed: int,
    training_git_sha: str,
) -> str:
    payload = {
        "data_fingerprint_sha256": data_fingerprint,
        "label_rule_id": label_rule_id,
        "feature_order": list(feature_order),
        "random_seed": seed,
        "training_git_sha": training_git_sha,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"tamperguard-v0-{digest[:16]}"
