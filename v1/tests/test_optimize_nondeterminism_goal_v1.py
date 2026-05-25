from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from ai_tamperguard_v1.prompt_pack import load_prompt_pack


def run_optimizer(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/optimize_nondeterminism_goal_v1.py", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dry_run_writes_public_tracked_candidate_results_without_splunk(tmp_path: Path) -> None:
    v1_root = Path(__file__).resolve().parents[1]
    goal_batch = "pytest_goal_nondet50"
    report_dir = v1_root / "reports" / "goal_runs" / goal_batch
    generated_dir = v1_root / "scenarios" / "generated" / goal_batch
    for root in (report_dir, generated_dir):
        if root.exists():
            for child in sorted(root.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            root.rmdir()

    result = run_optimizer(
        "--goal",
        "nondet50",
        "--goal-batch",
        goal_batch,
        "--config",
        "config/nondeterminism_goal_defaults.yaml",
        "--baseline-report",
        "reports/private/full_live_v1_k3_fixed_20260525T204429Z/nondeterminism-summary.json",
        "--k",
        "3",
        "--target-group-rate",
        "0.50",
        "--target-scenario-rate",
        "0.50",
        "--max-rounds",
        "1",
        "--candidates-per-round",
        "2",
        "--mode",
        "dry-run",
        "--no-openclaw-grading",
        "--force",
        cwd=v1_root,
    )

    try:
        assert result.returncode == 0, result.stderr
        assert "Splunk" not in result.stderr
        candidate_results = report_dir / "candidate-results.jsonl"
        summary_path = report_dir / "goal-summary.json"
        assert candidate_results.exists()
        assert summary_path.exists()
        assert generated_dir.is_dir()
        assert not (v1_root / "data" / "private" / "goal_runs" / goal_batch).exists()

        rows = [json.loads(line) for line in candidate_results.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert all(row["mode"] == "dry-run" for row in rows)
        assert all(row["artifact_paths"]["generated_prompt_pack"].startswith("scenarios/generated/") for row in rows)
        for row in rows:
            generated_prompt_pack = v1_root / row["artifact_paths"]["generated_prompt_pack"]
            assert load_prompt_pack(generated_prompt_pack)
            assert (generated_prompt_pack.parent / "candidate-config.json").exists()
        assert all(row["artifact_paths"]["report_dir"].startswith("reports/goal_runs/") for row in rows)
        assert any(row["acceptance"]["status"] in {"accepted", "rejected"} for row in rows)

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["goal"] == "nondet50"
        assert summary["mode"] == "dry-run"
        assert summary["baseline"]["batch_id"] == "full_live_v1_k3_fixed_20260525T204429Z"
        assert summary["baseline"]["acceptance"]["status"] == "rejected"
    finally:
        for root in (report_dir, generated_dir):
            if root.exists():
                for child in sorted(root.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                root.rmdir()


def test_optimizer_refuses_live_without_live_row_gate() -> None:
    v1_root = Path(__file__).resolve().parents[1]
    result = run_optimizer(
        "--goal",
        "nondet50",
        "--config",
        "config/nondeterminism_goal_defaults.yaml",
        "--mode",
        "live-splunk",
        "--no-openclaw-grading",
        cwd=v1_root,
    )

    assert result.returncode != 0
    assert "--require-live-splunk-rows" in result.stderr


def test_optimizer_requires_no_openclaw_grading_flag() -> None:
    v1_root = Path(__file__).resolve().parents[1]
    result = run_optimizer(
        "--goal",
        "nondet50",
        "--config",
        "config/nondeterminism_goal_defaults.yaml",
        "--mode",
        "dry-run",
        cwd=v1_root,
    )

    assert result.returncode != 0
    assert "--no-openclaw-grading" in result.stderr
