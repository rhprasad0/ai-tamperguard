from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.io import write_jsonl  # noqa: E402
from ai_tamperguard_v1.lab_config import LabConfigError, load_lab_config  # noqa: E402
from ai_tamperguard_v1.scenario_events import (  # noqa: E402
    public_safe_scenario_events,
    scenario_actor_id,
    scenario_id_from_run,
)
from ai_tamperguard_v1.splunk_io import SplunkIoError, search_scenario_events  # noqa: E402

SCHEMA_EVENT_KEYS = {
    "event_id",
    "relative_time_sec",
    "actor_id",
    "actor_type",
    "source_surface",
    "source_index_family",
    "source_sourcetype_family",
    "action",
    "action_family",
    "object_type",
    "object_id",
    "object_role",
    "status",
    "scenario_id",
    "scenario_run_id",
    "raw_event_ref",
    "redaction_level",
    "source_derivation",
    "target_evidence_overlap",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--reset-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-id")
    parser.add_argument("--earliest-epoch", type=int, default=0)
    parser.add_argument("--require-live-splunk-rows", action="store_true")
    parser.add_argument("--allow-scaffold-fallback", action="store_true")
    parser.add_argument("--verified-live-rows-jsonl", help="Private JSONL export of Splunk-verified rows, e.g. from Splunk MCP readback")
    args = parser.parse_args()

    out = _Path(args.output_dir)
    if not _is_private_capture_path(out):
        print("capture output must stay under data/private/raw_exports", file=sys.stderr)
        return 2

    try:
        config = load_lab_config(args.config)
    except LabConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    scenario_id = scenario_id_from_run(args.scenario_run_id)
    reset_path = _Path("data/private/resets") / f"{args.reset_id}.json"
    if not reset_path.exists():
        print("capture requires successful private reset manifest", file=sys.stderr)
        return 2
    reset = json.loads(reset_path.read_text(encoding="utf-8"))
    if reset.get("scenario_id") != scenario_id:
        print(f"scenario_run_id {args.scenario_run_id} does not match reset scenario {reset.get('scenario_id')}", file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)

    if args.require_live_splunk_rows:
        if args.verified_live_rows_jsonl:
            rows_path = _Path(args.verified_live_rows_jsonl)
            if not _is_private_raw_export_path(rows_path):
                print("verified live rows JSONL must stay under data/private/raw_exports", file=sys.stderr)
                return 2
            if not rows_path.exists():
                print("verified live rows JSONL does not exist", file=sys.stderr)
                return 2
            search_rows = _read_jsonl(rows_path)
        else:
            try:
                search_result = search_scenario_events(
                    config=config,
                    scenario_run_id=args.scenario_run_id,
                    earliest_epoch=args.earliest_epoch,
                )
            except SplunkIoError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            search_rows = search_result.rows
        search_rows = [row for row in search_rows if row.get("scenario_run_id") == args.scenario_run_id]
        if search_rows:
            events = [_normalize_splunk_row(row, scenario_id=scenario_id, scenario_run_id=args.scenario_run_id) for row in search_rows]
            write_jsonl(out / "public_safe_events_private.jsonl", events)
            _write_manifest(
                out=out,
                scenario_run_id=args.scenario_run_id,
                scenario_id=scenario_id,
                reset_id=args.reset_id,
                status="captured_live_splunk_public_safe",
                source_derivation="live_splunk_public_redacted",
                source_surfaces=sorted({event["source_surface"] for event in events}),
                event_count=len(events),
                target_namespace=config.target_namespace,
                source_index="openclaw_tamper_lab",
                public_release_blocker="requires review before release-candidate promotion",
                batch_id=args.batch_id,
            )
            return 0
        if not args.allow_scaffold_fallback:
            print("no live Splunk rows found for scenario_run_id", file=sys.stderr)
            return 2

    events = public_safe_scenario_events(
        scenario_id=scenario_id,
        scenario_run_id=args.scenario_run_id,
        actor_id=scenario_actor_id(scenario_id),
        artifact_ids=tuple(reset.get("sacrificial_artifact_ids", [])),
    )
    write_jsonl(out / "public_safe_events_private.jsonl", events)
    _write_manifest(
        out=out,
        scenario_run_id=args.scenario_run_id,
        scenario_id=scenario_id,
        reset_id=args.reset_id,
        status="captured_private_public_safe_scaffold",
        source_derivation="live_lab_public_redacted",
        source_surfaces=sorted({event["source_surface"] for event in events}),
        event_count=len(events),
        target_namespace=config.target_namespace,
        public_release_blocker="scenario behavior is scaffolded from reset/capture metadata until live Splunk action rows are attached",
        batch_id=args.batch_id,
    )
    return 0


def _write_manifest(
    *,
    out: _Path,
    scenario_run_id: str,
    scenario_id: str,
    reset_id: str,
    status: str,
    source_derivation: str,
    source_surfaces: list[str],
    event_count: int,
    target_namespace: str,
    public_release_blocker: str,
    batch_id: str | None = None,
    source_index: str | None = None,
) -> None:
    manifest = {
        "scenario_run_id": scenario_run_id,
        "scenario_id": scenario_id,
        "reset_id": reset_id,
        "status": status,
        "source_derivation": source_derivation,
        "source_surfaces": source_surfaces,
        "event_count": event_count,
        "target_namespace": target_namespace,
        "public_release_ready": False,
        "public_release_blocker": public_release_blocker,
    }
    if batch_id:
        manifest["batch_id"] = batch_id
    if source_index:
        manifest["source_index"] = source_index
    (out / "capture_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_splunk_row(row: dict[str, Any], *, scenario_id: str, scenario_run_id: str) -> dict[str, Any]:
    event = {key: row[key] for key in SCHEMA_EVENT_KEYS if key in row}
    event["scenario_id"] = scenario_id
    event["scenario_run_id"] = scenario_run_id
    event["redaction_level"] = "public_safe"
    event.setdefault("source_derivation", "live_lab_public_redacted")
    event.setdefault("raw_event_ref", f"private_ref_{scenario_id.rsplit('_', 1)[-1]}_splunk_{event.get('event_id', 'evt')}".lower())
    event.setdefault("target_evidence_overlap", False)
    if "relative_time_sec" in event:
        event["relative_time_sec"] = int(event["relative_time_sec"])
    return event


def _is_private_capture_path(path: _Path) -> bool:
    parts = tuple(part for part in path.as_posix().split("/") if part)
    needle = ("data", "private", "raw_exports")
    return any(parts[idx : idx + 3] == needle for idx in range(len(parts) - 2))


def _is_private_raw_export_path(path: _Path) -> bool:
    parts = tuple(part for part in path.as_posix().split("/") if part)
    needle = ("data", "private", "raw_exports")
    return any(parts[idx : idx + 3] == needle for idx in range(len(parts) - 2))


def _read_jsonl(path: _Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


# Backward-compatible aliases for older tests/imports.
_scenario_id_from_run = scenario_id_from_run
_scenario_events = public_safe_scenario_events


if __name__ == "__main__":
    raise SystemExit(main())
