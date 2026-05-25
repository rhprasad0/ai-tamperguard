from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.lab_config import (  # noqa: E402
    LabConfig,
    LabConfigError,
    SacrificialInventory,
    load_lab_config,
    load_sacrificial_inventory,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--inventory")
    parser.add_argument("--observed-indexes-json")
    args = parser.parse_args()

    output = _Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        config = load_lab_config(args.config)
        inventory = _load_inventory_if_available(args.inventory, config)
        observed_indexes = _load_observed_indexes(args.observed_indexes_json)
        failures = _readiness_failures(config, inventory, observed_indexes, observed_indexes_configured=bool(args.observed_indexes_json))
    except LabConfigError as exc:
        output.write_text(_failure_report([str(exc)]), encoding="utf-8")
        print(str(exc), file=sys.stderr)
        return 2

    if failures:
        output.write_text(_failure_report(failures), encoding="utf-8")
        return 2

    output.write_text(_success_report(config, inventory, observed_indexes), encoding="utf-8")
    return 0


def _load_inventory_if_available(raw_inventory: str | None, config: LabConfig) -> SacrificialInventory | None:
    if raw_inventory:
        return load_sacrificial_inventory(raw_inventory, expected_namespace=config.target_namespace)
    candidate = config.path.with_name("sacrificial_inventory.toml")
    if candidate.exists():
        return load_sacrificial_inventory(candidate, expected_namespace=config.target_namespace)
    return None


def _load_observed_indexes(raw_path: str | None) -> dict[str, dict[str, Any]]:
    if not raw_path:
        return {}
    path = _Path(raw_path)
    if not path.exists():
        raise LabConfigError(f"missing observed index snapshot: {path}")
    parts = tuple(part for part in path.as_posix().split("/") if part)
    if not any(parts[idx : idx + 2] == ("splunk", "private") for idx in range(len(parts) - 1)):
        raise LabConfigError(f"observed index snapshot must live under splunk/private: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LabConfigError(f"invalid observed index snapshot JSON: {exc}") from exc
    rows = payload.get("results", payload if isinstance(payload, list) else [])
    if not isinstance(rows, list):
        raise LabConfigError("observed index snapshot must contain a results list")
    observed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = row.get("title") or row.get("name") or row.get("index")
        if title:
            observed[str(title)] = row
    return observed


def _readiness_failures(
    config: LabConfig,
    inventory: SacrificialInventory | None,
    observed_indexes: dict[str, dict[str, Any]],
    *,
    observed_indexes_configured: bool,
) -> list[str]:
    failures: list[str] = []
    if not observed_indexes_configured:
        failures.append("observed index snapshot is required for live V1 readiness")
    else:
        missing = [index for index in config.required_indexes if index not in observed_indexes]
        if missing:
            failures.append("missing required observed indexes: " + ", ".join(missing))
        disabled = [index for index in config.required_indexes if str(observed_indexes.get(index, {}).get("disabled", "0")) == "1"]
        if disabled:
            failures.append("required observed indexes are disabled: " + ", ".join(disabled))
    if inventory is None:
        failures.append("sacrificial inventory is required for live V1 readiness")
    elif not inventory.artifacts:
        failures.append("sacrificial inventory has no artifacts")
    return failures


def _failure_report(failures: list[str]) -> str:
    lines = ["# Splunk readiness failed", "", "Fail-closed checks blocked live V1 execution:", ""]
    lines.extend(f"- {failure}" for failure in failures)
    lines.append("")
    return "\n".join(lines)


def _success_report(
    config: LabConfig,
    inventory: SacrificialInventory | None,
    observed_indexes: dict[str, dict[str, Any]],
) -> str:
    lines = [
        "# Splunk readiness passed",
        "",
        f"- Authorized lab marker: `{config.authorized_lab_marker}`",
        f"- Target namespace: `{config.target_namespace}`",
        f"- Capture destination: `{config.capture_destination.as_posix()}`",
        "",
        "## Required observed indexes",
        "",
    ]
    for index in config.required_indexes:
        row = observed_indexes[index]
        event_count = row.get("totalEventCount", "unknown")
        lines.append(f"- `{index}`: present, disabled={row.get('disabled', 'unknown')}, totalEventCount={event_count}")
    optional_present = [index for index in config.optional_indexes if index in observed_indexes]
    if optional_present:
        lines.extend(["", "## Optional observed indexes", ""])
        lines.extend(f"- `{index}`: present" for index in optional_present)
    if inventory is not None:
        lines.extend(["", "## Sacrificial inventory", ""])
        lines.append(f"- Namespace: `{inventory.namespace}`")
        lines.append(f"- Synthetic index: `{inventory.synthetic_index}`")
        for artifact in inventory.artifacts:
            scenarios = ", ".join(artifact.scenario_ids)
            lines.append(f"- `{artifact.object_id}`: {artifact.object_type}, scenarios={scenarios}")
    lines.append("")
    lines.append("Readiness is public-safe: private artifact names and raw SPL are intentionally omitted from this report.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
