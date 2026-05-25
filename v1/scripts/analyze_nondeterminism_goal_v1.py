from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.nondeterminism_goal import acceptance_status, load_existing_summary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze AI TamperGuard k=3 nondeterminism goal status.")
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--target-group-rate", required=True, type=float)
    parser.add_argument("--target-scenario-rate", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _normalize_report_path(path: Path) -> Path:
    cwd = Path.cwd().resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(cwd)
    except ValueError as exc:
        raise SystemExit("--output must be relative to the v1 project root") from exc
    if relative.parts[:2] != ("reports", "goal_runs") or len(relative.parts) < 3:
        raise SystemExit("--output must be under reports/goal_runs")
    return relative


def main() -> int:
    args = parse_args()
    baseline = load_existing_summary(args.summary)
    output = _normalize_report_path(args.output)
    report = baseline.to_dict()
    report["acceptance"] = acceptance_status(
        baseline,
        target_group_rate=args.target_group_rate,
        target_scenario_rate=args.target_scenario_rate,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": output.as_posix(), "acceptance": report["acceptance"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
