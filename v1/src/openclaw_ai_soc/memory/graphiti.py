"""Async Graphiti precedent lookup and case-law memory writes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.logging import emit_log, get_logger
from openclaw_ai_soc.state import ErrorRecord, MemoryMatch

SCHEMA_VERSION: str = "openclaw.case_law.v1"
_LOGGER = get_logger(__name__)
_FORBIDDEN_RAW_KEYS = {
    "events",
    "raw_events",
    "raw_event",
    "raw_event_dump",
    "event_dump",
    "raw_prompt",
    "prompt",
    "model_response",
    "raw_model_output",
    "_raw",
    "raw",
}


class GraphitiTransport(Protocol):
    """Small async MCP-compatible transport protocol used by tests and adapters."""

    async def search_memory_facts(
        self, *, query: str, group_ids: list[str], max_facts: int
    ) -> dict[str, Any]: ...

    async def add_memory(
        self,
        *,
        name: str,
        episode_body: str,
        group_id: str,
        source: str,
        source_description: str,
    ) -> dict[str, Any]: ...


class CaseLawWritePayload(BaseModel):
    """Structured Graphiti case law summary, never a raw event dump."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["openclaw.case_law.v1"] = "openclaw.case_law.v1"
    incident_id: str
    incident_mode: str
    alert_type: str | None = None
    classification: str | None = None
    confidence: str | None = None
    summary: str
    findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    memory_refs: list[dict[str, Any]] = Field(default_factory=list)
    human_review_required: bool = True
    human_confirmed: Literal[False] = False
    raw_events_stored: Literal[False] = False

    @model_validator(mode="after")
    def reject_raw_event_content(self) -> CaseLawWritePayload:
        _assert_no_raw_fields(self.model_dump())
        return self


@dataclass(frozen=True)
class MemoryWriteResult:
    memory_write_status: Literal["not_attempted", "written", "failed", "skipped"]
    memory_episode_id: str | None = None
    error: ErrorRecord | None = None


class GraphitiMemoryClient:
    """Async Graphiti client over an injected MCP/HTTP-compatible transport."""

    def __init__(
        self, *, settings: OpenclawSettings | None = None, transport: GraphitiTransport
    ):
        if transport is None:
            raise ValueError(
                "GraphitiMemoryClient requires an injected async transport"
            )
        self.settings = settings or OpenclawSettings()
        self.transport = transport

    async def lookup_precedents(
        self, state: dict[str, Any], *, max_facts: int = 5
    ) -> list[MemoryMatch]:
        query = _precedent_query(state)
        response = await self.transport.search_memory_facts(
            query=query,
            group_ids=[self.settings.graphiti_group_id],
            max_facts=max_facts,
        )
        return _compact_matches(response)

    async def write_case_law(self, state: dict[str, Any]) -> MemoryWriteResult:
        payload = build_case_law_payload(state)
        response = await self.transport.add_memory(
            name=f"Openclaw case law: {payload.incident_id}",
            episode_body=payload.model_dump_json(),
            group_id=self.settings.graphiti_group_id,
            source="json",
            source_description="openclaw.case_law.v1 compact incident precedent",
        )
        episode_id = response.get("uuid") or response.get("episode_uuid")
        return MemoryWriteResult(
            memory_write_status="written", memory_episode_id=episode_id
        )


def build_case_law_payload(state: dict[str, Any]) -> CaseLawWritePayload:
    """Transform validated state into compact case-law memory."""

    _assert_no_raw_fields(state.get("evidence", []))
    summary = state.get("summary") or {}
    analysis = state.get("analysis") or {}
    source_alert = state.get("source_alert") or {}
    evidence_refs = []
    for evidence in state.get("evidence", []):
        evidence_refs.append(
            {
                "kind": evidence.get("kind"),
                "template_id": evidence.get("template_id"),
                "summary": evidence.get("summary"),
                "redactions": list(evidence.get("redactions", [])),
            }
        )
    memory_refs = []
    for match in state.get("memory_matches", []):
        memory_refs.append(
            {
                "case_id": match.get("case_id"),
                "classification": match.get("classification"),
                "relevance": match.get("relevance"),
                "summary": match.get("summary"),
            }
        )
    recommended_actions = [
        action.get("action", "")
        for action in state.get("recommended_actions", [])
        if action.get("action")
    ]
    return CaseLawWritePayload(
        incident_id=state["incident_id"],
        incident_mode=state.get("incident_mode", "unknown"),
        alert_type=source_alert.get("alert_type"),
        classification=state.get("classification"),
        confidence=state.get("confidence"),
        summary=summary.get("short")
        or summary.get("details")
        or "No summary rendered.",
        findings=list(analysis.get("key_findings", [])),
        recommended_actions=recommended_actions,
        evidence_refs=evidence_refs,
        memory_refs=memory_refs,
        human_review_required=bool(state.get("human_review_required", True)),
    )


async def lookup_graphiti_precedents(
    state: dict[str, Any], *, memory_client: GraphitiMemoryClient
) -> dict[str, Any]:
    """Node helper: lookup precedent and continue visibly if Graphiti is down."""

    try:
        emit_log(
            _LOGGER,
            event="graphiti.lookup.started",
            component="graphiti",
            status="started",
            incident_id=state.get("incident_id"),
            group_id=memory_client.settings.graphiti_group_id,
        )
        matches = await memory_client.lookup_precedents(state)
    except Exception as exc:  # noqa: BLE001 - boundary maps all transport failures.
        emit_log(
            _LOGGER,
            event="graphiti.lookup.failed",
            component="graphiti",
            status="failed",
            incident_id=state.get("incident_id"),
            group_id=memory_client.settings.graphiti_group_id,
            error_code="memory_unavailable",
            message=str(exc),
        )
        return {
            "memory_matches": [],
            "evidence_quality": state.get("evidence_quality", "none"),
            "investigation_status": state.get("investigation_status", "running"),
            "errors": [
                ErrorRecord(
                    code="memory_unavailable",
                    message=str(exc),
                    component="graphiti",
                ).model_dump()
            ],
        }
    emit_log(
        _LOGGER,
        event="graphiti.lookup.completed",
        component="graphiti",
        status="ok",
        incident_id=state.get("incident_id"),
        group_id=memory_client.settings.graphiti_group_id,
        match_count=len(matches),
    )
    return {"memory_matches": [match.model_dump() for match in matches]}


async def write_case_law_memory(
    state: dict[str, Any], *, memory_client: GraphitiMemoryClient
) -> dict[str, Any]:
    """Node helper: write case-law summary without invalidating final summary."""

    try:
        emit_log(
            _LOGGER,
            event="graphiti.write.started",
            component="graphiti",
            status="started",
            incident_id=state.get("incident_id"),
            group_id=memory_client.settings.graphiti_group_id,
        )
        result = await memory_client.write_case_law(state)
    except Exception as exc:  # noqa: BLE001 - failed writes are non-fatal in v1.
        emit_log(
            _LOGGER,
            event="graphiti.write.failed",
            component="graphiti",
            status="failed",
            incident_id=state.get("incident_id"),
            group_id=memory_client.settings.graphiti_group_id,
            error_code="memory_write_failed",
            message=str(exc),
        )
        return {
            "memory_write_status": "failed",
            "errors": [
                ErrorRecord(
                    code="memory_write_failed",
                    message=str(exc),
                    component="graphiti",
                ).model_dump()
            ],
        }
    update: dict[str, Any] = {"memory_write_status": result.memory_write_status}
    emit_log(
        _LOGGER,
        event="graphiti.write.completed"
        if result.memory_write_status == "written"
        else "graphiti.write.skipped",
        component="graphiti",
        status="ok" if result.memory_write_status == "written" else "skipped",
        incident_id=state.get("incident_id"),
        group_id=memory_client.settings.graphiti_group_id,
        memory_write_status=result.memory_write_status,
    )
    if result.memory_episode_id:
        update["trace_ids"] = {"graphiti_episode_id": result.memory_episode_id}
    return update


def _precedent_query(state: dict[str, Any]) -> str:
    source_alert = state.get("source_alert") or {}
    entities = state.get("entities") or {}
    chunks = [
        "openclaw incident precedent",
        str(source_alert.get("alert_type", "")),
        str(source_alert.get("description", "")),
        " ".join(f"{key}:{value}" for key, value in sorted(entities.items())),
    ]
    return " ".join(chunk for chunk in chunks if chunk).strip()


def _compact_matches(response: dict[str, Any]) -> list[MemoryMatch]:
    facts = (
        response.get("facts") or response.get("results") or response.get("data") or []
    )
    matches: list[MemoryMatch] = []
    for fact in facts:
        metadata = fact.get("metadata") or {}
        matches.append(
            MemoryMatch(
                case_id=fact.get("name") or fact.get("uuid") or "unknown-case",
                classification=metadata.get("classification"),
                summary=fact.get("summary")
                or fact.get("fact")
                or fact.get("content")
                or "",
                relevance=str(
                    metadata.get("relevance") or fact.get("relevance") or "unknown"
                ),
            )
        )
    return matches


def _assert_no_raw_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_RAW_KEYS:
                raise ValueError(
                    f"raw event or prompt field is forbidden at {path}.{key}"
                )
            _assert_no_raw_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_raw_fields(child, path=f"{path}[{index}]")
    elif isinstance(value, str):
        # Guard against accidental serialized event dumps smuggled into a text field.
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return
        _assert_no_raw_fields(parsed, path=path)
