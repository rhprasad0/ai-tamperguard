"""LangGraph construction and manual runner for Sergeant Openclaw v1."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.logging import emit_log, get_logger
from openclaw_ai_soc.nodes import (
    ServiceBundle,
    complete_investigation,
    handle_failure,
    normalize_incident,
    notify_summary_node,
    render_summary,
    select_evidence_playbooks,
    trigger_manual_hermes,
    validate_decision_node,
)
from openclaw_ai_soc.state import OpenclawState

V1_NODE_ORDER = [
    "trigger.manual_hermes",
    "normalize_incident",
    "select_evidence_playbooks",
    "collect_splunk_evidence",
    "lookup_graphiti_precedent",
    "analyze_incident",
    "validate_decision",
    "render_summary",
    "write_graphiti_memory",
    "notify_summary",
    "handle_failure",
]
_FAILURE_ROUTED_NODES = [node for node in V1_NODE_ORDER if node != "handle_failure"]
_LOGGER = get_logger(__name__)


class GraphConstructionError(ValueError):
    """Raised when startup settings would violate conservative v1 invariants."""


@dataclass(frozen=True)
class OpenclawGraph:
    """Compiled LangGraph plus auditable v1 graph metadata."""

    compiled: CompiledStateGraph
    node_order: list[str]
    failure_node_name: str
    failure_routed_nodes: list[str]


def build_openclaw_graph(
    *, settings: OpenclawSettings, services: ServiceBundle
) -> OpenclawGraph:
    """Build the serial v1 StateGraph and enforce graph-level safety gates."""

    _assert_v1_graph_settings(settings)
    builder = StateGraph(OpenclawState)
    builder.add_node("trigger.manual_hermes", trigger_manual_hermes)  # type: ignore[type-var]
    builder.add_node("normalize_incident", lambda state: state)
    builder.add_node("select_evidence_playbooks", select_evidence_playbooks)  # type: ignore[type-var]
    builder.add_node("collect_splunk_evidence", services.splunk.run)  # type: ignore[type-var]
    builder.add_node("lookup_graphiti_precedent", services.graphiti.lookup)  # type: ignore[type-var]
    builder.add_node("analyze_incident", services.llm.analyze)  # type: ignore[type-var]
    builder.add_node("validate_decision", validate_decision_node)  # type: ignore[type-var]
    builder.add_node("render_summary", render_summary)  # type: ignore[type-var]
    builder.add_node("write_graphiti_memory", services.graphiti.write)  # type: ignore[type-var]
    builder.add_node("notify_summary", _notify_with_service(services))  # type: ignore[arg-type]
    builder.add_node("handle_failure", _metadata_failure_node)  # type: ignore[type-var]

    builder.set_entry_point("trigger.manual_hermes")
    serial_edges = [
        ("trigger.manual_hermes", "normalize_incident"),
        ("normalize_incident", "select_evidence_playbooks"),
        ("select_evidence_playbooks", "collect_splunk_evidence"),
        ("collect_splunk_evidence", "lookup_graphiti_precedent"),
        ("lookup_graphiti_precedent", "analyze_incident"),
        ("analyze_incident", "validate_decision"),
        ("validate_decision", "render_summary"),
        ("render_summary", "write_graphiti_memory"),
        ("write_graphiti_memory", "notify_summary"),
        ("notify_summary", END),
        ("handle_failure", END),
    ]
    for source, destination in serial_edges:
        builder.add_edge(source, destination)

    return OpenclawGraph(
        compiled=builder.compile(),
        node_order=list(V1_NODE_ORDER),
        failure_node_name="handle_failure",
        failure_routed_nodes=list(_FAILURE_ROUTED_NODES),
    )


def required_v1_node_names(graph: OpenclawGraph) -> list[str]:
    """Return required v1 nodes in their serial execution order."""

    return list(graph.node_order)


def run_investigation(
    payload_path: str | Path,
    *,
    settings: OpenclawSettings,
    services: ServiceBundle,
) -> dict[str, Any]:
    """Run one manual Hermes investigation with injected services."""

    build_openclaw_graph(settings=settings, services=services)
    payload = json.loads(Path(payload_path).read_text())
    state = normalize_incident(payload, settings=settings)
    run_started = perf_counter()
    emit_log(
        _LOGGER,
        event="investigation.started",
        component="graph",
        status="started",
        incident_id=state.get("incident_id"),
        trace_mode=_trace_mode(state),
    )
    steps: list[tuple[str, Callable[[dict[str, Any]], Any]]] = [
        ("trigger", trigger_manual_hermes),
        ("playbooks", select_evidence_playbooks),
        ("splunk", services.splunk.run),
        ("graphiti", services.graphiti.lookup),
        ("llm", services.llm.analyze),
        ("decision", validate_decision_node),
        ("summary", render_summary),
        ("graphiti", services.graphiti.write),
        ("notify", _notify_with_service(services)),
        ("complete", complete_investigation),
    ]
    for component, step in steps:
        step_started = perf_counter()
        emit_log(
            _LOGGER,
            event="node.started",
            component="graph",
            status="started",
            incident_id=state.get("incident_id"),
            node=component,
            trace_mode=_trace_mode(state),
        )
        try:
            update = step(state)
            if asyncio.iscoroutine(update):
                update = asyncio.run(update)
            _merge_state(state, update or {})
            emit_log(
                _LOGGER,
                event="node.completed",
                component="graph",
                status="ok",
                incident_id=state.get("incident_id"),
                node=component,
                duration_ms=_elapsed_ms(step_started),
                classification=state.get("classification"),
                trace_mode=_trace_mode(state),
                memory_write_status=state.get("memory_write_status"),
                notification_status=state.get("notification_status"),
            )
        except Exception as exc:  # noqa: BLE001 - graph boundary converts failures.
            _merge_state(state, handle_failure(state, component=component, exc=exc))
            emit_log(
                _LOGGER,
                event="node.failed",
                component="graph",
                status="failed",
                incident_id=state.get("incident_id"),
                node=component,
                duration_ms=_elapsed_ms(step_started),
                error_code=f"{component}_failure",
                message=str(exc),
                trace_mode=_trace_mode(state),
            )
            break
    investigation_failed = state.get("investigation_status") == "failed"
    final_event = (
        "investigation.failed" if investigation_failed else "investigation.completed"
    )
    emit_log(
        _LOGGER,
        event=final_event,
        component="graph",
        status="failed" if investigation_failed else "completed",
        incident_id=state.get("incident_id"),
        duration_ms=_elapsed_ms(run_started),
        classification=state.get("classification"),
        trace_mode=_trace_mode(state),
        memory_write_status=state.get("memory_write_status"),
        notification_status=state.get("notification_status"),
    )
    return state


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _trace_mode(state: dict[str, Any]) -> str | None:
    trace_ids = state.get("trace_ids")
    if isinstance(trace_ids, dict):
        trace_mode = trace_ids.get("trace_mode")
        if trace_mode is not None:
            return str(trace_mode)
    return None


def _assert_v1_graph_settings(settings: OpenclawSettings) -> None:
    if settings.ai_soc_trigger_mode != "manual_hermes":
        raise GraphConstructionError("v1 graph requires manual_hermes trigger mode")
    if settings.ai_soc_memory_backend != "graphiti":
        raise GraphConstructionError("v1 graph requires Graphiti as the memory backend")
    if settings.ai_soc_remediation_enabled is not False:
        raise GraphConstructionError("v1 graph refuses remediation-enabled settings")


def _notify_with_service(
    services: ServiceBundle,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _notify(state: dict[str, Any]) -> dict[str, Any]:
        try:
            return services.notifier.notify(state)
        except AttributeError:
            return notify_summary_node(state)

    return _notify


def _metadata_failure_node(state: dict[str, Any]) -> dict[str, Any]:
    return handle_failure(
        state,
        component=str(state.get("failure_component", "unknown")),
        exc=str(state.get("failure_message", "unknown failure")),
    )


def _merge_state(state: dict[str, Any], update: dict[str, Any] | BaseModel) -> None:
    if isinstance(update, BaseModel):
        update = update.model_dump()
    for key, value in update.items():
        if key == "errors" and state.get("errors") and value:
            existing = list(state.get("errors", []))
            incoming = list(value)
            if len(incoming) >= len(existing) and incoming[: len(existing)] == existing:
                state[key] = incoming
            else:
                state[key] = [*existing, *incoming]
        elif key == "trace_ids" and isinstance(value, dict):
            state[key] = {**state.get("trace_ids", {}), **value}
        else:
            state[key] = value
