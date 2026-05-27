from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

FORBIDDEN_MODEL_FEATURES = {
    "window_id",
    "scenario_run_id",
    "actor_id",
    "label_binary",
    "label_family",
    "label_source",
    "split_id",
    "reset_id",
    "window_type",
    "label_confidence",
    "outcome",
    "source_batch_id",
    "source_input_path_count",
    "window_start_relative_sec",
    "window_end_relative_sec",
}


class FeaturePolicyError(ValueError):
    """Raised when a feature policy violates the explicit-allowlist contract."""


@dataclass(frozen=True)
class ResolvedFeaturePolicy:
    path: Path
    sha256: str
    allowlist: list[str]
    denylist_generator_signature: list[str]
    denylist_cross_split_population: list[str]
    leakage_probe_overrides: dict[str, str]
    feature_order: list[str]
    unclassified_feature_columns: list[str]
    selection_mode: str = "explicit_allowlist_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_path": self.path.as_posix(),
            "policy_sha256": self.sha256,
            "allowlist": self.allowlist,
            "allowlist_resolved": self.feature_order,
            "denylist_generator_signature_applied": self.denylist_generator_signature,
            "denylist_cross_split_population_applied": self.denylist_cross_split_population,
            "leakage_probe_overrides": self.leakage_probe_overrides,
            "csv_feature_columns_unclassified": self.unclassified_feature_columns,
            "selection_mode": self.selection_mode,
        }


def resolve_feature_policy(policy_path: str | Path, *, csv_columns: Iterable[str]) -> ResolvedFeaturePolicy:
    path = Path(policy_path)
    if not path.exists():
        raise FeaturePolicyError(f"feature policy not found: {path}")
    raw = path.read_bytes()
    try:
        payload = yaml.safe_load(raw.decode("utf-8")) or {}
    except yaml.YAMLError as exc:
        raise FeaturePolicyError(f"feature policy failed to parse: {exc}") from exc
    if payload.get("schema_version") != "feature_policy_v1":
        raise FeaturePolicyError("feature policy must declare schema_version: feature_policy_v1")

    allowlist = _string_list(payload.get("allowlist"), "allowlist")
    deny_gen = _string_list(payload.get("denylist_generator_signature", []), "denylist_generator_signature")
    deny_pop = _string_list(payload.get("denylist_cross_split_population", []), "denylist_cross_split_population")
    overrides_raw = payload.get("leakage_probe_overrides", {}) or {}
    if not isinstance(overrides_raw, dict):
        raise FeaturePolicyError("leakage_probe_overrides must be a mapping from feature to reviewer note")
    overrides = {str(k): str(v) for k, v in overrides_raw.items()}

    if not allowlist:
        raise FeaturePolicyError("feature policy allowlist must be non-empty")
    forbidden = sorted(set(allowlist).intersection(FORBIDDEN_MODEL_FEATURES))
    if forbidden:
        raise FeaturePolicyError(f"feature policy allowlist includes forbidden metadata columns: {forbidden}")
    for feature in allowlist + deny_gen + deny_pop:
        if not feature.startswith("feature_"):
            raise FeaturePolicyError(f"feature policy entries must be feature_* columns, got: {feature}")

    overlap = (set(allowlist) & set(deny_gen)) | (set(allowlist) & set(deny_pop)) | (set(deny_gen) & set(deny_pop))
    if overlap:
        raise FeaturePolicyError(f"feature policy lists overlap: {sorted(overlap)}")

    columns = list(csv_columns)
    csv_features = sorted(c for c in columns if c.startswith("feature_"))
    classified = set(allowlist) | set(deny_gen) | set(deny_pop)
    unclassified = sorted(set(csv_features) - classified)
    if unclassified:
        raise FeaturePolicyError(f"unclassified feature_ columns in CSV: {unclassified}")

    missing_allowlisted = sorted(set(allowlist) - set(columns))
    if missing_allowlisted:
        raise FeaturePolicyError(f"allowlisted features missing from CSV: {missing_allowlisted}")

    feature_order = [feature for feature in allowlist if feature in columns]
    if not feature_order:
        raise FeaturePolicyError("resolved feature set is empty after applying policy")
    if not set(feature_order).issubset(set(allowlist)):
        raise FeaturePolicyError("resolved feature set is not a subset of the explicit allowlist")
    if set(feature_order) & (set(deny_gen) | set(deny_pop)):
        raise FeaturePolicyError("resolved feature set includes denylisted features")

    return ResolvedFeaturePolicy(
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
        allowlist=allowlist,
        denylist_generator_signature=deny_gen,
        denylist_cross_split_population=deny_pop,
        leakage_probe_overrides=overrides,
        feature_order=feature_order,
        unclassified_feature_columns=unclassified,
    )


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise FeaturePolicyError(f"{field} must be a list of strings")
    return list(value)
