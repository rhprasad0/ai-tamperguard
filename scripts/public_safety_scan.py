#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_tamperguard.public_safety import scan_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan public AI TamperGuard artifacts for v0 safety leaks.")
    parser.add_argument("paths", nargs="+", help="Explicit file or directory paths to scan")
    args = parser.parse_args(argv)

    findings = scan_paths(args.paths)
    for finding in findings:
        print(f"{finding.path}: {finding.reason}", file=sys.stderr)

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
