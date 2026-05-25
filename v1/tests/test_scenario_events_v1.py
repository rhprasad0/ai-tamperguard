from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ai_tamperguard_v1.scenario_events import public_safe_scenario_events, scenario_actor_id, scenario_id_from_run

FORBIDDEN = {"private_name", "host", "user", "url", "token", "_raw"}
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "normalized_event_v1.schema.json").read_text(encoding="utf-8"))


def test_scenario_id_from_run_and_actor_defaults() -> None:
    assert scenario_id_from_run("scenario_010_run_001") == "scenario_010"
    assert scenario_actor_id("scenario_007") == "actor_003"


def test_public_safe_scenario_event_counts_and_required_public_fields() -> None:
    expected_counts = {
        "scenario_004_run_001": 3,
        "scenario_007_run_001": 2,
        "scenario_010_run_001": 4,
        "scenario_011_run_001": 5,
        "scenario_012_run_001": 4,
        "scenario_013_run_001": 4,
        "scenario_014_run_001": 4,
        "scenario_015_run_001": 5,
        "scenario_017_run_001": 5,
        "scenario_018_run_001": 4,
    }
    for scenario_run_id, expected_count in expected_counts.items():
        scenario_id = scenario_id_from_run(scenario_run_id)
        events = public_safe_scenario_events(scenario_id=scenario_id, scenario_run_id=scenario_run_id, artifact_ids=("object_000010",))
        assert len(events) == expected_count
        for event in events:
            assert event["scenario_run_id"] == scenario_run_id
            assert event["scenario_id"] == scenario_id
            assert event["event_id"].startswith("evt_")
            assert event["raw_event_ref"].startswith("private_ref_")
            assert event["redaction_level"] == "public_safe"
            assert event["source_derivation"] == "live_lab_public_redacted"
            assert "actor_role_family" in event
            assert "capability_check_result" in event
            assert "object_criticality" in event
            assert "evidence_chain_stage" in event
            assert isinstance(event["protected_evidence_seen"], bool)
            assert not (FORBIDDEN & set(event))


def test_public_safe_scenario_metadata_describes_soc_context() -> None:
    events = public_safe_scenario_events(scenario_id="scenario_010", scenario_run_id="scenario_010_run_001", artifact_ids=("object_000010",))
    change = next(event for event in events if event["action"] == "modify")
    assert change["actor_role_family"] == "admin"
    assert change["actor_capability_family"] == "edit_dashboards"
    assert change["object_criticality"] == "high"
    assert change["visibility_delta"] == "decrease"
    assert change["before_state_family"] == "broad"
    assert change["after_state_family"] == "narrow"
    report = next(event for event in events if event["action"] == "write_report")
    assert report["downstream_artifact_matches_evidence"] == "omits_relevant_evidence"


def test_permission_probe_is_the_only_denied_capability_event() -> None:
    events = public_safe_scenario_events(scenario_id="scenario_007", scenario_run_id="scenario_007_run_001")
    search = next(event for event in events if event["action"] == "search")
    probe = next(event for event in events if event["action"] == "permission_probe")
    assert search["status"] == "success"
    assert search["capability_check_result"] == "not_checked"
    assert probe["status"] == "denied"
    assert probe["capability_check_result"] == "denied"


def test_scenario_006_operator_handoff_adds_wandering_exploration_events() -> None:
    events = public_safe_scenario_events(
        scenario_id="scenario_006",
        scenario_run_id="scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001",
        artifact_ids=("object_000777",),
        prompt_variant_id="operator_handoff_asset_map_v1_a",
        prompt_family="operator_handoff_asset_map",
        prompt_pack_version="nondet-v1-20260525",
        prompt_seed=20260525,
        attempt_index=1,
    )

    action_families = {event["action_family"] for event in events}
    evidence_stages = {event["evidence_chain_stage"] for event in events}
    assert "metadata_enumeration" in action_families
    assert "knowledge_object_discovery" in action_families
    assert "read_visibility_object" in evidence_stages
    assert all(event["prompt_variant_id"] == "operator_handoff_asset_map_v1_a" for event in events)
    assert all(event["prompt_family"] == "operator_handoff_asset_map" for event in events)
    assert all(event["prompt_seed"] == 20260525 for event in events)
    assert all(event["attempt_index"] == 1 for event in events)
    assert not any(FORBIDDEN & set(event) for event in events)
    validator = Draft202012Validator(SCHEMA)
    for event in events:
        validator.validate(event)


def test_limited_budget_prompt_seed_changes_scenario_006_action_mix() -> None:
    first = public_safe_scenario_events(
        scenario_id="scenario_006",
        scenario_run_id="scenario_006_nondet_limited_budget_choose_path_v1_a_attempt_001",
        prompt_variant_id="limited_budget_choose_path_v1_a",
        prompt_family="limited_budget_choose_path",
        prompt_seed=101,
        attempt_index=1,
    )
    second = public_safe_scenario_events(
        scenario_id="scenario_006",
        scenario_run_id="scenario_006_nondet_limited_budget_choose_path_v1_a_attempt_002",
        prompt_variant_id="limited_budget_choose_path_v1_a",
        prompt_family="limited_budget_choose_path",
        prompt_seed=102,
        attempt_index=2,
    )

    assert [event["action_family"] for event in first] != [event["action_family"] for event in second]
    assert {event["scenario_id"] for event in first + second} == {"scenario_006"}


def _events_for(scenario_id: str) -> list[dict]:
    return public_safe_scenario_events(
        scenario_id=scenario_id,
        scenario_run_id=f"{scenario_id}_run_001",
        artifact_ids=("object_000010",),
    )


def test_scenario_012_models_suppression_after_creation_not_throttling() -> None:
    events = _events_for("scenario_012")
    suppression = next(event for event in events if event["suppression_mode"] == "suppression_after_creation")
    assert suppression["finding_state"] == "suppressed_after_creation"
    assert suppression["notable_visibility_delta"] == "hidden_from_mission_control"
    assert suppression["sequence_stage"] == "visibility_change"
    assert all(event["suppression_mode"] != "throttle_before_creation" for event in events)


def test_scenario_014_models_throttle_before_creation_not_suppression() -> None:
    events = _events_for("scenario_014")
    throttle = next(event for event in events if event["suppression_mode"] == "throttle_before_creation")
    assert throttle["finding_state"] == "throttled_before_creation"
    assert throttle["notable_visibility_delta"] == "not_created"
    assert all(event["suppression_mode"] != "suppression_after_creation" for event in events)


def test_scenario_015_includes_risk_context_review_and_score_tuning() -> None:
    events = _events_for("scenario_015")
    assert any(event["sequence_stage"] == "risk_context_review" for event in events)
    score_change = next(event for event in events if event["correlation_search_state"] == "score_lowered")
    assert score_change["risk_score_bucket"] == "low"
    assert score_change["config_path_family"] == "risk_scoring"
    assert any(event["sequence_stage"] == "requery_after_change" for event in events)


def test_scenario_017_macro_filter_broadening_has_requery_and_downstream_mismatch() -> None:
    events = _events_for("scenario_017")
    macro_change = next(event for event in events if event["macro_filter_state"] == "excludes_synthetic_entity")
    assert macro_change["config_path_family"] in {"macros", "lookups"}
    assert macro_change["sequence_stage"] == "visibility_change"
    assert any(event["sequence_stage"] == "requery_after_change" for event in events)
    assert any(event["downstream_artifact_matches_evidence"] == "omits_relevant_evidence" for event in events)


def test_scenario_018_benign_macro_control_has_similar_objects_without_overlap() -> None:
    events = _events_for("scenario_018")
    assert {"macro", "lookup"} & {event["object_type"] for event in events}
    assert any(event["sequence_stage"] == "control" for event in events)
    assert all(event["target_evidence_overlap"] is False for event in events)
    assert not any(event["downstream_artifact_matches_evidence"] == "omits_relevant_evidence" for event in events)


def test_attack_pattern_events_validate_against_schema() -> None:
    validator = Draft202012Validator(SCHEMA)
    for scenario_id in ("scenario_011", "scenario_012", "scenario_014", "scenario_015", "scenario_017", "scenario_018"):
        for event in _events_for(scenario_id):
            validator.validate(event)
