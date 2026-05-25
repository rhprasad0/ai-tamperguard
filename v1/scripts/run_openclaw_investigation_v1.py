#!/usr/bin/env python3
"""Run the copied Openclaw agent runner from the AI TamperGuard v1 workspace.

Default mode is an offline no-network smoke runner, matching the copied
policy-bonfire-2 CLI defaults. Use --live-full-lan only for an authorized lab run;
it requires AI_SOC_LIVE_TESTS=1 and keeps Graphiti writes disabled unless explicitly
requested.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

V1_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = V1_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from openclaw_ai_soc.cli import default_offline_services, format_hermes_summary  # noqa: E402
from openclaw_ai_soc.config import OpenclawSettings, load_config  # noqa: E402
from openclaw_ai_soc.graph import run_investigation  # noqa: E402
from openclaw_ai_soc.live_smoke import LIVE_TEST_ENV_VAR, live_tests_enabled  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_openclaw_investigation_v1")
    parser.add_argument("--payload", required=True, help="JSON trigger payload under v1/")
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional private env file for live settings. Omit for safe defaults.",
    )
    parser.add_argument(
        "--live-full-lan",
        action="store_true",
        help=(
            "Use live Splunk/Graphiti/model services. Requires "
            f"{LIVE_TEST_ENV_VAR}=1. Graphiti writes remain disabled by default."
        ),
    )
    parser.add_argument(
        "--graphiti-write",
        action="store_true",
        help="Allow Graphiti case-law writes in --live-full-lan mode.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="LLM temperature for --live-full-lan mode.",
    )
    args = parser.parse_args(argv)

    payload = _resolve_payload(Path(args.payload))
    settings = load_config(env_file=args.env_file) if args.env_file else OpenclawSettings()
    counters: dict[str, int] = {
        "splunk": 0,
        "graphiti_lookup": 0,
        "graphiti_write": 0,
        "llm": 0,
        "notifier": 0,
    }

    if args.live_full_lan:
        if not live_tests_enabled():
            print(f"live LAN mode requires {LIVE_TEST_ENV_VAR}=1", file=sys.stderr)
            return 2
        from openclaw_ai_soc.evals.live_services import build_live_full_lan_services

        services = build_live_full_lan_services(
            settings=settings,
            counters=counters,
            graphiti_write=args.graphiti_write,
            temperature=args.temperature,
        )
    else:
        services = default_offline_services()

    state = run_investigation(payload, settings=settings, services=services)
    print(format_hermes_summary(state))
    if args.live_full_lan:
        print("Live service call counters:")
        print(json.dumps(counters, indent=2, sort_keys=True))
    return 0 if state.get("investigation_status") in {"completed", "failed"} else 1


def _resolve_payload(path: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (V1_ROOT / path).resolve()
    if resolved.suffix.lower() != ".json":
        raise ValueError("payload must be a JSON file")
    try:
        resolved.relative_to(V1_ROOT)
    except ValueError as exc:
        raise ValueError("payload must live inside v1/") from exc
    return resolved


if __name__ == "__main__":
    raise SystemExit(main())
