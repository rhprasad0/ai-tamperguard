from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_valid_private_files(tmp_path: Path) -> tuple[Path, Path, Path]:
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
        'public_sample_policy = "live_run_required"\n'
        '\n[sacrificial]\n'
        'allowed_app = "ai_tamperguard_v1"\n'
        'allowed_object_id_prefixes = ["tg_v1_", "ai_tamperguard_v1_"]\n'
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report", "lookup"]\n',
        encoding="utf-8",
    )
    inventory = private_dir / "sacrificial_inventory.toml"
    inventory.write_text(
        'namespace = "ai_tamperguard_v1"\n'
        'synthetic_index = "openclaw_tamper_lab"\n'
        '\n[[artifacts]]\n'
        'object_id = "object_000010"\n'
        'private_name = "tg_v1_dashboard_alibi_factory"\n'
        'object_type = "dashboard"\n'
        'scenario_ids = ["scenario_010"]\n',
        encoding="utf-8",
    )
    output = tmp_path / "reports" / "private" / "readiness.md"
    return cfg, inventory, output


def test_readiness_cli_fails_closed_without_observed_indexes(tmp_path: Path) -> None:
    cfg, _inventory, output = _write_valid_private_files(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_splunk_readiness_v1.py",
            "--config",
            str(cfg),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "observed index snapshot" in output.read_text(encoding="utf-8")


def test_readiness_cli_passes_with_required_indexes_and_inventory(tmp_path: Path) -> None:
    cfg, inventory, output = _write_valid_private_files(tmp_path)
    observed = tmp_path / "splunk" / "private" / "observed_indexes.json"
    observed.write_text(
        json.dumps(
            {
                "results": [
                    {"title": "_audit", "disabled": "0", "totalEventCount": "10"},
                    {"title": "_configtracker", "disabled": "0", "totalEventCount": "2"},
                    {"title": "openclaw_tamper_lab", "disabled": "0", "totalEventCount": "1"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_splunk_readiness_v1.py",
            "--config",
            str(cfg),
            "--inventory",
            str(inventory),
            "--observed-indexes-json",
            str(observed),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    report = output.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "# Splunk readiness passed" in report
    assert "_audit" in report
    assert "object_000010" in report


def test_readiness_cli_fails_when_required_index_is_missing(tmp_path: Path) -> None:
    cfg, inventory, output = _write_valid_private_files(tmp_path)
    observed = tmp_path / "splunk" / "private" / "observed_indexes.json"
    observed.write_text(json.dumps({"results": [{"title": "_audit", "disabled": "0"}]}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_splunk_readiness_v1.py",
            "--config",
            str(cfg),
            "--inventory",
            str(inventory),
            "--observed-indexes-json",
            str(observed),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    report = output.read_text(encoding="utf-8")
    assert result.returncode == 2
    assert "missing required observed indexes" in report
    assert "_configtracker" in report
    assert "openclaw_tamper_lab" in report
