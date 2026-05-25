"""Tests for the AI TamperGuard project-local Openclaw runner wrapper."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

V1_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = "tests/fixtures/triggers/telemetry_disable_canary.json"
RUNNER = V1_ROOT / "scripts" / "run_openclaw_investigation_v1.py"


def test_project_local_openclaw_runner_offline_smoke() -> None:
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--payload", PAYLOAD],
        cwd=V1_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Incident:" in result.stdout
    assert "Openclaw offline synthetic investigation completed" in result.stdout
    assert "Remediation executed: false" in result.stdout
    assert "Live service call counters" not in result.stdout


def test_project_local_openclaw_runner_live_mode_requires_explicit_gate() -> None:
    env = {**os.environ}
    env.pop("AI_SOC_LIVE_TESTS", None)
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--payload", PAYLOAD, "--live-full-lan"],
        cwd=V1_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 2
    assert "live LAN mode requires AI_SOC_LIVE_TESTS=1" in result.stderr
