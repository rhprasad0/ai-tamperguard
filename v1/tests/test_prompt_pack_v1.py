from __future__ import annotations

import re
from pathlib import Path

import pytest

from ai_tamperguard_v1.prompt_pack import (
    PROMPT_PACK_PATH,
    PromptPackValidationError,
    load_prompt_pack,
    prompt_variant_by_id,
)
from ai_tamperguard_v1.scenario_catalog import SCENARIO_CATALOG_PATH, load_scenario_catalog

STARTER_FAMILIES = {
    "uncertain_soc_analyst",
    "operator_handoff_asset_map",
    "conflicting_evidence_resolution",
    "limited_budget_choose_path",
    "soft_temptation_visibility_object",
    "risk_score_tuning_path",
    "suppression_throttle_disambiguation",
    "macro_filter_visibility_path",
    "itsi_episode_triage",
    "synthetic_input_token_path",
    "model_training_validation",
}

FORBIDDEN_TEMPLATE_PATTERNS = {
    "ip address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "url": re.compile(r"https?://|www\."),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "local path": re.compile(r"/(home|Users|var|etc)/[A-Za-z0-9._/-]+"),
    "credential assignment": re.compile(r"(?i)(password|passwd|api[_-]?key|secret|bearer|token)\s*[:=]"),
    "raw spl pipe": re.compile(r"\|\s*(stats|table|search|where|eval)\b", re.IGNORECASE),
}

REQUIRED_FIELDS = {
    "prompt_variant_id",
    "prompt_family",
    "prompt_pack_version",
    "allowed_scenario_ids",
    "trajectory_goal_family",
    "max_tool_budget",
    "template",
    "safety_boundary",
    "expected_public_event_families",
}


def test_prompt_pack_loads_public_safe_catalog() -> None:
    variants = load_prompt_pack(PROMPT_PACK_PATH)

    assert len(variants) >= len(STARTER_FAMILIES)
    assert STARTER_FAMILIES <= {variant.prompt_family for variant in variants}
    assert len({variant.prompt_variant_id for variant in variants}) == len(variants)

    for variant in variants:
        row = variant.to_public_metadata()
        assert REQUIRED_FIELDS <= set(row)
        assert variant.prompt_pack_version.startswith("nondet-v1-")
        assert 2 <= variant.max_tool_budget <= 8
        assert variant.allowed_scenario_ids
        assert variant.expected_public_event_families
        assert "{synthetic_case_id}" in variant.template
        assert "{max_tool_budget}" in variant.template
        assert "raw prompt" not in variant.template.lower()


def test_prompt_pack_templates_avoid_private_or_live_markers() -> None:
    variants = load_prompt_pack(PROMPT_PACK_PATH)

    for variant in variants:
        for label, pattern in FORBIDDEN_TEMPLATE_PATTERNS.items():
            assert not pattern.search(variant.template), f"{variant.prompt_variant_id} contains {label}"
        assert "real system" not in variant.template.lower()
        assert "production" not in variant.template.lower()


def test_prompt_variant_lookup_and_scenario_filtering() -> None:
    variant = prompt_variant_by_id(PROMPT_PACK_PATH, "operator_handoff_asset_map_v1_a")

    assert variant.prompt_family == "operator_handoff_asset_map"
    assert "scenario_006" in variant.allowed_scenario_ids


def test_prompt_pack_rejects_unsupported_placeholder(tmp_path: Path) -> None:
    bad_pack = tmp_path / "bad_prompt_pack.jsonl"
    bad_pack.write_text(
        '{"prompt_variant_id":"bad_variant_v1",'
        '"prompt_family":"uncertain_soc_analyst",'
        '"prompt_pack_version":"nondet-v1-test",'
        '"allowed_scenario_ids":["scenario_006"],'
        '"trajectory_goal_family":"uncertainty_reduction",'
        '"max_tool_budget":5,'
        '"template":"Investigate {unsupported_placeholder} for {synthetic_case_id} using {max_tool_budget} checks.",'
        '"safety_boundary":"synthetic_lab_read_or_report_only",'
        '"expected_public_event_families":["investigation"]}\n',
        encoding="utf-8",
    )

    with pytest.raises(PromptPackValidationError, match="unsupported placeholder"):
        load_prompt_pack(bad_pack)


def test_prompt_pack_covers_attack_pattern_scenarios() -> None:
    variants = load_prompt_pack(PROMPT_PACK_PATH)
    by_family = {variant.prompt_family: variant for variant in variants}

    assert {"scenario_012", "scenario_014"} <= set(by_family["suppression_throttle_disambiguation"].allowed_scenario_ids)
    assert "scenario_015" in by_family["risk_score_tuning_path"].allowed_scenario_ids
    assert {"scenario_017", "scenario_018"} <= set(by_family["macro_filter_visibility_path"].allowed_scenario_ids)
    assert "scenario_016" in by_family["itsi_episode_triage"].allowed_scenario_ids
    assert "scenario_021" in by_family["synthetic_input_token_path"].allowed_scenario_ids
    assert "scenario_023" in by_family["model_training_validation"].allowed_scenario_ids

    for family in [
        "suppression_throttle_disambiguation",
        "risk_score_tuning_path",
        "macro_filter_visibility_path",
        "itsi_episode_triage",
        "synthetic_input_token_path",
        "model_training_validation",
    ]:
        variant = by_family[family]
        assert variant.safety_boundary in {"synthetic_lab_read_or_report_only", "synthetic_lab_report_write_only", "synthetic_lab_sacrificial_only"}
        assert "synthetic" in variant.template.lower()
        assert "live systems" not in variant.template.lower()
        assert any(event_family in variant.expected_public_event_families for event_family in ["repeat_search", "read_visibility_object", "knowledge_object_discovery", "write_report", "synthetic_control_change"])


def test_prompt_pack_covers_every_catalog_scenario() -> None:
    variants = load_prompt_pack(PROMPT_PACK_PATH)
    covered = {scenario_id for variant in variants for scenario_id in variant.allowed_scenario_ids}

    assert {scenario.scenario_id for scenario in load_scenario_catalog(SCENARIO_CATALOG_PATH)} <= covered


def test_prompt_pack_meets_catalog_minimum_prompt_family_counts() -> None:
    variants = load_prompt_pack(PROMPT_PACK_PATH)
    by_scenario: dict[str, set[str]] = {}
    for variant in variants:
        for scenario_id in variant.allowed_scenario_ids:
            by_scenario.setdefault(scenario_id, set()).add(variant.prompt_family)

    for scenario in load_scenario_catalog(SCENARIO_CATALOG_PATH):
        families = by_scenario.get(scenario.scenario_id, set())
        assert len(families) >= scenario.minimum_prompt_families, (scenario.scenario_id, families)


def test_prompt_pack_reuses_families_across_labels_to_reduce_prompt_proxy_risk() -> None:
    variants = load_prompt_pack(PROMPT_PACK_PATH)
    scenarios_by_id = {scenario.scenario_id: scenario for scenario in load_scenario_catalog(SCENARIO_CATALOG_PATH)}

    for variant in variants:
        families = {scenarios_by_id[scenario_id].family for scenario_id in variant.allowed_scenario_ids}
        assert len(families) >= 2 or len(variant.allowed_scenario_ids) >= 2, variant.prompt_variant_id
