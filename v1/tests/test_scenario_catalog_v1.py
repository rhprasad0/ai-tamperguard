from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ai_tamperguard_v1.scenario_catalog import (
    SCENARIO_CATALOG_PATH,
    ScenarioCatalogValidationError,
    load_scenario_catalog,
    scenario_ids,
)

V1_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = V1_ROOT.parent
SUBSET_PATH = V1_ROOT / "scenarios" / "scenario_subset_v1.jsonl"

ALLOWED_STATUSES = {"required_v1", "optional_v1", "future", "doc_only", "implemented"}


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_catalog_replaces_subset_without_losing_existing_scenarios() -> None:
    catalog = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    catalog_ids = scenario_ids(catalog)
    subset_ids = {str(row["scenario_id"]) for row in _jsonl(SUBSET_PATH)}

    assert subset_ids <= catalog_ids
    assert {"scenario_016", "scenario_021", "scenario_023"} <= catalog_ids
    assert len(catalog_ids) == len(catalog)


def test_catalog_rows_have_public_safe_release_fields() -> None:
    catalog = load_scenario_catalog(SCENARIO_CATALOG_PATH)
    catalog_ids = scenario_ids(catalog)

    for scenario in catalog:
        assert scenario.scenario_id.startswith("scenario_")
        assert scenario.canonical_status in ALLOWED_STATUSES
        assert scenario.path_types_supported
        assert scenario.variation_axes_supported
        assert scenario.minimum_prompt_families >= 1
        assert scenario.verification_requirements
        assert scenario.public_claim_boundary
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
