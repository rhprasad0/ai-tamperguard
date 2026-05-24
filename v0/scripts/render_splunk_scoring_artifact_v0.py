#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_tamperguard.render_spl import PRIVATE_SPL_DEFAULT, write_scoring_spl  # noqa: E402
from ai_tamperguard.train import PRIVATE_ARTIFACT_DEFAULT  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render deterministic AI TamperGuard v0 SPL scoring from a model artifact.")
    parser.add_argument(
        "--artifact",
        type=Path,
        default=ROOT / PRIVATE_ARTIFACT_DEFAULT,
        help=f"Path to model artifact JSON (default: {PRIVATE_ARTIFACT_DEFAULT})",
    )
    parser.add_argument(
        "--lookup",
        required=True,
        help="App-scoped CSV lookup filename to read with inputlookup, e.g. tamperguard_windows_holdout_proxy.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / PRIVATE_SPL_DEFAULT,
        help=f"Private output SPL path (default: {PRIVATE_SPL_DEFAULT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spl = write_scoring_spl(artifact_path=args.artifact, lookup_name=args.lookup, output_path=args.output)
    print(f"wrote SPL scoring artifact to {args.output} ({len(spl.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
