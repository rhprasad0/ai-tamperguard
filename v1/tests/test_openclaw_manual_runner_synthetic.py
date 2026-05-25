"""Synthetic manual-runner integration tests for Task 11."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from openclaw_ai_soc.cli import main, resolve_payload_path
from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.graph import run_investigation
from openclaw_ai_soc.nodes import ServiceBundle

REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = (
    REPO_ROOT / "tests" / "fixtures" / "triggers" / "telemetry_disable_canary.json"
)


class FakeSplunk:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.called = False

    def run(self, state: dict) -> dict:
        self.called = True
        if self.fail:
            raise RuntimeError("Splunk query failed with bearer abc.def.ghi")
        return {
            "splunk_queries_run": [
                {
                    "template_id": "agentops_telemetry_disable_canary",
                    "search_id": "search-synthetic-1",
                    "earliest": state["time_window"]["earliest"],
                    "latest": state["time_window"]["latest"],
                    "max_results": 50,
                    "result_count": 1,
                    "status": "ok",
                    "query_hash": "hash-synthetic-1",
                }
            ],
            "evidence": [
                {
                    "kind": "splunk_summary",
                    "summary": "Synthetic event suggests telemetry disable behavior.",
                    "template_id": "agentops_telemetry_disable_canary",
                    "selected_fields": [{"host": "pi-agent-01"}],
                    "redactions": [],
                    "untrusted_evidence_locations": ["source_alert.description"],
                }
            ],
            "evidence_quality": "sufficient",
        }


class FakeGraphiti:
    def __init__(self, *, fail_lookup: bool = False, fail_write: bool = False) -> None:
        self.fail_lookup = fail_lookup
        self.fail_write = fail_write

    async def lookup(self, state: dict) -> dict:
        if self.fail_lookup:
            raise RuntimeError("Graphiti unavailable password=not-for-output")
        return {
            "memory_matches": [
                {
                    "case_id": "case-1",
                    "classification": "telemetry_failure",
                    "summary": "Telemetry disable canary previously required review.",
                    "relevance": "high",
                }
            ]
        }

    async def write(self, state: dict) -> dict:
        if self.fail_write:
            raise RuntimeError("Graphiti write unavailable")
        return {
            "memory_write_status": "written",
            "trace_ids": {"graphiti_episode_id": "episode-synthetic-1"},
        }


class FakeLLM:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def analyze(self, state: dict) -> dict:
        if self.fail:
            raise RuntimeError(
                "Model bridge failed with token eyJhbGciOiJIUzI1NiJ9.abc.def"
            )
        return {
            "analysis": {
                "key_findings": ["Telemetry disable canary fired."],
                "alternative_explanations": ["Synthetic lab scenario."],
            },
            "classification": "telemetry_failure",
            "confidence": "high",
            "recommended_actions": [
                {
                    "action": "escalate",
                    "priority": "high",
                    "reason": "Human review is required; no remediation was executed.",
                    "execution_allowed": False,
                }
            ],
            "remediation_plan": {
                "generated": False,
                "execution_enabled": False,
                "requires_human_approval": True,
                "steps": [],
                "executed": False,
            },
            "human_review_required": True,
            "prompt_injection_detected": False,
            "telemetry_evasion_detected": True,
            "summary": {
                "short": "Telemetry disable canary indicates telemetry_failure.",
                "details": (
                    "Synthetic evidence and Graphiti precedent support human review."
                ),
            },
        }


class FakeNotifier:
    def __init__(self) -> None:
        self.called = False

    def notify(self, state: dict) -> dict:
        self.called = True
        return {"notification_status": "not_configured"}


@pytest.fixture
def fake_services() -> ServiceBundle:
    return ServiceBundle(
        splunk=FakeSplunk(),
        graphiti=FakeGraphiti(),
        llm=FakeLLM(),
        notifier=FakeNotifier(),
    )


def test_runner_accepts_injected_fake_services(fake_services: ServiceBundle) -> None:
    state = run_investigation(
        PAYLOAD, settings=OpenclawSettings(), services=fake_services
    )

    assert state["investigation_status"] == "completed"
    assert state["classification"] == "telemetry_failure"
    assert state["confidence"] == "high"
    assert state["human_review_required"] is True
    assert state["remediation_plan"]["executed"] is False
    assert state["notification_status"] == "not_configured"
    assert state["memory_write_status"] == "written"
    assert state["trace_ids"]["graphiti_episode_id"] == "episode-synthetic-1"


def test_cli_reads_json_payload_and_prints_hermes_summary(
    fake_services: ServiceBundle, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["--payload", str(PAYLOAD)], services=fake_services, env_file=None)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Incident:" in captured.out
    assert "Classification: telemetry_failure" in captured.out
    assert "Confidence: high" in captured.out
    assert "Human review required: true" in captured.out
    assert "Remediation executed: false" in captured.out
    assert "search-synthetic-1" in captured.out
    assert "episode-synthetic-1" in captured.out
    assert "Slack" not in captured.out


def test_cli_subprocess_uses_sys_executable() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "openclaw_ai_soc.cli", "--payload", str(PAYLOAD)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Incident:" in result.stdout
    assert "Remediation executed: false" in result.stdout


def test_cli_rejects_payload_outside_repo_or_with_arbitrary_python_extension(
    tmp_path: Path,
) -> None:
    outside_json = tmp_path / "payload.json"
    outside_json.write_text("{}")
    in_repo_py = REPO_ROOT / "tests" / "fixtures" / "triggers" / "unsafe_payload.py"

    with pytest.raises(ValueError, match="inside this repository"):
        resolve_payload_path(outside_json)
    with pytest.raises(ValueError, match="JSON"):
        resolve_payload_path(in_repo_py)


def test_cli_does_not_require_slack(fake_services: ServiceBundle) -> None:
    notifier = fake_services.notifier

    state = run_investigation(
        PAYLOAD, settings=OpenclawSettings(), services=fake_services
    )

    assert isinstance(notifier, FakeNotifier)
    assert notifier.called is True
    assert state["notification_status"] == "not_configured"


@pytest.mark.parametrize(
    ("services", "component", "status_label"),
    [
        (
            ServiceBundle(
                splunk=FakeSplunk(fail=True),
                graphiti=FakeGraphiti(),
                llm=FakeLLM(),
                notifier=FakeNotifier(),
            ),
            "splunk",
            "failed_at_splunk",
        ),
        (
            ServiceBundle(
                splunk=FakeSplunk(),
                graphiti=FakeGraphiti(fail_lookup=True),
                llm=FakeLLM(),
                notifier=FakeNotifier(),
            ),
            "graphiti",
            "failed_at_graphiti",
        ),
        (
            ServiceBundle(
                splunk=FakeSplunk(),
                graphiti=FakeGraphiti(),
                llm=FakeLLM(fail=True),
                notifier=FakeNotifier(),
            ),
            "llm",
            "failed_at_llm",
        ),
    ],
)
def test_partial_summary_for_splunk_graphiti_and_model_failures(
    services: ServiceBundle, component: str, status_label: str
) -> None:
    state = run_investigation(PAYLOAD, settings=OpenclawSettings(), services=services)

    assert state["investigation_status"] == "failed"
    assert state["trace_ids"]["failure_status"] == status_label
    assert state["errors"][-1]["component"] == component
    assert state["summary"]["short"] == f"Openclaw investigation failed at {component}."
    serialized = json.dumps(state, sort_keys=True)
    assert "abc.def.ghi" not in serialized
    assert "not-for-output" not in serialized
    assert "eyJhbGci" not in serialized


def test_partial_summary_status_label_matches_failure_source() -> None:
    state = run_investigation(
        PAYLOAD,
        settings=OpenclawSettings(),
        services=ServiceBundle(
            splunk=FakeSplunk(),
            graphiti=FakeGraphiti(),
            llm=FakeLLM(fail=True),
            notifier=FakeNotifier(),
        ),
    )

    assert state["trace_ids"]["failure_status"] == "failed_at_llm"
    assert state["summary"]["details"].startswith("Partial result retained")
