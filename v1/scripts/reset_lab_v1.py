from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.lab_config import LabConfigError, load_lab_config, load_sacrificial_inventory  # noqa: E402

ALLOWED_SCENARIOS = {
    "scenario_004",
    "scenario_006",
    "scenario_007",
    "scenario_010",
    "scenario_011",
    "scenario_012",
    "scenario_013",
    "scenario_014",
    "scenario_015",
    "scenario_017",
    "scenario_018",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--reset-id", required=True)
    parser.add_argument("--inventory")
    args = parser.parse_args()

    if args.scenario not in ALLOWED_SCENARIOS:
        print("scenario outside V1 sacrificial allowlist", file=sys.stderr)
        return 2

    try:
        config = load_lab_config(args.config)
        inventory_path = _Path(args.inventory) if args.inventory else config.path.with_name("sacrificial_inventory.toml")
        inventory = load_sacrificial_inventory(inventory_path, expected_namespace=config.target_namespace)
    except LabConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    artifacts = [artifact for artifact in inventory.artifacts if args.scenario in artifact.scenario_ids]
    if not artifacts:
        print(f"no sacrificial artifacts configured for {args.scenario}", file=sys.stderr)
        return 2

    out = _Path("data/resets") / f"{args.reset_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "reset_id": args.reset_id,
                "scenario_id": args.scenario,
                "status": "reset_manifest_recorded",
                "relative_time_sec": 0,
                "target_namespace": config.target_namespace,
                "sacrificial_artifact_ids": [artifact.object_id for artifact in artifacts],
                "sacrificial_object_types": [artifact.object_type for artifact in artifacts],
                "preserved_evidence_surfaces": ["splunk_audit", "splunk_configtracker"],
                "public_summary": "sacrificial fixtures selected from private inventory; protected evidence preserved",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
