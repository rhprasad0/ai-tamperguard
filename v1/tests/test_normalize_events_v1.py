from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_normalize_live_capture_writes_public_events_and_metadata(tmp_path: Path) -> None:
    capture_dir = tmp_path / "data" / "private" / "raw_exports" / "batch_001" / "scenario_010_run_001"
    events = [
        {
            "event_id": "evt_000010001",
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
            "scenario_id": "scenario_010",
            "scenario_run_id": "scenario_010_run_001",
            "raw_event_ref": "private_ref_010_001_001",
            "redaction_level": "public_safe",
            "source_derivation": "live_lab_public_redacted",
            "target_evidence_overlap": False,
        },
        {
            "event_id": "evt_000010002",
            "relative_time_sec": 480,
            "actor_id": "actor_001",
            "actor_type": "agent_or_admin",
            "source_surface": "splunk_configtracker",
            "source_index_family": "configtracker",
            "source_sourcetype_family": "splunk_configuration_change",
            "action": "modify",
            "action_family": "visibility_change",
            "object_type": "dashboard",
            "object_id": "object_000010",
            "object_role": "detection_or_visibility_artifact",
            "status": "success",
            "scenario_id": "scenario_010",
            "scenario_run_id": "scenario_010_run_001",
            "raw_event_ref": "private_ref_010_001_002",
            "redaction_level": "public_safe",
            "source_derivation": "live_lab_public_redacted",
            "target_evidence_overlap": True,
        },
    ]
    _write_jsonl(capture_dir / "public_safe_events_private.jsonl", events)
    (capture_dir / "capture_manifest.json").write_text(
        json.dumps(
            {
                "scenario_run_id": "scenario_010_run_001",
                "scenario_id": "scenario_010",
                "reset_id": "reset_010_001",
                "status": "captured_private_public_safe_scaffold",
                "public_release_ready": False,
            }
        ),
        encoding="utf-8",
    )
    run_manifest = tmp_path / "data" / "private" / "run_manifests" / "batch_001" / "scenario_runs_private.jsonl"
    _write_jsonl(
        run_manifest,
        [
            {
                "scenario_run_id": "scenario_010_run_001",
                "scenario_id": "scenario_010",
                "actor_id": "actor_001",
                "environment_id": "environment_001",
                "outcome": "attempted",
                "ground_truth_family": "evidence_laundering",
                "paired_control_run_id": None,
                "private_reset_id": "reset_010_001",
                "public_reset_id": "reset_004",
            }
        ],
    )
    public_events = tmp_path / "data" / "public_sample" / "normalized" / "events.jsonl"
    private_out = tmp_path / "data" / "private" / "normalized" / "events_private.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "normalize_events_v1.py"),
            "--input",
            str(tmp_path / "data" / "private" / "raw_exports" / "batch_001"),
            "--run-manifest",
            str(run_manifest),
            "--output-private",
            str(private_out),
            "--output-public",
            str(public_events),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    public_rows = [json.loads(line) for line in public_events.read_text(encoding="utf-8").splitlines()]
    assert public_rows == events
    sample = tmp_path / "data" / "public_sample"
    scenario_runs = [json.loads(line) for line in (sample / "scenarios" / "scenario_runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert scenario_runs[0]["source_derivation"] == "live_lab_public_redacted"
    assert scenario_runs[0]["release_eligibility"] == "fixture_smoke_only"
    answer_rows = [json.loads(line) for line in (sample / "scenarios" / "answer_key_public_redacted.jsonl").read_text(encoding="utf-8").splitlines()]
    assert answer_rows[0]["label_source"] == "post_run_verification"
    assert answer_rows[0]["positive_intervals"]
    manifest = json.loads((sample / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["release_status"] == "live_lab_capture_scaffold_not_release_candidate"
