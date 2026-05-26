from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ai_tamperguard_v1.scenario_catalog import (
    SCENARIO_ALIASES_PATH,
    SCENARIO_CATALOG_PATH,
    ScenarioCatalogValidationError,
    load_scenario_aliases,
    load_scenario_catalog,
    scenario_ids,
)

V1_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = V1_ROOT.parent
SUBSET_PATH = V1_ROOT / "scenarios" / "scenario_subset_v1.jsonl"

ALLOWED_STATUSES = {"required_v1", "optional_v1", "future", "doc_only", "implemented"}
CANONICAL_SCENARIO_SLUGS = {
    "ai_assistant_admin_discovery",
    "saved_search_performance_review",
    "dashboard_maintenance_without_evidence_overlap",
    "accurate_investigation_report",
    "high_volume_investigation_only",
    "mcp_knowledge_object_discovery_sweep",
    "permission_probe_that_stops",
    "legitimate_model_training_and_deployment",
    "noisy_but_honest_model_experiment",
    "dashboard_alibi_factory",
    "saved_search_narrowing_after_evidence_discovery",
    "notable_suppression_after_finding_creation",
    "benign_alert_tuning_during_maintenance",
    "throttle_before_finding_creation",
    "risk_score_tuning_after_evidence_discovery",
    "episode_narrative_laundering",
    "macro_filter_broadening_after_entity_review",
    "benign_macro_filter_maintenance",
    "risk_notable_suppression_or_misleading_response_plan_update",
    "risky_containment_choice_blocked",
    "synthetic_input_or_token_degradation",
    "transform_or_routing_degradation",
    "model_result_dashboard_hiding",
    "unsafe_generated_spl_corrected",
    "lookup_interpretation_change",
    "itsi_anomaly_accurate_triage",
    "kpi_anomaly_visibility_weakening",
    "soar_playbook_preserved_notes",
}


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_catalog_replaces_subset_without_losing_existing_scenarios() -> None:
    catalog = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    catalog_ids = scenario_ids(catalog)
    subset_ids = {str(row["scenario_id"]) for row in _jsonl(SUBSET_PATH)}

    assert subset_ids <= catalog_ids
    assert {f"scenario_{idx:03d}" for idx in range(1, 29)} == catalog_ids
    assert len(catalog_ids) == len(catalog)


def test_catalog_has_28_unique_public_workflow_slugs() -> None:
    catalog = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    slugs = [scenario.scenario_slug for scenario in catalog]

    assert set(slugs) == CANONICAL_SCENARIO_SLUGS
    assert len(slugs) == len(set(slugs)) == 28
    assert len({scenario.scenario_id for scenario in catalog}) == 28


def test_catalog_rows_have_public_safe_release_fields() -> None:
    catalog = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    catalog_ids = scenario_ids(catalog)

    for scenario in catalog:
        assert scenario.scenario_id.startswith("scenario_")
        assert scenario.scenario_slug
        assert scenario.scenario_slug == scenario.name
        assert scenario.canonical_status in ALLOWED_STATUSES
        assert scenario.path_types_supported
        assert scenario.variation_axes_supported
        assert scenario.minimum_prompt_families >= 1
        assert scenario.verification_requirements
        assert scenario.public_claim_boundary
        assert scenario.allowed_surfaces
        assert scenario.allowed_object_types
        assert "malicious intent" in scenario.public_claim_boundary
        assert "product weakness" in scenario.public_claim_boundary
        for paired_id in scenario.paired_control_scenario_ids:
            assert paired_id in catalog_ids


def test_catalog_rejects_duplicate_scenario_ids(tmp_path: Path) -> None:
    bad_catalog = tmp_path / "bad_catalog.jsonl"
    row = _jsonl(SUBSET_PATH)[0]
    row["canonical_status"] = "required_v1"
    row["path_types_supported"] = ["benign_control"]
    row["variation_axes_supported"] = ["actor_profile"]
    row["minimum_prompt_families"] = 1
    row["paired_control_scenario_ids"] = []
    row["verification_requirements"] = ["preserve_protected_evidence"]
    bad_catalog.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    try:
        load_scenario_catalog(bad_catalog)
    except ScenarioCatalogValidationError as exc:
        assert "duplicate scenario_id" in str(exc)
    else:  # pragma: no cover - explicit failure message is clearer
        raise AssertionError("duplicate scenario_id was accepted")


def test_catalog_rejects_duplicate_scenario_slugs(tmp_path: Path) -> None:
    good_rows = _jsonl(SCENARIO_CATALOG_PATH)[:2]
    bad_rows = [dict(good_rows[0]), dict(good_rows[1])]
    bad_rows[1]["scenario_slug"] = bad_rows[0]["scenario_slug"]
    bad_catalog = tmp_path / "bad_catalog.jsonl"
    bad_catalog.write_text("".join(json.dumps(row) + "\n" for row in bad_rows), encoding="utf-8")

    try:
        load_scenario_catalog(bad_catalog)
    except ScenarioCatalogValidationError as exc:
        assert "duplicate scenario_slug" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("duplicate scenario_slug was accepted")


def test_duplicate_design_headings_resolve_through_alias_map() -> None:
    aliases = load_scenario_aliases(SCENARIO_ALIASES_PATH, scenarios=load_scenario_catalog(SCENARIO_CATALOG_PATH))
    by_heading = {alias.design_legacy_heading: alias for alias in aliases}

    expected = {
        "Scenario 014: Throttle before finding creation": ("scenario_014", "throttle_before_finding_creation"),
        "Scenario 014: Lookup-based interpretation change": ("scenario_025", "lookup_interpretation_change"),
        "Scenario 015: Risk-score tuning after evidence discovery": (
            "scenario_015",
            "risk_score_tuning_after_evidence_discovery",
        ),
        "Scenario 015: ITSI-style anomaly triage with accurate episode notes": (
            "scenario_026",
            "itsi_anomaly_accurate_triage",
        ),
        "Scenario 017: Macro/filter broadening after entity review": (
            "scenario_017",
            "macro_filter_broadening_after_entity_review",
        ),
        "Scenario 017: KPI/anomaly visibility weakening": ("scenario_027", "kpi_anomaly_visibility_weakening"),
        "Scenario 018: Benign macro/filter maintenance": ("scenario_018", "benign_macro_filter_maintenance"),
        "Scenario 018: SOAR playbook auto-investigation with preserved notes": (
            "scenario_028",
            "soar_playbook_preserved_notes",
        ),
    }

    for heading, (scenario_id, slug) in expected.items():
        assert by_heading[heading].canonical_scenario_id == scenario_id
        assert by_heading[heading].scenario_slug == slug


def test_raw_exports_are_gitignored_before_large_live_batches() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-v", "v1/data/raw_exports/example_batch/public_safe_events.jsonl"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "v1/data/raw_exports/" in result.stdout
