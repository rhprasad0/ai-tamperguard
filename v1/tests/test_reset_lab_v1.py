from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_private_config_and_inventory(root: Path) -> tuple[Path, Path]:
    private_dir = root / "splunk" / "private"
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
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report"]\n',
        encoding="utf-8",
    )
    inventory = private_dir / "sacrificial_inventory.toml"
    inventory.write_text(
        'namespace = "ai_tamperguard_v1"\n'
        'synthetic_index = "openclaw_tamper_lab"\n'
        '\n[[artifacts]]\n'
        'object_id = "object_000012"\n'
        'private_name = "tg_v1_alert_suppression"\n'
        'object_type = "alert"\n'
        'scenario_ids = ["scenario_012", "scenario_013"]\n',
        encoding="utf-8",
    )
    return cfg, inventory


def test_reset_allows_attack_pattern_scenario_ids(tmp_path: Path) -> None:
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
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report", "macro", "lookup"]\n',
        encoding="utf-8",
    )
    inventory = private_dir / "sacrificial_inventory.toml"
    entries = [
        ("object_000011", "saved_search", "scenario_011"),
        ("object_000014", "alert", "scenario_014"),
        ("object_000015", "saved_search", "scenario_015"),
        ("object_000017", "macro", "scenario_017"),
        ("object_000018", "macro", "scenario_018"),
    ]
    inventory.write_text(
        'namespace = "ai_tamperguard_v1"\nsynthetic_index = "openclaw_tamper_lab"\n'
        + "".join(
            f'\n[[artifacts]]\nobject_id = "{object_id}"\nprivate_name = "tg_v1_{scenario_id}"\nobject_type = "{object_type}"\nscenario_ids = ["{scenario_id}"]\n'
            for object_id, object_type, scenario_id in entries
        ),
        encoding="utf-8",
    )

    for _object_id, _object_type, scenario_id in entries:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "reset_lab_v1.py"),
                "--config",
                str(cfg),
                "--inventory",
                str(inventory),
                "--scenario",
                scenario_id,
                "--reset-id",
                f"reset_{scenario_id}_test",
            ],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_reset_manifest_uses_inventory_artifacts_for_requested_scenario(tmp_path: Path) -> None:
    cfg, inventory = _write_private_config_and_inventory(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "reset_lab_v1.py"),
            "--config",
            str(cfg),
            "--inventory",
            str(inventory),
            "--scenario",
            "scenario_012",
            "--reset-id",
            "reset_012_test",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    manifest = json.loads((tmp_path / "data" / "resets" / "reset_012_test.json").read_text(encoding="utf-8"))
    assert manifest["scenario_id"] == "scenario_012"
    assert manifest["sacrificial_artifact_ids"] == ["object_000012"]
    assert manifest["status"] == "reset_manifest_recorded"


def test_reset_fails_when_scenario_has_no_inventory_artifact(tmp_path: Path) -> None:
    cfg, inventory = _write_private_config_and_inventory(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "reset_lab_v1.py"),
            "--config",
            str(cfg),
            "--inventory",
            str(inventory),
            "--scenario",
            "scenario_010",
            "--reset-id",
            "reset_010_test",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "no sacrificial artifacts" in result.stderr
