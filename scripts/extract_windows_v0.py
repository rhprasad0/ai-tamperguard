#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_tamperguard.features import build_actor_windows  # noqa: E402
from ai_tamperguard.schema import validate_behavior_window  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract AI TamperGuard v0 actor behavior windows.")
    parser.add_argument("--input", required=True, type=Path, help="Private JSONL export of raw Splunk events")
    parser.add_argument("--output", required=True, type=Path, help="Private CSV output path for behavior windows")
    parser.add_argument("--salt-file", required=True, type=Path, help="Private file containing actor surrogate salt")
    parser.add_argument("--source-dataset", default="private_splunk_export_v0", help="Dataset id to record on output rows")
    parser.add_argument(
        "--window-minutes",
        default=60,
        choices=(15, 60),
        type=int,
        help="Actor window size in minutes; default: 60",
    )
    args = parser.parse_args(argv)

    salt = args.salt_file.read_text(encoding="utf-8").strip()
    if not salt:
        raise SystemExit("salt file is empty")

    events = _read_jsonl(args.input)
    windows = build_actor_windows(
        events,
        salt=salt,
        source_dataset=args.source_dataset,
        window_minutes=args.window_minutes,
    )
    for window in windows:
        public_window = {key: value for key, value in window.items() if not key.endswith("_private")}
        validate_behavior_window(public_window, public=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(windows).to_csv(args.output, index=False)
    print(f"wrote {len(windows)} actor_{args.window_minutes}m windows to {args.output}")
    return 0


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError(f"JSONL line {line_number} is not an object")
            events.append(event)
    return events


if __name__ == "__main__":
    raise SystemExit(main())
