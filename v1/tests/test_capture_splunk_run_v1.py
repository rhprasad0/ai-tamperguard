from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


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
    assert all("actor_role_family" in event for event in events)
    assert any(event["visibility_delta"] == "decrease" for event in events)


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


def test_capture_accepts_verified_live_rows_jsonl_under_private_raw_exports(tmp_path: Path) -> None:
    cfg, _reset = _private_files(tmp_path)
    batch_dir = tmp_path / "data" / "private" / "raw_exports" / "batch_001" / "scenario_010_run_001"
    batch_dir.mkdir(parents=True)
    rows = batch_dir / "verified_splunk_rows.jsonl"
    rows.write_text(
        json.dumps(
            {
                "event_id": "evt_000010001",
                "relative_time_sec": 60,
                "actor_id": "actor_001",
                "actor_type": "agent_or_admin",
                "source_surface": "synthetic_control_plane",
                "source_index_family": "synthetic_control_plane",
                "source_sourcetype_family": "scenario_operator_note",
                "action": "search",
                "action_family": "investigation",
                "object_type": "dashboard",
                "object_id": "object_000010",
                "object_role": "detection_or_visibility_artifact",
                "status": "success",
                "scenario_id": "scenario_010",
                "scenario_run_id": "scenario_010_run_001",
                "raw_event_ref": "private_ref_010_001_001",
                "redaction_level": "public_safe",
                "source_derivation": "live_splunk_public_redacted",
                "target_evidence_overlap": True,
                "actor_role_family": "admin",
                "actor_capability_family": "edit_dashboards",
                "capability_check_result": "allowed",
                "object_criticality": "high",
                "object_visibility_scope": "global",
                "detection_lifecycle_stage": "enabled",
                "detection_effect_family": "none",
                "before_state_family": "present",
                "after_state_family": "present",
                "change_magnitude_bucket": "none",
                "visibility_delta": "none",
                "protected_evidence_seen": True,
                "downstream_artifact_updated": False,
                "downstream_artifact_matches_evidence": "not_applicable",
                "evidence_chain_stage": "search",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = batch_dir / "capture"

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
            "--require-live-splunk-rows",
            "--verified-live-rows-jsonl",
            str(rows),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    manifest = json.loads((output_dir / "capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "captured_live_splunk_public_safe"
    assert manifest["source_index"] == "openclaw_tamper_lab"
    events = _jsonl(output_dir / "public_safe_events_private.jsonl")
    assert len(events) == 1
    assert events[0]["source_derivation"] == "live_splunk_public_redacted"
    assert events[0]["actor_role_family"] == "admin"
    assert events[0]["object_criticality"] == "high"
    assert events[0]["protected_evidence_seen"] is True
    assert events[0]["downstream_artifact_matches_evidence"] == "not_applicable"


def test_capture_preserves_prompt_pack_metadata_from_verified_live_rows(tmp_path: Path) -> None:
    cfg, _reset = _private_files(tmp_path, scenario="scenario_006", reset_id="reset_006_001")
    batch_dir = tmp_path / "data" / "private" / "raw_exports" / "batch_001" / "scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001"
    batch_dir.mkdir(parents=True)
    rows = batch_dir / "verified_splunk_rows.jsonl"
    rows.write_text(
        json.dumps(
            {
                "event_id": "evt_000006001",
                "relative_time_sec": "60",
                "actor_id": "actor_002",
                "actor_type": "agent_or_admin",
                "source_surface": "splunk_audit",
                "source_index_family": "audit",
                "source_sourcetype_family": "audittrail",
                "action": "search",
                "action_family": "investigation",
                "object_type": "index",
                "object_id": "object_000900",
                "object_role": "evidence_source",
                "status": "success",
                "scenario_id": "scenario_006",
                "scenario_run_id": "scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001",
                "raw_event_ref": "private_ref_006_001_001",
                "redaction_level": "public_safe",
                "source_derivation": "live_splunk_public_redacted",
                "target_evidence_overlap": "false",
                "prompt_variant_id": "operator_handoff_asset_map_v1_a",
                "prompt_family": "operator_handoff_asset_map",
                "prompt_pack_version": "nondet-v1-20260525",
                "prompt_seed": "20260525",
                "attempt_index": "1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = batch_dir / "capture"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "capture_splunk_run_v1.py"),
            "--config",
            str(cfg),
            "--scenario-run-id",
            "scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001",
            "--reset-id",
            "reset_006_001",
            "--output-dir",
            str(output_dir),
            "--require-live-splunk-rows",
            "--verified-live-rows-jsonl",
            str(rows),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    events = _jsonl(output_dir / "public_safe_events_private.jsonl")
    assert events[0]["relative_time_sec"] == 60
    assert events[0]["prompt_variant_id"] == "operator_handoff_asset_map_v1_a"
    assert events[0]["prompt_family"] == "operator_handoff_asset_map"
    assert events[0]["prompt_pack_version"] == "nondet-v1-20260525"
    assert events[0]["prompt_seed"] == 20260525
    assert events[0]["attempt_index"] == 1


def test_capture_require_live_rows_fails_closed_without_search_config(tmp_path: Path) -> None:
    cfg, _reset = _private_files(tmp_path, scenario="scenario_004", reset_id="reset_004_001")
    output_dir = tmp_path / "data" / "private" / "raw_exports" / "batch_001" / "scenario_004_run_001"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "capture_splunk_run_v1.py"),
            "--config",
            str(cfg),
            "--scenario-run-id",
            "scenario_004_run_001",
            "--reset-id",
            "reset_004_001",
            "--output-dir",
            str(output_dir),
            "--require-live-splunk-rows",
            "--earliest-epoch",
            "123",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "search config" in result.stderr


def test_capture_live_rows_write_live_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import capture_splunk_run_v1 as capture

    cfg, _reset = _private_files(tmp_path, scenario="scenario_004", reset_id="reset_004_001")
    output_dir = tmp_path / "data" / "private" / "raw_exports" / "batch_001" / "scenario_004_run_001"
    rows = [
        {
            "event_id": "evt_000004001",
            "relative_time_sec": 60,
            "actor_id": "actor_001",
            "actor_type": "agent_or_admin",
            "source_surface": "splunk_audit",
            "source_index_family": "audit",
            "source_sourcetype_family": "audittrail",
            "action": "search",
            "action_family": "investigation",
            "object_type": "index",
            "object_id": "object_000900",
            "object_role": "evidence_source",
            "status": "success",
            "scenario_id": "scenario_004",
            "scenario_run_id": "scenario_004_run_001",
            "raw_event_ref": "private_ref_004_001_001",
            "redaction_level": "public_safe",
            "source_derivation": "live_lab_public_redacted",
            "target_evidence_overlap": False,
            "private_name": "must_not_be_written",
        }
    ]
    monkeypatch.setattr(capture, "search_scenario_events", lambda **_kwargs: SimpleNamespace(rows=rows))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture_splunk_run_v1.py",
            "--config",
            str(cfg),
            "--scenario-run-id",
            "scenario_004_run_001",
            "--reset-id",
            "reset_004_001",
            "--output-dir",
            str(output_dir),
            "--require-live-splunk-rows",
            "--earliest-epoch",
            "123",
        ],
    )

    assert capture.main() == 0
    manifest = json.loads((output_dir / "capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "captured_live_splunk_public_safe"
    assert manifest["source_index"] == "openclaw_tamper_lab"
    events = _jsonl(output_dir / "public_safe_events_private.jsonl")
    assert events[0]["event_id"] == "evt_000004001"
    assert events[0]["actor_role_family"] == "unknown"
    assert events[0]["protected_evidence_seen"] is False
    assert "private_name" not in events[0]
