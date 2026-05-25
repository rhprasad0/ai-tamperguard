from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_splunk_scenario_evidence_v1.py"


def _files(tmp_path: Path, *, hec_index: str = "openclaw_tamper_lab", scenario: str = "scenario_004", reset_id: str = "reset_004_001") -> tuple[Path, Path]:
    private_dir = tmp_path / "splunk" / "private"
    private_dir.mkdir(parents=True)
    cfg = private_dir / "lab.toml"
    cfg.write_text(
        'authorized_lab_marker = "ai_tamperguard_v1_lab"\n'
        'target_namespace = "ai_tamperguard_v1"\n'
        'capture_destination = "data/raw_exports"\n'
        'allowed_indexes = ["_audit", "_configtracker", "openclaw_tamper_lab"]\n'
        'protected_indexes = ["_audit", "_configtracker"]\n'
        'synthetic_evidence_index = "openclaw_tamper_lab"\n'
        '\n[sacrificial]\n'
        'allowed_app = "ai_tamperguard_v1"\n'
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report"]\n'
        '\n[splunk_hec]\n'
        'url = "https://example.invalid/services/collector/event"\n'
        'token_env = "AI_TAMPERGUARD_SPLUNK_HEC_TOKEN"\n'
        f'index = "{hec_index}"\n',
        encoding="utf-8",
    )
    inventory = private_dir / "sacrificial_inventory.toml"
    inventory.write_text(
        'namespace = "ai_tamperguard_v1"\n'
        'synthetic_index = "openclaw_tamper_lab"\n'
        '\n[[artifacts]]\n'
        'object_id = "object_000010"\n'
        'private_name = "tg_v1_private_dashboard_name"\n'
        'object_type = "dashboard"\n'
        f'scenario_ids = ["{scenario}"]\n',
        encoding="utf-8",
    )
    reset_dir = tmp_path / "data" / "resets"
    reset_dir.mkdir(parents=True)
    (reset_dir / f"{reset_id}.json").write_text(
        json.dumps({"reset_id": reset_id, "scenario_id": scenario, "sacrificial_artifact_ids": ["object_000010"]}),
        encoding="utf-8",
    )
    return cfg, inventory


def _run(
    tmp_path: Path,
    cfg: Path,
    inventory: Path,
    *,
    scenario: str,
    scenario_run_id: str,
    reset_id: str,
    output: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(cfg),
            "--inventory",
            str(inventory),
            "--scenario",
            scenario,
            "--scenario-run-id",
            scenario_run_id,
            "--reset-id",
            reset_id,
            "--batch-id",
            "batch_001",
            "--anchor-epoch",
            "1234567890",
            "--output-manifest",
            str(output),
            "--dry-run",
            *(extra_args or []),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )


def test_seed_dry_run_expected_counts_for_three_scenarios(tmp_path: Path) -> None:
    cases = [("scenario_004", "scenario_004_run_001", "reset_004_001", 3), ("scenario_007", "scenario_007_run_001", "reset_007_001", 2), ("scenario_010", "scenario_010_run_001", "reset_010_001", 4)]
    for scenario, run_id, reset_id, count in cases:
        case_root = tmp_path / scenario
        cfg, inventory = _files(case_root, scenario=scenario, reset_id=reset_id)
        output = case_root / "data" / "seed_manifests" / "batch_001" / f"{run_id}.json"
        result = _run(case_root, cfg, inventory, scenario=scenario, scenario_run_id=run_id, reset_id=reset_id, output=output)
        assert result.returncode == 0, result.stderr
        manifest = json.loads(output.read_text(encoding="utf-8"))
        assert manifest["event_count"] == count
        assert "private_name" not in output.read_text(encoding="utf-8")


def test_seed_propagates_prompt_metadata_for_scenario_006(tmp_path: Path) -> None:
    cfg, inventory = _files(tmp_path, scenario="scenario_006", reset_id="reset_006_001")
    output = tmp_path / "data" / "seed_manifests" / "batch_001" / "scenario_006.json"
    result = _run(
        tmp_path,
        cfg,
        inventory,
        scenario="scenario_006",
        scenario_run_id="scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001",
        reset_id="reset_006_001",
        output=output,
        extra_args=[
            "--prompt-variant-id",
            "operator_handoff_asset_map_v1_a",
            "--prompt-family",
            "operator_handoff_asset_map",
            "--prompt-pack-version",
            "nondet-v1-20260525",
            "--prompt-seed",
            "20260525",
            "--attempt-index",
            "1",
        ],
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["prompt_variant_id"] == "operator_handoff_asset_map_v1_a"
    assert manifest["prompt_family"] == "operator_handoff_asset_map"
    assert manifest["prompt_pack_version"] == "nondet-v1-20260525"
    assert manifest["prompt_seed"] == 20260525
    assert manifest["attempt_index"] == 1
    assert manifest["event_count"] >= 5


def test_seed_rejects_scenario_run_mismatch(tmp_path: Path) -> None:
    cfg, inventory = _files(tmp_path)
    output = tmp_path / "data" / "seed_manifests" / "batch_001" / "x.json"
    result = _run(tmp_path, cfg, inventory, scenario="scenario_004", scenario_run_id="scenario_010_run_001", reset_id="reset_004_001", output=output)
    assert result.returncode == 2
    assert "mismatch" in result.stderr


def test_seed_rejects_missing_reset_manifest(tmp_path: Path) -> None:
    cfg, inventory = _files(tmp_path)
    (tmp_path / "data" / "resets" / "reset_004_001.json").unlink()
    output = tmp_path / "data" / "seed_manifests" / "batch_001" / "x.json"
    result = _run(tmp_path, cfg, inventory, scenario="scenario_004", scenario_run_id="scenario_004_run_001", reset_id="reset_004_001", output=output)
    assert result.returncode == 2
    assert "reset manifest" in result.stderr


def test_seed_rejects_output_manifest_outside_private_seed_manifests(tmp_path: Path) -> None:
    cfg, inventory = _files(tmp_path)
    output = tmp_path / "public" / "seed.json"
    result = _run(tmp_path, cfg, inventory, scenario="scenario_004", scenario_run_id="scenario_004_run_001", reset_id="reset_004_001", output=output)
    assert result.returncode == 2
    assert "data/seed_manifests" in result.stderr


def test_seed_rejects_traversal_out_of_private_seed_manifests(tmp_path: Path) -> None:
    cfg, inventory = _files(tmp_path)
    output = tmp_path / "data" / "seed_manifests" / ".." / ".." / "public" / "seed.json"
    result = _run(tmp_path, cfg, inventory, scenario="scenario_004", scenario_run_id="scenario_004_run_001", reset_id="reset_004_001", output=output)
    assert result.returncode == 2
    assert "data/seed_manifests" in result.stderr


def test_seed_rejects_bad_hec_index(tmp_path: Path) -> None:
    cfg, inventory = _files(tmp_path, hec_index="main")
    output = tmp_path / "data" / "seed_manifests" / "batch_001" / "x.json"
    result = _run(tmp_path, cfg, inventory, scenario="scenario_004", scenario_run_id="scenario_004_run_001", reset_id="reset_004_001", output=output)
    assert result.returncode == 2
    assert "openclaw_tamper_lab" in result.stderr
