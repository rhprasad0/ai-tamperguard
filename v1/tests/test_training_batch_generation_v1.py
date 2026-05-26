from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

V1_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = V1_ROOT / "scripts" / "generate_training_batch_v1.py"
SCENARIO_CATALOG = V1_ROOT / "scenarios" / "scenario_catalog_v1.jsonl"
PATH_TEMPLATES = V1_ROOT / "scenarios" / "path_templates_v1.jsonl"
PROMPT_PACK = V1_ROOT / "scenarios" / "nondeterministic_prompt_pack_v1.jsonl"


def test_generate_training_batch_writes_all_scenario_dry_run_manifest(tmp_path: Path) -> None:
    batch_id = "pytest_all_scenarios_dry"
    target_runs = 42
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--scenario-catalog",
            str(SCENARIO_CATALOG),
            "--path-templates",
            str(PATH_TEMPLATES),
            "--prompt-pack",
            str(PROMPT_PACK),
            "--batch-id",
            batch_id,
            "--target-runs",
            str(target_runs),
            "--target-windows-min",
            "5000",
            "--target-windows-max",
            "5500",
            "--seed",
            "260526",
            "--mode",
            "dry-run",
            "--output-dir",
            f"data/run_manifests/{batch_id}",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output_dir = tmp_path / "data" / "run_manifests" / batch_id
    scenario_runs_path = output_dir / "scenario_runs.jsonl"
    coverage_path = output_dir / "coverage_summary.json"
    assert scenario_runs_path.exists()
    assert coverage_path.exists()

    rows = [json.loads(line) for line in scenario_runs_path.read_text(encoding="utf-8").splitlines()]
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    assert coverage["batch_id"] == batch_id
    assert coverage["mode"] == "dry-run"
    assert coverage["target_windows_min"] == 5000
    assert coverage["target_windows_max"] == 5500
    assert coverage["all_catalog_scenarios_covered"] is True
    assert coverage["scenario_count"] == 14
    assert coverage["scenario_run_count"] == target_runs
    assert len(rows) == target_runs
    assert {row["scenario_id"] for row in rows} == set(coverage["scenario_ids"])
    assert len({row["actor_profile"] for row in rows}) > 1
    assert len({row["evidence_order"] for row in rows}) > 1
    assert len({row["conflict_intensity"] for row in rows}) > 1

    required_manifest_fields = {
        "scenario_run_id",
        "scenario_id",
        "path_type",
        "ground_truth_family",
        "outcome",
        "prompt_variant_id",
        "label_source",
        "actor_prompt_path",
        "actor_profile",
        "evidence_order",
        "conflict_intensity",
        "distractor_count",
        "object_family",
    }
    for row in rows:
        assert required_manifest_fields <= set(row)
        assert (tmp_path / row["actor_prompt_path"]).exists()
