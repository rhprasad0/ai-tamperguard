from __future__ import annotations

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse
import sys
from ai_tamperguard_v1.safety import scan_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan V1 public artifacts for private markers and overclaims.")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    findings = scan_paths(args.paths)
    for finding in findings:
        print(f"{finding.path}: {finding.reason}", file=sys.stderr)
    return 1 if findings else 0

if __name__ == "__main__":
    raise SystemExit(main())
