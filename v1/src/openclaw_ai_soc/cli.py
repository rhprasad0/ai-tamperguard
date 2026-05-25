"""Manual Hermes-friendly CLI for one Sergeant Openclaw investigation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from openclaw_ai_soc.config import OpenclawSettings, load_config
from openclaw_ai_soc.graph import run_investigation
from openclaw_ai_soc.logging import configure_logging
from openclaw_ai_soc.nodes import ServiceBundle
from openclaw_ai_soc.summary import render_hermes_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


class OfflineSplunkService:
    """Safe local synthetic service used when no live service is injected."""

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "splunk_queries_run": [
                {
                    "template_id": template_id,
                    "search_id": f"offline-{template_id}",
                    "earliest": state["time_window"]["earliest"],
                    "latest": state["time_window"]["latest"],
                    "max_results": 50,
                    "result_count": 1,
                    "status": "ok",
                    "query_hash": f"offline-{template_id}",
                }
                for template_id in state.get("selected_playbooks", [])
            ],
            "evidence": [
                {
                    "kind": "splunk_summary",
                    "summary": state.get("source_alert", {}).get(
                        "description", "Synthetic manual payload accepted."
                    ),
                    "template_id": state.get("selected_playbooks", [None])[0],
                    "selected_fields": [state.get("entities", {})],
                    "redactions": [],
                    "untrusted_evidence_locations": ["source_alert.description"],
                }
            ],
            "evidence_quality": "sufficient",
        }


class OfflineGraphitiService:
    """Safe local Graphiti substitute for manual synthetic dry runs."""

    async def lookup(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"memory_matches": []}

    async def write(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"memory_write_status": "skipped"}


class OfflineLLMService:
    """Safe local model substitute for manual synthetic dry runs."""

    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "analysis": {
                "key_findings": [
                    "Synthetic manual runner completed without live services."
                ],
                "alternative_explanations": [
                    "Offline dry run; verify live evidence later."
                ],
            },
            "classification": "telemetry_failure"
            if state.get("source_alert", {}).get("alert_type")
            == "telemetry_disable_canary"
            else "inconclusive",
            "confidence": "medium",
            "recommended_actions": [
                {
                    "action": "investigate",
                    "priority": "medium",
                    "reason": "Review the bounded evidence anchors in Hermes.",
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
                "short": "Openclaw offline synthetic investigation completed.",
                "details": (
                    "No Slack, Splunk, Graphiti, or model network calls were required."
                ),
            },
        }


class OfflineNotifierService:
    """No-Slack notifier used by the v1 manual CLI by default."""

    def notify(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"notification_status": "not_configured"}


def default_offline_services() -> ServiceBundle:
    """Return a no-network service bundle for CLI dry-run safety."""

    return ServiceBundle(
        splunk=OfflineSplunkService(),
        graphiti=OfflineGraphitiService(),
        llm=OfflineLLMService(),
        notifier=OfflineNotifierService(),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    services: ServiceBundle | None = None,
    env_file: str | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="openclaw-investigate")
    parser.add_argument(
        "--payload", required=True, help="Path to a JSON trigger payload"
    )
    args = parser.parse_args(argv)
    payload_path = resolve_payload_path(Path(args.payload))
    settings = load_config(env_file=env_file) if env_file else OpenclawSettings()
    configure_logging(
        level=settings.ai_soc_log_level,
        log_format=settings.ai_soc_log_format,
    )
    state = run_investigation(
        payload_path,
        settings=settings,
        services=services or default_offline_services(),
    )
    print(format_hermes_summary(state))
    return 0 if state.get("investigation_status") in {"completed", "failed"} else 1


def resolve_payload_path(path: Path) -> Path:
    """Resolve and constrain payloads to JSON files inside this repository."""

    resolved = path.resolve()
    if resolved.suffix.lower() != ".json":
        raise ValueError("payload must be a JSON file, not executable Python or text")
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError("payload must live inside this repository") from exc
    return resolved


def format_hermes_summary(state: dict[str, Any]) -> str:
    """Render a concise terminal/Hermes-ready summary without raw event dumps."""

    return render_hermes_summary(state)


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main())
