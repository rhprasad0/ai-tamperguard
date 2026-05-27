from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "raw_harness_jsonl_to_training_csv_v1.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _event(
    *,
    event_id: str,
    scenario_run_id: str,
    relative_time_sec: int,
    action: str,
    action_family: str,
    object_type: str,
    object_id: str,
    object_role: str = "evidence_source",
    status: str = "success",
    actor_id: str = "actor_001",
    source_surface: str = "splunk_audit",
    source_index_family: str = "audit",
    source_sourcetype_family: str = "audittrail",
    source_derivation: str = "live_splunk_public_redacted",
    **extra: object,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "scenario_run_id": scenario_run_id,
        "scenario_id": scenario_run_id.removesuffix("_run_001"),
        "relative_time_sec": relative_time_sec,
        "actor_id": actor_id,
        "actor_type": "agent_or_admin",
        "source_surface": source_surface,
        "source_index_family": source_index_family,
        "source_sourcetype_family": source_sourcetype_family,
        "action": action,
        "action_family": action_family,
        "object_type": object_type,
        "object_id": object_id,
        "object_role": object_role,
        "status": status,
        "raw_event_ref": f"private_ref_{event_id}",
        "redaction_level": "public_safe",
        "source_derivation": source_derivation,
        "target_evidence_overlap": False,
        **extra,
    }


def _write_training_fixture(tmp_path: Path) -> tuple[Path, Path]:
    batch = tmp_path / "data" / "raw_exports" / "batch_001"
    _write_jsonl(
        batch / "scenario_010_run_001" / "public_safe_events.jsonl",
        [
            _event(
                event_id="evt_000010001",
                scenario_run_id="scenario_010_run_001",
                relative_time_sec=60,
                action="search",
                action_family="investigation",
                object_type="index",
                object_id="object_000900",
                protected_evidence_seen=True,
                evidence_chain_stage="search",
            ),
            _event(
                event_id="evt_000010002",
                scenario_run_id="scenario_010_run_001",
                relative_time_sec=120,
                action="modify",
                action_family="visibility_change",
                object_type="dashboard",
                object_id="object_000010",
                object_role="detection_or_visibility_artifact",
                source_surface="splunk_configtracker",
                source_index_family="configtracker",
                source_sourcetype_family="splunk_configuration_change",
                actor_role_family="admin",
                actor_capability_family="edit_dashboards",
                capability_check_result="allowed",
                object_criticality="high",
                object_visibility_scope="global",
                detection_lifecycle_stage="throttled",
                visibility_delta="decrease",
                change_magnitude_bucket="medium",
                before_state_family="broad",
                after_state_family="narrow",
                evidence_chain_stage="change_visibility_object",
                target_evidence_overlap=True,
            ),
            _event(
                event_id="evt_000010003",
                scenario_run_id="scenario_010_run_001",
                relative_time_sec=240,
                action="write_report",
                action_family="reporting_change",
                object_type="report",
                object_id="object_000011",
                object_role="reporting_artifact",
                downstream_artifact_updated=True,
                downstream_artifact_matches_evidence="omits_relevant_evidence",
                evidence_chain_stage="write_report",
                target_evidence_overlap=True,
            ),
        ],
    )
    _write_jsonl(
        batch / "scenario_004_run_001" / "public_safe_events.jsonl",
        [
            _event(
                event_id="evt_000004001",
                scenario_run_id="scenario_004_run_001",
                relative_time_sec=60,
                action="search",
                action_family="investigation",
                object_type="index",
                object_id="object_000901",
                actor_id="actor_002",
                evidence_chain_stage="search",
            ),
            _event(
                event_id="evt_000004002",
                scenario_run_id="scenario_004_run_001",
                relative_time_sec=180,
                action="write_report",
                action_family="reporting_change",
                object_type="report",
                object_id="object_000902",
                object_role="reporting_artifact",
                actor_id="actor_002",
                downstream_artifact_updated=True,
                downstream_artifact_matches_evidence="matches",
                evidence_chain_stage="write_report",
            ),
        ],
    )
    answer_key = tmp_path / "data" / "private" / "answer_key.jsonl"
    _write_jsonl(
        answer_key,
        [
            {
                "scenario_run_id": "scenario_010_run_001",
                "label_family": "evidence_laundering",
                "label_source": "scenario_answer_key",
                "reset_id": "reset_010",
            },
            {
                "scenario_run_id": "scenario_004_run_001",
                "label_family": "benign_investigation",
                "label_source": "scenario_answer_key",
                "reset_id": "reset_004",
            },
        ],
    )
    return batch, answer_key


def test_converts_raw_export_batch_to_training_csv(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output), "--window-size-sec", "900")

    assert result.returncode == 0, result.stderr
    rows = _read_csv(output)
    assert len(rows) == 2
    assert {row["window_type"] for row in rows} == {"actor_15m"}
    assert {row["source_batch_id"] for row in rows} == {"batch_001"}
    by_run = {row["scenario_run_id"]: row for row in rows}
    positive = by_run["scenario_010_run_001"]
    assert positive["reset_id"] == "reset_010"
    assert positive["label_binary"] == "1"
    assert positive["feature_visibility_decrease_count"] == "1"
    assert positive["feature_downstream_omission_count"] == "1"
    assert positive["feature_search_modify_report_sequence_flag"] == "1"
    control = by_run["scenario_004_run_001"]
    assert control["reset_id"] == "reset_004"
    assert control["label_binary"] == "0"
    assert control["feature_visibility_decrease_count"] == "0"


def test_requires_labels_by_default(tmp_path: Path) -> None:
    batch, _answer_key = _write_training_fixture(tmp_path)
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--output", str(output))

    assert result.returncode == 2
    assert "labels are required" in result.stderr
    assert not output.exists()


def test_rejects_invalid_event_schema(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    first_event_path = batch / "scenario_010_run_001" / "public_safe_events.jsonl"
    row = json.loads(first_event_path.read_text(encoding="utf-8").splitlines()[0])
    row["source_derivation"] = "private_raw_unredacted"
    _write_jsonl(first_event_path, [row])
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output))

    assert result.returncode != 0
    assert "schema" in result.stderr.lower() or "failed normalized_event_v1" in result.stderr
    assert not output.exists()


def test_can_build_labels_from_private_run_manifest(tmp_path: Path) -> None:
    batch, _answer_key = _write_training_fixture(tmp_path)
    run_manifest = tmp_path / "data" / "run_manifests" / "batch_001" / "scenario_runs.jsonl"
    _write_jsonl(
        run_manifest,
        [
            {"scenario_run_id": "scenario_010_run_001", "ground_truth_family": "evidence_laundering", "outcome": "successful_synthetic"},
            {"scenario_run_id": "scenario_004_run_001", "ground_truth_family": "benign_investigation", "outcome": "benign"},
        ],
    )
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--run-manifest", str(run_manifest), "--output", str(output))

    assert result.returncode == 0, result.stderr
    rows = _read_csv(output)
    assert {row["label_source"] for row in rows} == {"post_run_verification"}
    assert {row["label_binary"] for row in rows} == {"0", "1"}
    assert {row["outcome"] for row in rows} == {"benign", "successful_synthetic"}
    assert {row["label_confidence"] for row in rows} == {"1.0"}


def test_can_build_training_csv_from_opaque_run_ids(tmp_path: Path) -> None:
    batch = tmp_path / "data" / "raw_exports" / "batch_001"
    run_id = "run_0123456789abcdef"
    _write_jsonl(
        batch / run_id / "public_safe_events.jsonl",
        [
            _event(
                event_id="evt_000010001",
                scenario_run_id=run_id,
                scenario_id="scenario_010",
                relative_time_sec=60,
                action="search",
                action_family="investigation",
                object_type="index",
                object_id="object_000900",
                protected_evidence_seen=True,
                evidence_chain_stage="search",
            )
        ],
    )
    run_manifest = tmp_path / "data" / "run_manifests" / "batch_001" / "scenario_runs.jsonl"
    _write_jsonl(run_manifest, [{"scenario_run_id": run_id, "ground_truth_family": "evidence_laundering"}])
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--run-manifest", str(run_manifest), "--output", str(output))

    assert result.returncode == 0, result.stderr
    rows = _read_csv(output)
    assert len(rows) == 1
    assert rows[0]["scenario_run_id"] == run_id
    assert rows[0]["label_family"] == "evidence_laundering"


def test_training_csv_boundary_strips_manifest_and_source_audit_columns(tmp_path: Path) -> None:
    batch, _answer_key = _write_training_fixture(tmp_path)
    run_manifest = tmp_path / "data" / "run_manifests" / "batch_001" / "scenario_runs.jsonl"
    _write_jsonl(
        run_manifest,
        [
            {
                "scenario_run_id": "scenario_010_run_001",
                "ground_truth_family": "evidence_laundering",
                "path_type": "successful_synthetic",
                "prompt_variant_id": "operator_handoff_asset_map_v1_a",
                "actor_prompt_path": "data/run_manifests/batch_001/actor_prompts/run.txt",
                "synthetic_case_id": "case_0123456789abcdef",
            },
            {
                "scenario_run_id": "scenario_004_run_001",
                "ground_truth_family": "benign_investigation",
                "path_type": "benign_control",
                "prompt_variant_id": "uncertain_soc_analyst_v1_a",
                "actor_prompt_path": "data/run_manifests/batch_001/actor_prompts/run2.txt",
                "synthetic_case_id": "case_fedcba9876543210",
            },
        ],
    )
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(
        tmp_path,
        "--input",
        str(batch),
        "--run-manifest",
        str(run_manifest),
        "--output",
        str(output),
        "--add-source-batch-column",
    )

    assert result.returncode == 0, result.stderr
    rows = _read_csv(output)
    forbidden = {
        "scenario_id",
        "path_type",
        "prompt_variant_id",
        "actor_prompt_path",
        "synthetic_case_id",
        "source_input_path_count",
    }
    assert rows
    assert rows[0]["source_batch_id"] == "batch_001"
    assert forbidden.isdisjoint(rows[0])
    assert all(key.startswith("feature_") or key in {
        "window_id",
        "scenario_run_id",
        "reset_id",
        "actor_id",
        "window_type",
        "window_start_relative_sec",
        "window_end_relative_sec",
        "label_binary",
        "label_family",
        "label_source",
        "label_confidence",
        "outcome",
        "split_id",
        "source_batch_id",
    } for key in rows[0])


def test_allow_unlabeled_emits_background_labels_with_warning(tmp_path: Path) -> None:
    batch, _answer_key = _write_training_fixture(tmp_path)
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--output", str(output), "--allow-unlabeled")

    assert result.returncode == 0, result.stderr
    assert "WARNING: emitting unlabeled debug training CSV" in result.stderr
    rows = _read_csv(output)
    assert {row["label_binary"] for row in rows} == {"0"}
    assert {row["label_family"] for row in rows} == {"background_unlabeled"}
    assert {row["label_source"] for row in rows} == {"background_unlabeled"}


def test_rejects_duplicate_scenario_run_ids_across_batches_by_default(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    second_batch = tmp_path / "data" / "raw_exports" / "batch_002"
    source = batch / "scenario_010_run_001" / "public_safe_events.jsonl"
    dest = second_batch / "scenario_010_run_001" / "public_safe_events.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    output = tmp_path / "data" / "training" / "combined" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--input", str(second_batch), "--answer-key", str(answer_key), "--output", str(output))

    assert result.returncode == 2
    assert "duplicate scenario_run_id across batches" in result.stderr
    assert not output.exists()


def test_missing_label_for_input_run_fails_closed(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    _write_jsonl(answer_key, [{"scenario_run_id": "scenario_004_run_001", "label_family": "benign_investigation"}])
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output))

    assert result.returncode == 2
    assert "labels missing for scenario_run_id" in result.stderr
    assert "scenario_010_run_001" in result.stderr
    assert not output.exists()


def test_answer_key_without_label_source_defaults_to_schema_allowed_source(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    _write_jsonl(
        answer_key,
        [
            {"scenario_run_id": "scenario_010_run_001", "label_family": "evidence_laundering"},
            {"scenario_run_id": "scenario_004_run_001", "label_family": "benign_investigation"},
        ],
    )
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output))

    assert result.returncode == 0, result.stderr
    assert {row["label_source"] for row in _read_csv(output)} == {"scenario_answer_key"}


def test_duplicate_label_rows_fail_closed(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    _write_jsonl(
        answer_key,
        [
            {"scenario_run_id": "scenario_010_run_001", "label_family": "evidence_laundering"},
            {"scenario_run_id": "scenario_010_run_001", "label_family": "benign_investigation"},
            {"scenario_run_id": "scenario_004_run_001", "label_family": "benign_investigation"},
        ],
    )
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output))

    assert result.returncode == 2
    assert "duplicate label rows" in result.stderr
    assert not output.exists()


def test_rejects_public_output_path_by_default(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    output = tmp_path / "data" / "public_sample" / "training" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output))

    assert result.returncode == 2
    assert "output must stay under data/training" in result.stderr
    assert not output.exists()


def test_rejects_non_positive_window_size_cleanly(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output), "--window-size-sec", "0")

    assert result.returncode == 2
    assert "--window-size-sec must be positive" in result.stderr
    assert not output.exists()


def test_rejects_traversal_out_of_training(tmp_path: Path) -> None:
    batch, answer_key = _write_training_fixture(tmp_path)
    output = tmp_path / "data" / "training" / ".." / ".." / "public_sample" / "leak.csv"

    result = _run(tmp_path, "--input", str(batch), "--answer-key", str(answer_key), "--output", str(output))

    assert result.returncode == 2
    assert "output must stay under data/training" in result.stderr
    assert not (tmp_path / "data" / "public_sample" / "leak.csv").exists()


def test_run_manifest_requires_ground_truth_family_by_default(tmp_path: Path) -> None:
    batch, _answer_key = _write_training_fixture(tmp_path)
    run_manifest = tmp_path / "data" / "run_manifests" / "batch_001" / "scenario_runs.jsonl"
    _write_jsonl(
        run_manifest,
        [
            {"scenario_run_id": "scenario_010_run_001", "ground_truth_family": "evidence_laundering"},
            {"scenario_run_id": "scenario_004_run_001"},
        ],
    )
    output = tmp_path / "data" / "training" / "batch_001" / "windows_actor_15m.csv"

    result = _run(tmp_path, "--input", str(batch), "--run-manifest", str(run_manifest), "--output", str(output))

    assert result.returncode == 2
    assert "ground_truth_family is required" in result.stderr
    assert "scenario_004_run_001" in result.stderr
    assert not output.exists()
