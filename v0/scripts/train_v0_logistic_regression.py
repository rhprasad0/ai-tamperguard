#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_tamperguard.train import (  # noqa: E402
    DEFAULT_THRESHOLD,
    PRIVATE_ARTIFACT_DEFAULT,
    PRIVATE_EXPECTED_HOLDOUT_DEFAULT,
    PRIVATE_REPORT_DEFAULT,
    write_training_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train AI TamperGuard v0 local logistic-regression artifact.",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=120),
    )
    parser.add_argument("--train", required=True, type=Path, help="Private training CSV path.")
    parser.add_argument("--holdout", required=True, type=Path, help="Private held-out fixture CSV path.")
    parser.add_argument(
        "--artifact",
        default=ROOT / PRIVATE_ARTIFACT_DEFAULT,
        type=Path,
        help=f"Private model artifact output path (default: {PRIVATE_ARTIFACT_DEFAULT}).",
    )
    parser.add_argument(
        "--expected-holdout",
        default=ROOT / PRIVATE_EXPECTED_HOLDOUT_DEFAULT,
        type=Path,
        help=f"Private locally scored holdout CSV path (default: {PRIVATE_EXPECTED_HOLDOUT_DEFAULT}).",
    )
    parser.add_argument(
        "--report",
        default=ROOT / PRIVATE_REPORT_DEFAULT,
        type=Path,
        help=f"Private local diagnostics report path (default: {PRIVATE_REPORT_DEFAULT}).",
    )
    parser.add_argument("--seed", required=True, type=int, help="Pinned random seed.")
    parser.add_argument("--threshold", default=DEFAULT_THRESHOLD, type=float, help="Prediction threshold.")
    parser.add_argument("--training-git-sha", default=None, help="Override git SHA recorded in artifact.")
    args = parser.parse_args()

    result = write_training_outputs(
        train_path=args.train,
        holdout_path=args.holdout,
        artifact_path=args.artifact,
        expected_holdout_path=args.expected_holdout,
        report_path=args.report,
        seed=args.seed,
        threshold=args.threshold,
        training_git_sha=args.training_git_sha,
    )
    print(
        "wrote v0 model artifact "
        f"{args.artifact} and expected holdout {args.expected_holdout} "
        f"for model_version {result.artifact['model_version']}"
    )
    print(f"wrote diagnostics report {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
