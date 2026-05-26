from __future__ import annotations

from collections import Counter
from pathlib import Path

from ai_tamperguard_v1.path_templates import (
    PATH_TEMPLATES_PATH,
    PathTemplateValidationError,
    load_path_templates,
)
from ai_tamperguard_v1.scenario_catalog import SCENARIO_CATALOG_PATH, load_scenario_catalog, scenario_ids

VALID_PATH_TYPES = {
    "benign_control",
    "hard_negative",
    "gray_zone",
    "attempted_positive",
    "successful_synthetic",
    "blocked",
}
GENERIC_PLACEHOLDER_PHRASES = {
    "read synthetic case context",
    "execute bounded",
    "without protected evidence",
    "record conservative outcome and verification notes",
}
FORBIDDEN_OBJECT_TYPES = {"credential", "real_secret", "protected_evidence_source", "private_lab_config"}


def test_path_templates_cover_every_catalog_scenario() -> None:
    scenarios = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    templates = load_path_templates(PATH_TEMPLATES_PATH, scenarios=scenarios)

    counts = Counter(template.scenario_id for template in templates)
    for scenario_id in scenario_ids(scenarios):
        assert counts[scenario_id] >= 1


def test_path_templates_cover_every_catalog_supported_path_type() -> None:
    scenarios = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    templates = load_path_templates(PATH_TEMPLATES_PATH, scenarios=scenarios)
    by_scenario: dict[str, set[str]] = {}
    for template in templates:
        by_scenario.setdefault(template.scenario_id, set()).add(template.path_type)

    for scenario in scenarios:
        assert by_scenario.get(scenario.scenario_id, set()) == set(scenario.path_types_supported)


def test_path_templates_have_specific_action_sequences_per_scenario_path_type() -> None:
    scenarios = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    templates = load_path_templates(PATH_TEMPLATES_PATH, scenarios=scenarios)
    seen_sequences: dict[tuple[str, tuple[str, ...]], str] = {}

    for template in templates:
        key = (template.scenario_id, template.expected_action_sequence)
        assert key not in seen_sequences, (
            f"{template.path_template_id} duplicates action sequence from {seen_sequences.get(key)}"
        )
        seen_sequences[key] = template.path_template_id
        assert any(template.path_type in step or template.scenario_id in step for step in template.expected_action_sequence)
        joined = " ".join(template.expected_action_sequence).lower()
        assert not any(phrase in joined for phrase in GENERIC_PLACEHOLDER_PHRASES), template.path_template_id
        assert any(
            action in joined
            for action in [
                "search:",
                "read:",
                "modify:",
                "write:",
                "run:",
                "attempt:",
                "status:",
                "fit:",
                "apply:",
                "compare:",
                "verify:",
                "enrich:",
            ]
        ), template.path_template_id


def test_path_templates_are_bounded_and_catalog_compatible() -> None:
    scenarios = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    templates = load_path_templates(PATH_TEMPLATES_PATH, scenarios=scenarios)
    template_ids = {template.path_template_id for template in templates}
    scenarios_by_id = {scenario.scenario_id: scenario for scenario in scenarios}

    for template in templates:
        scenario = scenarios_by_id[template.scenario_id]
        assert template.path_type in VALID_PATH_TYPES
        assert template.path_type in scenario.path_types_supported
        assert template.expected_action_sequence
        assert template.allowed_object_types
        assert template.label_family
        assert template.label_binary_policy in {"benign", "positive_proxy", "needs_review", "hard_negative"}
        assert template.outcome in {"benign", "attempted", "blocked", "failed", "successful_synthetic", "needs_review"}
        assert template.post_run_verification
        assert not set(template.allowed_object_types) & set(template.forbidden_object_types)
        assert FORBIDDEN_OBJECT_TYPES <= set(template.forbidden_object_types)
        if template.paired_control_path_template_id:
            assert template.paired_control_path_template_id in template_ids


def test_positive_capable_path_templates_reference_paired_controls() -> None:
    scenarios = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    templates = load_path_templates(PATH_TEMPLATES_PATH, scenarios=scenarios)
    scenarios_by_id = {scenario.scenario_id: scenario for scenario in scenarios}

    for template in templates:
        scenario = scenarios_by_id[template.scenario_id]
        if template.path_type in {"successful_synthetic", "attempted_positive"} and scenario.paired_control_scenario_ids:
            assert template.paired_control_path_template_id, template.path_template_id


def test_path_template_loader_rejects_unknown_scenario(tmp_path: Path) -> None:
    bad_path = tmp_path / "path_templates.jsonl"
    bad_path.write_text(
        '{"path_template_id":"bad_unknown_scenario",'
        '"scenario_id":"scenario_999",'
        '"path_type":"benign_control",'
        '"expected_action_sequence":["read synthetic fixture"],'
        '"allowed_object_types":["report"],'
        '"forbidden_object_types":["credential"],'
        '"label_family":"benign_control",'
        '"label_binary_policy":"benign",'
        '"outcome":"benign",'
        '"post_run_verification":["preserve protected evidence"],'
        '"paired_control_path_template_id":null}\n',
        encoding="utf-8",
    )

    try:
        load_path_templates(bad_path, scenarios=load_scenario_catalog(SCENARIO_CATALOG_PATH))
    except PathTemplateValidationError as exc:
        assert "unknown scenario_id" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown scenario_id was accepted")
