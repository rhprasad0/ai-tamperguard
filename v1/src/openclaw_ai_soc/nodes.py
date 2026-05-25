"""LangGraph node helpers for the conservative Openclaw v1 pipeline."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.llm import analyze_with_llm
from openclaw_ai_soc.memory.graphiti import (
    GraphitiMemoryClient,
    lookup_graphiti_precedents,
    write_case_law_memory,
)
from openclaw_ai_soc.redaction import redact_payload
from openclaw_ai_soc.splunk.client import SplunkQueryEnvelope, SplunkTemplateClient
from openclaw_ai_soc.splunk.playbooks import load_template_registry
from openclaw_ai_soc.state import IncidentState, ManualHermesTrigger, RemediationPlan
from openclaw_ai_soc.summary import render_summary_node
from openclaw_ai_soc.tracing import resolve_trace_mode
from openclaw_ai_soc.validation import validate_decision


class SplunkService(Protocol):
    """Injected Splunk service boundary used by the graph runner."""

    def run(self, state: dict[str, Any]) -> dict[str, Any]: ...


class GraphitiService(Protocol):
    """Injected async Graphiti service boundary used by the graph runner."""

    async def lookup(self, state: dict[str, Any]) -> dict[str, Any]: ...

    async def write(self, state: dict[str, Any]) -> dict[str, Any]: ...


class LLMService(Protocol):
    """Injected model bridge boundary used by the graph runner."""

    def analyze(self, state: dict[str, Any]) -> dict[str, Any] | BaseModel: ...


class NotifierService(Protocol):
    """Injected summary notification boundary; Slack is not required in v1."""

    def notify(self, state: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ServiceBundle:
    """Dependency-injection bundle for all side-effecting graph boundaries."""

    splunk: SplunkService
    graphiti: GraphitiService
    llm: LLMService
    notifier: NotifierService


def trigger_manual_hermes(state: dict[str, Any]) -> dict[str, Any]:
    """Validate that the v1 run came from the manual Hermes boundary."""

    if state.get("trigger_type") != "manual_hermes":
        raise ValueError("v1 only accepts trigger_type=manual_hermes")
    return {"investigation_status": "running"}


def normalize_incident(
    payload: dict[str, Any] | str | Path,
    *,
    settings: OpenclawSettings | None = None,
) -> dict[str, Any]:
    """Normalize a manual trigger payload into the typed LangGraph state shape."""

    effective_settings = settings or OpenclawSettings()
    trigger = ManualHermesTrigger.model_validate(payload)
    source_alert = trigger.source_alert.model_dump()
    raw = source_alert.get("raw", {})
    entities = _extract_entities(raw)
    incident_id = _incident_id(trigger.model_dump())
    received_at = datetime.now(UTC).isoformat()
    state = IncidentState(
        incident_id=incident_id,
        trigger_type=trigger.trigger_type,
        incident_mode=trigger.incident_mode,
        source_alert=trigger.source_alert,
        received_at=received_at,
        time_window=trigger.time_window,
        entities=entities,
        selected_playbooks=[],
        splunk_queries_run=[],
        evidence=[],
        evidence_quality="none",
        memory_matches=[],
        recommended_actions=[],
        remediation_plan=RemediationPlan(),
        human_review_required=True,
        prompt_injection_detected=False,
        telemetry_evasion_detected=False,
        notification_status="not_configured",
        memory_write_status="not_attempted",
        investigation_status="running",
        trace_ids={
            "trace_mode": resolve_trace_mode(
                trigger.incident_mode, settings=effective_settings
            )
        },
        model_endpoint=effective_settings.openai_base_url,
        model_name=effective_settings.ai_soc_model,
        errors=[],
    )
    return state.model_dump()


def select_evidence_playbooks(state: dict[str, Any]) -> dict[str, Any]:
    """Select curated v1 SPL templates; never accepts model-authored SPL."""

    source_alert = state.get("source_alert") or {}
    alert_type = source_alert.get("alert_type")
    selected = ["host_recent_activity", "recent_alert_context"]
    if alert_type == "telemetry_disable_canary":
        selected.insert(0, "agentops_telemetry_disable_canary")
    return {"selected_playbooks": _existing_templates(selected)}


def collect_splunk_evidence(
    state: dict[str, Any],
    *,
    splunk_client: SplunkTemplateClient | None = None,
    settings: OpenclawSettings | None = None,
    max_results: int | None = None,
) -> dict[str, Any]:
    """Collect bounded curated Splunk evidence for selected playbooks.

    The node returns only query metadata, structured errors, and compact redacted
    evidence summaries. Rendered SPL and raw event bodies stay out of the node
    contract.
    """

    if splunk_client is None:
        raise ValueError("collect_splunk_evidence requires an injected Splunk client")

    effective_settings = settings or OpenclawSettings()
    template_ids = list(state.get("selected_playbooks", []))
    time_window = state.get("time_window", {})
    earliest = time_window.get("earliest", effective_settings.splunk_default_earliest)
    latest = time_window.get("latest", effective_settings.splunk_default_latest)
    entities = dict(state.get("entities", {}))
    registry = load_template_registry()

    query_records: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for template_id in template_ids:
        template = registry[template_id]
        params = {name: entities[name] for name in template.params if name in entities}
        result = splunk_client.splunk_run_curated_template(
            SplunkQueryEnvelope(
                template_id=template_id,
                params=params,
                earliest=earliest,
                latest=latest,
                max_results=max_results or template.max_results,
            )
        )
        query_records.append(result.to_query_record())
        evidence_records.extend(item.to_node_payload() for item in result.evidence)
        if result.error is not None:
            errors.append(result.error.model_dump())

    return {
        "splunk_queries_run": query_records,
        "evidence": evidence_records,
        "evidence_quality": _evidence_quality(query_records),
        "errors": errors,
    }


async def lookup_graphiti_precedent_node(
    state: dict[str, Any], *, memory_client: GraphitiMemoryClient
) -> dict[str, Any]:
    """LangGraph adapter for Graphiti precedent lookup."""

    return await lookup_graphiti_precedents(state, memory_client=memory_client)


def analyze_incident_node(state: dict[str, Any], *, llm_client: Any) -> dict[str, Any]:
    """LangGraph adapter for model analysis."""

    return analyze_with_llm(state, llm_client=llm_client)


def validate_decision_node(state: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize model output currently merged into state."""

    decision = {
        "analysis": state.get("analysis"),
        "classification": state.get("classification"),
        "confidence": state.get("confidence"),
        "recommended_actions": state.get("recommended_actions", []),
        "remediation_plan": state.get("remediation_plan", {}),
        "human_review_required": state.get("human_review_required", True),
        "prompt_injection_detected": state.get("prompt_injection_detected", False),
        "telemetry_evasion_detected": state.get("telemetry_evasion_detected", False),
        "summary": state.get("summary"),
    }
    evidence = state.get("evidence", [])
    if _has_model_invalid_output(state):
        evidence = []
    validated = validate_decision(decision, evidence=evidence)
    return validated.model_dump()


def _has_model_invalid_output(state: dict[str, Any]) -> bool:
    return any(
        isinstance(error, dict) and error.get("code") == "model_invalid_output"
        for error in state.get("errors", []) or []
    )


def render_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure a concise Hermes-ready summary is present."""

    return render_summary_node(state)


async def write_graphiti_memory_node(
    state: dict[str, Any], *, memory_client: GraphitiMemoryClient
) -> dict[str, Any]:
    """LangGraph adapter for compact case-law writes."""

    return await write_case_law_memory(state, memory_client=memory_client)


def notify_summary_node(state: dict[str, Any]) -> dict[str, Any]:
    """Default no-Slack notification node for v1 unit-level graph tests."""

    from openclaw_ai_soc.notifications.summary_only import notify_summary_node as _node

    return _node(state)


def complete_investigation(state: dict[str, Any]) -> dict[str, Any]:
    """Mark clean serial v1 runs complete without hiding partial/error statuses."""

    current_status = str(state.get("investigation_status", "running"))
    if current_status in {"running", "queued"}:
        return {"investigation_status": "completed"}
    return {"investigation_status": current_status}


def handle_failure(
    state: dict[str, Any], *, component: str, exc: BaseException | str
) -> dict[str, Any]:
    """Return a non-secret partial summary and stable error record for failures."""

    raw_message = str(exc)
    redacted = _sanitize_error_message(raw_message)
    error = {
        "code": f"{component}_failure",
        "message": redacted,
        "component": component,
    }
    errors = [*state.get("errors", []), error]
    trace_ids = {
        **state.get("trace_ids", {}),
        "failure_status": f"failed_at_{component}",
    }
    return {
        "investigation_status": "failed",
        "errors": errors,
        "trace_ids": trace_ids,
        "summary": {
            "short": f"Openclaw investigation failed at {component}.",
            "details": (
                "Partial result retained for human review. "
                f"Failure source: {component}. Error code: {error['code']}."
            ),
        },
        "human_review_required": True,
        "remediation_plan": {
            **state.get("remediation_plan", {}),
            "execution_enabled": False,
            "executed": False,
            "requires_human_approval": True,
        },
    }


def _sanitize_error_message(message: str) -> str:
    sanitized = str(redact_payload(message).sanitized_payload)
    sanitized = re.sub(
        r"(?i)Bearer\s+[^\s,;}\]]+", "<redacted:bearer_token>", sanitized
    )
    sanitized = re.sub(
        r"\b[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
        "<redacted:jwt>",
        sanitized,
    )
    return sanitized


def _evidence_quality(query_records: list[dict[str, Any]]) -> str:
    if not query_records:
        return "none"
    successes = [
        record
        for record in query_records
        if record["status"] == "ok" and record["result_count"] > 0
    ]
    if not successes:
        return "none"
    if len(successes) == len(query_records):
        return "sufficient"
    return "partial"


def _extract_entities(raw: dict[str, Any]) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    if isinstance(raw, dict):
        if raw.get("host"):
            entities["host"] = raw["host"]
        if raw.get("scenario_id"):
            entities["scenario_id"] = raw["scenario_id"]
        scenario = raw.get("scenario")
        if isinstance(scenario, dict) and scenario.get("id"):
            entities["scenario_id"] = scenario["id"]
    return entities


def _incident_id(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()
    return f"openclaw-{digest[:12]}"


def _existing_templates(template_ids: list[str]) -> list[str]:
    registry = load_template_registry()
    return [template_id for template_id in template_ids if template_id in registry]
