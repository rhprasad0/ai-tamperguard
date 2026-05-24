#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_tamperguard.split import SplitError, write_split  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create deterministic AI TamperGuard v0 train/holdout splits.")
    parser.add_argument("--input", required=True, type=Path, help="Private behavior-window CSV input")
    parser.add_argument("--train-output", required=True, type=Path, help="Private train CSV output path")
    parser.add_argument("--holdout-output", required=True, type=Path, help="Private holdout CSV output path")
    parser.add_argument("--manifest-output", required=True, type=Path, help="Private split manifest JSON output path")
    parser.add_argument("--seed", required=True, type=int, help="Pinned deterministic split seed")
    parser.add_argument("--holdout-fraction", default=0.2, type=float, help="Per-class holdout fraction; default: 0.2")
    args = parser.parse_args(argv)

    try:
        manifest = write_split(
            input_path=args.input,
            train_output_path=args.train_output,
            holdout_output_path=args.holdout_output,
            manifest_output_path=args.manifest_output,
            seed=args.seed,
            holdout_fraction=args.holdout_fraction,
        )
    except SplitError as exc:
        raise SystemExit(f"split failed: {exc}") from exc

    counts = manifest["counts"]
    print(
        "wrote "
        f"{counts['train_total']} train rows and {counts['holdout_total']} holdout rows "
        f"to {args.train_output} and {args.holdout_output}; manifest {args.manifest_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
