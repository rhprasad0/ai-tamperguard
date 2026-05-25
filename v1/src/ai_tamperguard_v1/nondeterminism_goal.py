from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

STABLE = "stable"
PARTIALLY_VARIABLE = "partially_variable"
VARIABLE = "variable"
NONDET_CLASSIFICATIONS = {PARTIALLY_VARIABLE, VARIABLE}
IDENTITY_FIELDS = {
    "scenario_run_id",
    "batch_id",
    "attempt_index",
    "prompt_seed",
    "timestamp",
    "time",
    "_time",
    "event_id",
    "raw_event_id",
}


@dataclass(frozen=True)
class GoalBaseline:
    batch_id: str
    group_count: int
    classification_counts: dict[str, int]
    feature_classification_counts: dict[str, int]
    nondet_group_count: int
    group_nondet_rate: float
    scenario_count: int
    nondet_scenario_count: int
    scenario_nondet_rate: float
    semantic_failures: list[Any]
    control_drift_findings: list[Any]
    missing_attempt_groups: list[str]
    groups: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "group_count": self.group_count,
            "classification_counts": self.classification_counts,
            "feature_classification_counts": self.feature_classification_counts,
            "nondet_group_count": self.nondet_group_count,
            "group_nondet_rate": self.group_nondet_rate,
            "scenario_count": self.scenario_count,
            "nondet_scenario_count": self.nondet_scenario_count,
            "scenario_nondet_rate": self.scenario_nondet_rate,
            "semantic_failures": self.semantic_failures,
            "control_drift_findings": self.control_drift_findings,
            "missing_attempt_groups": self.missing_attempt_groups,
            "groups": self.groups,
        }


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"expected mapping, got {type(value).__name__}")
    return value


def _stable_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _stable_payload(v) for k, v in sorted(value.items()) if str(k) not in IDENTITY_FIELDS}
    if isinstance(value, list):
        return [_stable_payload(v) for v in value]
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(_stable_payload(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def trajectory_signature(events: Sequence[Mapping[str, Any]] | Mapping[str, Any]) -> str:
    """Return a stable behavior signature for event trajectories.

    Identity/provenance fields are ignored so attempts with the same behavior but
    different run IDs, batch IDs, or attempt indexes compare equal.
    """
    if isinstance(events, Mapping):
        events_seq: Sequence[Mapping[str, Any]] = [events]
    else:
        events_seq = events
    ordered = sorted(
        (_as_mapping(event) for event in events_seq),
        key=lambda event: (event.get("event_order", event.get("sequence_stage", 0)), json.dumps(_stable_payload(event), sort_keys=True, default=str)),
    )
    return _digest(ordered)


def feature_signature(window_or_feature_row: Mapping[str, Any]) -> str:
    """Return a stable signature for derived feature rows."""
    row = _as_mapping(window_or_feature_row)
    feature_payload = {
        key: value
        for key, value in row.items()
        if key.startswith("feature_") or key in {"label", "label_family", "outcome_label", "answer_key_label"}
    }
    if not feature_payload:
        feature_payload = {key: value for key, value in row.items() if key not in IDENTITY_FIELDS}
    return _digest(feature_payload)


def classify_attempt_group(events_or_windows: Sequence[Any]) -> str:
    """Classify a k-attempt group by distinct trajectory/feature signatures."""
    signatures: set[str] = set()
    for item in events_or_windows:
        if isinstance(item, Mapping) and "trajectory_signature" in item:
            signatures.add(str(item["trajectory_signature"]))
        elif isinstance(item, Mapping) and "feature_signature" in item:
            signatures.add(str(item["feature_signature"]))
        elif isinstance(item, Mapping):
            signatures.add(feature_signature(item))
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            signatures.add(trajectory_signature(item))
        else:
            signatures.add(str(item))
    distinct = len(signatures)
    if distinct <= 1:
        return STABLE
    if distinct == 2:
        return PARTIALLY_VARIABLE
    return VARIABLE


def group_key(group: Mapping[str, Any]) -> str:
    return f"{group.get('scenario_id', 'unknown')}/{group.get('prompt_variant_id', 'unknown')}"


def missing_attempt_groups(groups: Iterable[Mapping[str, Any]], *, expected_attempts: Iterable[int] = (1, 2, 3)) -> list[str]:
    expected = set(expected_attempts)
    missing: list[str] = []
    for group in groups:
        attempts = set(group.get("attempts") or [])
        if attempts != expected:
            missing.append(group_key(group))
    return missing


def summarize_group_variability(groups: Sequence[Mapping[str, Any]], *, expected_attempts: Iterable[int] = (1, 2, 3)) -> dict[str, Any]:
    counts = {STABLE: 0, PARTIALLY_VARIABLE: 0, VARIABLE: 0}
    feature_counts = {STABLE: 0, PARTIALLY_VARIABLE: 0, VARIABLE: 0}
    normalized_groups: list[dict[str, Any]] = []
    for group in groups:
        classification = str(group.get("classification") or classify_attempt_group(group.get("attempt_items", [])))
        feature_classification = str(group.get("feature_classification") or classification)
        counts[classification] = counts.get(classification, 0) + 1
        feature_counts[feature_classification] = feature_counts.get(feature_classification, 0) + 1
        normalized_groups.append(dict(group, classification=classification, feature_classification=feature_classification))
    group_count = len(normalized_groups)
    nondet_count = sum(counts.get(name, 0) for name in NONDET_CLASSIFICATIONS)
    return {
        "group_count": group_count,
        "classification_counts": {key: value for key, value in counts.items() if value or key in {STABLE, PARTIALLY_VARIABLE, VARIABLE}},
        "feature_classification_counts": {key: value for key, value in feature_counts.items() if value or key in {STABLE, PARTIALLY_VARIABLE, VARIABLE}},
        "nondet_group_count": nondet_count,
        "group_nondet_rate": nondet_count / group_count if group_count else 0.0,
        "missing_attempt_groups": missing_attempt_groups(normalized_groups, expected_attempts=expected_attempts),
        "groups": normalized_groups,
    }


def summarize_scenario_variability(groups: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scenarios: dict[str, bool] = {}
    for group in groups:
        scenario_id = str(group.get("scenario_id", "unknown"))
        classification = str(group.get("classification", STABLE))
        scenarios.setdefault(scenario_id, False)
        if classification in NONDET_CLASSIFICATIONS:
            scenarios[scenario_id] = True
    scenario_count = len(scenarios)
    nondet_scenario_count = sum(1 for value in scenarios.values() if value)
    return {
        "scenario_count": scenario_count,
        "nondet_scenario_count": nondet_scenario_count,
        "scenario_nondet_rate": nondet_scenario_count / scenario_count if scenario_count else 0.0,
        "scenario_nondeterministic": scenarios,
    }


def acceptance_status(summary: GoalBaseline | Mapping[str, Any], *, target_group_rate: float, target_scenario_rate: float) -> dict[str, Any]:
    data = summary.to_dict() if isinstance(summary, GoalBaseline) else dict(summary)
    reasons: list[str] = []
    if float(data.get("group_nondet_rate", 0.0)) < target_group_rate:
        reasons.append("group_nondet_rate")
    if float(data.get("scenario_nondet_rate", 0.0)) < target_scenario_rate:
        reasons.append("scenario_nondet_rate")
    if data.get("semantic_failures"):
        reasons.append("semantic_failures")
    if data.get("control_drift_findings"):
        reasons.append("control_drift_findings")
    if data.get("missing_attempt_groups"):
        reasons.append("missing_attempt_groups")
    return {"status": "rejected" if reasons else "accepted", "reasons": reasons}


def load_existing_summary(path: str | Path) -> GoalBaseline:
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    groups = [dict(group) for group in raw.get("groups", [])]
    group_summary = summarize_group_variability(groups)
    scenario_summary = summarize_scenario_variability(group_summary["groups"])
    semantic_failures = list(raw.get("semantic_failures") or [])
    control_drift_findings = list(raw.get("control_drift_findings") or [])
    return GoalBaseline(
        batch_id=str(raw.get("batch_id") or source.parent.name),
        group_count=group_summary["group_count"],
        classification_counts=group_summary["classification_counts"],
        feature_classification_counts=group_summary["feature_classification_counts"],
        nondet_group_count=group_summary["nondet_group_count"],
        group_nondet_rate=group_summary["group_nondet_rate"],
        scenario_count=scenario_summary["scenario_count"],
        nondet_scenario_count=scenario_summary["nondet_scenario_count"],
        scenario_nondet_rate=scenario_summary["scenario_nondet_rate"],
        semantic_failures=semantic_failures,
        control_drift_findings=control_drift_findings,
        missing_attempt_groups=group_summary["missing_attempt_groups"],
        groups=group_summary["groups"],
    )
