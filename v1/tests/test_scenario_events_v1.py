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
            assert not (FORBIDDEN & set(event))
