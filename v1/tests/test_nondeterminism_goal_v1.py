from __future__ import annotations

from pathlib import Path

from ai_tamperguard_v1.nondeterminism_goal import (
    acceptance_status,
    classify_attempt_group,
    feature_signature,
    load_existing_summary,
    summarize_group_variability,
    summarize_scenario_variability,
    trajectory_signature,
)


def test_load_existing_summary_reproduces_preserved_live_goal() -> None:
    v1_root = Path(__file__).resolve().parents[1]
    baseline = load_existing_summary(
        v1_root / "reports" / "goal_runs" / "live_goal_nondet50_20260525T214956Z" / "goal-summary.json"
    )

    assert baseline.batch_id == "live_goal_nondet50_20260525T214956Z"
    assert baseline.group_count == 4
    assert baseline.classification_counts["variable"] == 4
    assert baseline.classification_counts.get("stable", 0) == 0
    assert baseline.nondet_group_count == 4
    assert baseline.group_nondet_rate == 1.0

    status = acceptance_status(baseline, target_group_rate=0.50, target_scenario_rate=0.50)
    assert status["status"] == "accepted"
    assert status["reasons"] == []


def test_group_classifier_distinguishes_stable_partial_and_variable() -> None:
    stable = [
        {"attempt_index": 1, "trajectory_signature": "a"},
        {"attempt_index": 2, "trajectory_signature": "a"},
        {"attempt_index": 3, "trajectory_signature": "a"},
    ]
    partial = [
        {"attempt_index": 1, "trajectory_signature": "a"},
        {"attempt_index": 2, "trajectory_signature": "b"},
        {"attempt_index": 3, "trajectory_signature": "b"},
    ]
    variable = [
        {"attempt_index": 1, "trajectory_signature": "a"},
        {"attempt_index": 2, "trajectory_signature": "b"},
        {"attempt_index": 3, "trajectory_signature": "c"},
    ]

    assert classify_attempt_group(stable) == "stable"
    assert classify_attempt_group(partial) == "partially_variable"
    assert classify_attempt_group(variable) == "variable"


def test_signatures_ignore_run_identity_but_capture_behavior_changes() -> None:
    first = [
        {
            "scenario_run_id": "run_a",
            "batch_id": "batch_a",
            "attempt_index": 1,
            "event_order": 1,
            "event_family": "splunk_search",
            "normalized_action": "read",
            "object_type": "dashboard",
        }
    ]
    second = [{**first[0], "scenario_run_id": "run_b", "batch_id": "batch_b", "attempt_index": 2}]
    changed = [{**second[0], "normalized_action": "modify"}]

    assert trajectory_signature(first) == trajectory_signature(second)
    assert trajectory_signature(first) != trajectory_signature(changed)
    assert feature_signature({"scenario_run_id": "a", "feature_risk_tuning": 1, "feature_denied_probe_count": 0}) == feature_signature(
        {"scenario_run_id": "b", "feature_denied_probe_count": 0, "feature_risk_tuning": 1}
    )


def test_summaries_and_acceptance_handle_thresholds_and_fail_closed_gates() -> None:
    groups = []
    for idx in range(23):
        groups.append(
            {
                "scenario_id": f"scenario_{idx % 11:03d}",
                "prompt_variant_id": f"variant_{idx}",
                "attempts": [1, 2, 3],
                "classification": "partially_variable" if idx < 12 else "stable",
                "feature_classification": "partially_variable" if idx < 12 else "stable",
            }
        )

    group_summary = summarize_group_variability(groups)
    scenario_summary = summarize_scenario_variability(groups)
    assert group_summary["group_count"] == 23
    assert group_summary["nondet_group_count"] == 12
    assert group_summary["group_nondet_rate"] == 12 / 23
    assert scenario_summary["scenario_count"] >= 6
    assert scenario_summary["scenario_nondet_rate"] >= 0.50

    accepted = acceptance_status(
        {**group_summary, **scenario_summary, "semantic_failures": [], "control_drift_findings": [], "missing_attempt_groups": []},
        target_group_rate=0.50,
        target_scenario_rate=0.50,
    )
    assert accepted["status"] == "accepted"

    rejected_semantic = acceptance_status(
        {**group_summary, **scenario_summary, "semantic_failures": ["bad"], "control_drift_findings": [], "missing_attempt_groups": []},
        target_group_rate=0.50,
        target_scenario_rate=0.50,
    )
    assert rejected_semantic["status"] == "rejected"
    assert "semantic_failures" in rejected_semantic["reasons"]

    rejected_missing_attempts = acceptance_status(
        {**group_summary, **scenario_summary, "semantic_failures": [], "control_drift_findings": [], "missing_attempt_groups": ["scenario_004/a"]},
        target_group_rate=0.50,
        target_scenario_rate=0.50,
    )
    assert rejected_missing_attempts["status"] == "rejected"
    assert "missing_attempt_groups" in rejected_missing_attempts["reasons"]
