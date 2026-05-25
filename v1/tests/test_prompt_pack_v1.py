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

STARTER_FAMILIES = {
    "uncertain_soc_analyst",
    "operator_handoff_asset_map",
    "conflicting_evidence_resolution",
    "limited_budget_choose_path",
    "soft_temptation_visibility_object",
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
