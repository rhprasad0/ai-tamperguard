from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.lab_config import (  # noqa: E402
    LabConfigError,
    load_lab_config,
    load_sacrificial_inventory,
)
from ai_tamperguard_v1.scenario_events import public_safe_scenario_events, scenario_actor_id, scenario_id_from_run  # noqa: E402
from ai_tamperguard_v1.splunk_io import SplunkIoError, write_scenario_events_hec  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--reset-id", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--anchor-epoch", required=True, type=int)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--prompt-variant-id")
    parser.add_argument("--prompt-family")
    parser.add_argument("--prompt-pack-version")
    parser.add_argument("--prompt-seed", type=int)
    parser.add_argument("--attempt-index", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if scenario_id_from_run(args.scenario_run_id) != args.scenario:
        print("scenario and scenario_run_id mismatch", file=sys.stderr)
        return 2
    out_manifest = _Path(args.output_manifest)
    if not _is_seed_manifest_path(out_manifest):
        print("seed output manifest must stay under data/seed_manifests", file=sys.stderr)
        return 2

    try:
        config = load_lab_config(args.config)
        inventory = load_sacrificial_inventory(args.inventory, expected_namespace=config.target_namespace)
    except LabConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    reset_path = _Path("data/resets") / f"{args.reset_id}.json"
    if not reset_path.exists():
        print("seed requires successful reset manifest", file=sys.stderr)
        return 2
    reset = json.loads(reset_path.read_text(encoding="utf-8"))
    if reset.get("scenario_id") != args.scenario:
        print("scenario/run/reset mismatch", file=sys.stderr)
        return 2

    artifact_ids = tuple(artifact.object_id for artifact in inventory.artifacts if args.scenario in artifact.scenario_ids)
    if not artifact_ids:
        artifact_ids = tuple(reset.get("sacrificial_artifact_ids", []))

    events = public_safe_scenario_events(
        scenario_id=args.scenario,
        scenario_run_id=args.scenario_run_id,
        actor_id=scenario_actor_id(args.scenario),
        artifact_ids=artifact_ids,
        prompt_variant_id=args.prompt_variant_id,
        prompt_family=args.prompt_family,
        prompt_pack_version=args.prompt_pack_version,
        prompt_seed=args.prompt_seed,
        attempt_index=args.attempt_index,
    )
    seeded_events = [
        dict(
            event,
            batch_id=args.batch_id,
            reset_id=args.reset_id,
            seed_anchor_epoch=args.anchor_epoch,
            seed_source="ai_tamperguard_v1_seed",
        )
        for event in events
    ]
    try:
        write_result = write_scenario_events_hec(config=config, events=seeded_events, batch_id=args.batch_id, dry_run=args.dry_run)
    except SplunkIoError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": "dry_run_validated" if args.dry_run else "seeded_splunk_hec",
        "write_status": write_result.status,
        "scenario_id": args.scenario,
        "scenario_run_id": args.scenario_run_id,
        "reset_id": args.reset_id,
        "batch_id": args.batch_id,
        "seed_anchor_epoch": args.anchor_epoch,
        "event_count": len(seeded_events),
        "event_ids": [event["event_id"] for event in seeded_events],
        "artifact_ids": list(artifact_ids),
        "target_index": "openclaw_tamper_lab",
        "public_release_ready": False,
    }
    if args.prompt_variant_id is not None:
        manifest["prompt_variant_id"] = args.prompt_variant_id
    if args.prompt_family is not None:
        manifest["prompt_family"] = args.prompt_family
    if args.prompt_pack_version is not None:
        manifest["prompt_pack_version"] = args.prompt_pack_version
    if args.prompt_seed is not None:
        manifest["prompt_seed"] = args.prompt_seed
    if args.attempt_index is not None:
        manifest["attempt_index"] = args.attempt_index
    out_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def _is_seed_manifest_path(path: _Path) -> bool:
    cwd = _Path.cwd().resolve()
    try:
        relative = path.resolve().relative_to(cwd)
    except ValueError:
        return False
    parts = tuple(part for part in relative.as_posix().split("/") if part)
    needle = ("data", "seed_manifests")
    return parts[:2] == needle and len(parts) > 2


if __name__ == "__main__":
    raise SystemExit(main())
