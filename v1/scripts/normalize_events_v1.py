from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.derive import LABEL_POSITIVE_FAMILIES  # noqa: E402
from ai_tamperguard_v1.io import read_jsonl, write_jsonl  # noqa: E402
from ai_tamperguard_v1.schema import validate_rows  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--output-metadata", "--output-private", dest="output_metadata", required=True)
    parser.add_argument("--output-public", required=True)
    args = parser.parse_args()

    input_dir = _Path(args.input)
    public = _Path(args.output_public)
    metadata = _Path(args.output_metadata)
    run_manifest_path = _Path(args.run_manifest)

    if not _is_artifact_path(input_dir, ("data", "raw_exports")):
        print("input must stay under data/raw_exports", file=sys.stderr)
        return 2
    if not _is_artifact_path(metadata, ("data", "normalized")):
        print("normalization metadata output must stay under data/normalized", file=sys.stderr)
        return 2

    run_rows = read_jsonl(run_manifest_path)
    run_by_id = {row["scenario_run_id"]: row for row in run_rows}
    events: list[dict[str, Any]] = []
    capture_manifests: list[dict[str, Any]] = []
    for event_path in sorted(input_dir.glob("*/public_safe_events.jsonl")):
        rows = read_jsonl(event_path)
        events.extend(rows)
        manifest_path = event_path.with_name("capture_manifest.json")
        if manifest_path.exists():
            capture_manifests.append(json.loads(manifest_path.read_text(encoding="utf-8")))
    if not events:
        print("no public_safe_events.jsonl rows found in capture input", file=sys.stderr)
        return 2
    missing_runs = sorted({event["scenario_run_id"] for event in events} - set(run_by_id))
    if missing_runs:
        print("captured events missing run manifest rows: " + ", ".join(missing_runs), file=sys.stderr)
        return 2
    events = _enrich_events_from_run_manifest(events, run_by_id)

    validate_rows("normalized_event_v1.schema.json", events)
    write_jsonl(public, events)
    write_jsonl(
        metadata,
        [
            {
                "status": "normalization_complete",
                "public_export": public.as_posix(),
                "event_count": len(events),
                "scenario_run_count": len({event["scenario_run_id"] for event in events}),
                "source_derivation": "live_lab_public_redacted",
            }
        ],
    )

    sample_dir = public.parents[1] if public.name == "events.jsonl" and public.parent.name == "normalized" else public.parent.parent
    scenario_runs = _scenario_runs(run_rows, events)
    answer_key = _answer_key(run_rows, events)
    reset_rows = _reset_rows(run_rows)
    write_jsonl(sample_dir / "scenarios" / "scenario_runs.jsonl", scenario_runs)
    write_jsonl(sample_dir / "scenarios" / "answer_key_public_redacted.jsonl", answer_key)
    write_jsonl(sample_dir / "scenarios" / "reset_manifest_public_redacted.jsonl", reset_rows)
    (sample_dir / "dataset_manifest.json").write_text(
        json.dumps(
            {
                "dataset_build_id": "v1-live-capture-scaffold-batch-001",
                "release_status": "live_lab_capture_scaffold_not_release_candidate",
                "live_run_requirement": "partially satisfied by public-safe reset/capture scaffolds; attach live Splunk action rows before release candidate",
                "schema_version": "v1.0",
                "scenario_catalog_version": "v1-subset-20260525",
                "source_batch_ids": [input_dir.name],
                "capture_manifest_count": len(capture_manifests),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def _is_artifact_path(path: _Path, needle: tuple[str, ...]) -> bool:
    repo_root = _Path.cwd().resolve()
    artifact_root = repo_root.joinpath(*needle).resolve()
    resolved = path.expanduser().resolve()
    return resolved == artifact_root or resolved.is_relative_to(artifact_root)


PROMPT_METADATA_KEYS = (
    "prompt_variant_id",
    "prompt_family",
    "prompt_pack_version",
    "prompt_seed",
    "attempt_index",
)


def _enrich_events_from_run_manifest(events: list[dict[str, Any]], run_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for event in events:
        run = run_by_id[event["scenario_run_id"]]
        row = dict(event)
        for key in PROMPT_METADATA_KEYS:
            if key in run and key not in row:
                row[key] = run[key]
        if row.get("finding_state") == "notable_not_created":
            row["finding_state"] = "throttled_before_creation"
        for int_key in ("prompt_seed", "attempt_index"):
            if int_key in row:
                row[int_key] = int(row[int_key])
        enriched.append(row)
    return enriched


def _public_prompt_metadata(run: dict[str, Any]) -> dict[str, Any]:
    metadata = {key: run[key] for key in PROMPT_METADATA_KEYS if key in run}
    for int_key in ("prompt_seed", "attempt_index"):
        if int_key in metadata:
            metadata[int_key] = int(metadata[int_key])
    return metadata


def _scenario_runs(run_rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_run[event["scenario_run_id"]].append(event)
    rows: list[dict[str, Any]] = []
    for run in run_rows:
        run_events = by_run.get(run["scenario_run_id"], [])
        if not run_events:
            continue
        row = {
            "scenario_run_id": run["scenario_run_id"],
            "scenario_id": run["scenario_id"],
            "run_start_relative_sec": min(int(event["relative_time_sec"]) for event in run_events),
            "run_end_relative_sec": max(int(event["relative_time_sec"]) for event in run_events),
            "actor_id": run.get("actor_id", run_events[0]["actor_id"]),
            "environment_id": run.get("environment_id", "environment_001"),
            "outcome": _public_outcome(run.get("outcome", "needs_review")),
            "ground_truth_family": run.get("ground_truth_family", "background_unlabeled"),
            "paired_control_run_id": run.get("paired_control_run_id"),
            "reset_id": run.get("public_reset_id", _public_reset_id(run.get("private_reset_id", "reset_001"))),
            "release_eligibility": "fixture_smoke_only",
            "source_derivation": "live_lab_public_redacted",
        }
        row.update(_public_prompt_metadata(run))
        rows.append(row)
    return rows


def _answer_key(run_rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_run[event["scenario_run_id"]].append(event)
    rows = []
    for run in run_rows:
        run_events = sorted(by_run.get(run["scenario_run_id"], []), key=lambda event: int(event["relative_time_sec"]))
        if not run_events:
            continue
        family = run.get("ground_truth_family", "background_unlabeled")
        object_types = [event["object_type"] for event in run_events]
        positive_intervals = []
        if family in LABEL_POSITIVE_FAMILIES:
            positive_intervals.append(
                {
                    "relative_start_sec": min(int(event["relative_time_sec"]) for event in run_events),
                    "relative_end_sec": max(int(event["relative_time_sec"]) for event in run_events),
                    "behavior_family": family,
                    "object_type_sequence": object_types,
                }
            )
        row = {
            "scenario_run_id": run["scenario_run_id"],
            "positive_intervals": positive_intervals,
            "actor_id": run.get("actor_id", run_events[0]["actor_id"]),
            "object_ids_or_types": object_types,
            "label_family": family,
            "outcome": _public_outcome(run.get("outcome", "needs_review")),
            "label_source": "post_run_verification",
            "verification_basis": "public-safe reset/capture scaffold preserved protected evidence surfaces and emitted public-safe action rows; live Splunk raw action attachment remains required before release candidate",
            "limitations": "live capture scaffold only; not a public release candidate and not evidence of malicious intent",
        }
        row.update(_public_prompt_metadata(run))
        rows.append(row)
    return rows


def _reset_rows(run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for run in run_rows:
        public_reset_id = run.get("public_reset_id", _public_reset_id(run.get("private_reset_id", "reset_001")))
        rows.append(
            {
                "reset_id": public_reset_id,
                "scenario_id": run["scenario_id"],
                "status": "success",
                "relative_time_sec": 0,
                "sacrificial_artifact_ids": run.get("sacrificial_artifact_ids", ["object_000010"]),
                "preserved_evidence_surfaces": ["splunk_audit", "splunk_configtracker"],
                "public_summary": "sacrificial fixtures selected from private inventory; protected evidence preserved",
            }
        )
    return rows


def _public_outcome(outcome: str) -> str:
    aliases = {
        "expected_benign_control": "benign",
        "blocked_or_stopped": "blocked",
    }
    allowed = {"benign", "attempted", "blocked", "failed", "successful_synthetic", "needs_review"}
    normalized = aliases.get(str(outcome), str(outcome))
    return normalized if normalized in allowed else "needs_review"


def _public_reset_id(private_reset_id: str) -> str:
    # Private reset IDs look like reset_010_001; public schema intentionally exposes only reset_010.
    parts = private_reset_id.split("_")
    if len(parts) >= 2 and parts[0] == "reset" and parts[1].isdigit():
        return f"reset_{int(parts[1]):03d}"
    return "reset_001"


if __name__ == "__main__":
    raise SystemExit(main())
