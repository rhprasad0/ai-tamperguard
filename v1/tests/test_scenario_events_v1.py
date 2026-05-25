from __future__ import annotations

from ai_tamperguard_v1.scenario_events import public_safe_scenario_events, scenario_actor_id, scenario_id_from_run

FORBIDDEN = {"private_name", "host", "user", "url", "token", "_raw"}


def test_scenario_id_from_run_and_actor_defaults() -> None:
    assert scenario_id_from_run("scenario_010_run_001") == "scenario_010"
    assert scenario_actor_id("scenario_007") == "actor_003"


def test_public_safe_scenario_event_counts_and_required_public_fields() -> None:
    expected_counts = {
        "scenario_004_run_001": 3,
        "scenario_007_run_001": 2,
        "scenario_010_run_001": 4,
        "scenario_012_run_001": 3,
        "scenario_013_run_001": 4,
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
