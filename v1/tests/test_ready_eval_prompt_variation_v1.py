from __future__ import annotations

from ai_tamperguard_v1.nondeterminism_goal import trajectory_signature
from ai_tamperguard_v1.scenario_events import public_safe_scenario_events


def _signatures_for(scenario_id: str, prompt_family: str) -> set[str]:
    return {
        trajectory_signature(
            public_safe_scenario_events(
                scenario_id=scenario_id,
                scenario_run_id=f"{scenario_id}_nondet_{prompt_family}_attempt_{attempt_index:03d}",
                artifact_ids=("object_000010",),
                prompt_variant_id=f"{prompt_family}_v1_a",
                prompt_family=prompt_family,
                prompt_pack_version="nondet-v1-20260525",
                prompt_seed=20260524 + attempt_index,
                attempt_index=attempt_index,
            )
        )
        for attempt_index in (1, 2, 3)
    }


def test_ready_eval_prompt_families_vary_for_non_006_scenarios() -> None:
    ready_cases = [
        ("scenario_004", "uncertain_soc_analyst"),
        ("scenario_007", "limited_budget_choose_path"),
        ("scenario_010", "operator_handoff_asset_map"),
        ("scenario_012", "suppression_throttle_disambiguation"),
        ("scenario_013", "soft_temptation_visibility_object"),
        ("scenario_014", "suppression_throttle_disambiguation"),
        ("scenario_015", "risk_score_tuning_path"),
        ("scenario_017", "macro_filter_visibility_path"),
        ("scenario_018", "macro_filter_visibility_path"),
    ]

    for scenario_id, prompt_family in ready_cases:
        signatures = _signatures_for(scenario_id, prompt_family)
        assert len(signatures) > 1, (scenario_id, prompt_family, signatures)


def test_ready_eval_variation_stays_public_safe_and_synthetic() -> None:
    events = public_safe_scenario_events(
        scenario_id="scenario_010",
        scenario_run_id="scenario_010_nondet_operator_handoff_asset_map_v1_a_attempt_001",
        artifact_ids=("object_000010",),
        prompt_variant_id="operator_handoff_asset_map_v1_a",
        prompt_family="operator_handoff_asset_map",
        prompt_pack_version="nondet-v1-20260525",
        prompt_seed=20260525,
        attempt_index=1,
    )

    assert events
    assert {event["redaction_level"] for event in events} == {"public_safe"}
    assert {event["source_derivation"] for event in events} == {"live_lab_public_redacted"}
    assert all(event["scenario_id"] == "scenario_010" for event in events)
    assert all(event["prompt_family"] == "operator_handoff_asset_map" for event in events)
