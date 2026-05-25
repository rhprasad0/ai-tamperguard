from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_analyzer_cli_reads_baseline_and_writes_public_report() -> None:
    v1_root = Path(__file__).resolve().parents[1]
    output = v1_root / "reports" / "goal_runs" / "pytest_baseline_analysis" / "goal-baseline-analysis.json"
    if output.exists():
        output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_nondeterminism_goal_v1.py",
            "--summary",
            "reports/goal_runs/live_goal_nondet50_20260525T214956Z/goal-summary.json",
            "--target-group-rate",
            "0.50",
            "--target-scenario-rate",
            "0.50",
            "--output",
            str(output.relative_to(v1_root)),
        ],
        cwd=v1_root,
        text=True,
        capture_output=True,
        check=False,
    )

    try:
        assert result.returncode == 0, result.stderr
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["batch_id"] == "live_goal_nondet50_20260525T214956Z"
        assert report["group_count"] == 4
        assert report["nondet_group_count"] == 4
        assert report["group_nondet_rate"] == 1.0
        assert report["acceptance"]["status"] == "accepted"
        assert str(output.relative_to(v1_root)).startswith("reports/goal_runs/")
    finally:
        if output.exists():
            output.unlink()
        if output.parent.exists() and not any(output.parent.iterdir()):
            output.parent.rmdir()
