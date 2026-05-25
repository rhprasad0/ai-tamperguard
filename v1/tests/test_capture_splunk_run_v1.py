from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _private_files(root: Path, scenario: str = "scenario_010", reset_id: str = "reset_010_001") -> tuple[Path, Path]:
    private_dir = root / "splunk" / "private"
    private_dir.mkdir(parents=True)
    cfg = private_dir / "lab.toml"
    cfg.write_text(
        'authorized_lab_marker = "ai_tamperguard_v1_lab"\n'
        'target_namespace = "ai_tamperguard_v1"\n'
        'capture_destination = "data/private/raw_exports"\n'
        'allowed_indexes = ["_audit", "_configtracker", "openclaw_tamper_lab"]\n'
        'protected_indexes = ["_audit", "_configtracker"]\n'
        'synthetic_evidence_index = "openclaw_tamper_lab"\n'
        '\n[sacrificial]\n'
        'allowed_app = "ai_tamperguard_v1"\n'
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report"]\n',
        encoding="utf-8",
    )
    reset_dir = root / "data" / "private" / "resets"
    reset_dir.mkdir(parents=True)
    reset = reset_dir / f"{reset_id}.json"
    reset.write_text(
        json.dumps(
            {
                "reset_id": reset_id,
                "scenario_id": scenario,
                "status": "reset_manifest_recorded",
                "sacrificial_artifact_ids": ["object_000010"],
                "sacrificial_object_types": ["dashboard"],
                "preserved_evidence_surfaces": ["splunk_audit", "splunk_configtracker"],
            }
        ),
        encoding="utf-8",
    )
    return cfg, reset


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_capture_writes_private_public_safe_event_rows_from_reset_manifest(tmp_path: Path) -> None:
    cfg, _reset = _private_files(tmp_path)
    output_dir = tmp_path / "data" / "private" / "raw_exports" / "batch_001" / "scenario_010_run_001"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "capture_splunk_run_v1.py"),
            "--config",
            str(cfg),
            "--scenario-run-id",
            "scenario_010_run_001",
            "--reset-id",
            "reset_010_001",
            "--output-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    manifest = json.loads((output_dir / "capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "captured_private_public_safe_scaffold"
    assert manifest["scenario_id"] == "scenario_010"
    assert manifest["public_release_ready"] is False
    events = _jsonl(output_dir / "public_safe_events_private.jsonl")
    assert [event["source_derivation"] for event in events] == ["live_lab_public_redacted"] * len(events)
    assert {event["scenario_run_id"] for event in events} == {"scenario_010_run_001"}
    assert any(event["action"] == "modify" and event["object_type"] == "dashboard" for event in events)


def test_capture_rejects_mismatched_scenario_run_and_reset(tmp_path: Path) -> None:
    cfg, _reset = _private_files(tmp_path, scenario="scenario_004", reset_id="reset_004_001")
    output_dir = tmp_path / "data" / "private" / "raw_exports" / "batch_001" / "scenario_010_run_001"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "capture_splunk_run_v1.py"),
            "--config",
            str(cfg),
            "--scenario-run-id",
            "scenario_010_run_001",
            "--reset-id",
            "reset_004_001",
            "--output-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "does not match reset scenario" in result.stderr
