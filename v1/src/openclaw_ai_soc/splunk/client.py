"""Bounded Splunk evidence client for curated Openclaw v1 playbooks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import Field, field_validator

from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.logging import emit_log, get_logger
from openclaw_ai_soc.redaction import redact_payload
from openclaw_ai_soc.splunk.playbooks import CuratedTemplateError, render_curated_query
from openclaw_ai_soc.state import ErrorRecord, StrictBoundaryModel


class SplunkQueryFailure(RuntimeError):
    """Raised by a transport when Splunk cannot execute a bounded query."""


_LOGGER = get_logger(__name__)

class SplunkTransport(Protocol):
    """Injected transport boundary; tests use fakes, live clients are opt-in later."""

    def run_search(
        self, *, query: str, earliest: str, latest: str, max_results: int
    ) -> TransportSearchResult: ...


class SplunkQueryEnvelope(StrictBoundaryModel):
    """Required input envelope for one curated template execution."""

    template_id: str
    params: dict[str, Any]
    earliest: str
    latest: str
    max_results: int = Field(gt=0)

    @field_validator("template_id", "earliest", "latest")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be non-empty text")
        return value


@dataclass(frozen=True)
class TransportSearchResult:
    """Minimal normalized transport result, with raw rows kept inside the client."""

    search_id: str | None
    results: list[dict[str, Any]]


@dataclass(frozen=True)
class EvidenceSummary:
    """Compact redacted evidence summary safe for model/node payloads."""

    kind: str
    summary: str
    template_id: str
    selected_fields: list[dict[str, Any]]
    redactions: list[str] = field(default_factory=list)
    untrusted_evidence_locations: list[str] = field(default_factory=list)

    def to_node_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "template_id": self.template_id,
            "selected_fields": self.selected_fields,
            "redactions": self.redactions,
            "untrusted_evidence_locations": self.untrusted_evidence_locations,
        }


@dataclass(frozen=True)
class SplunkTemplateResult:
    """Result of one curated Splunk template execution."""

    template_id: str
    status: str
    earliest: str
    latest: str
    max_results: int
    query_hash: str
    search_id: str | None = None
    result_count: int = 0
    evidence: list[EvidenceSummary] = field(default_factory=list)
    error: ErrorRecord | None = None

    def to_query_record(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "search_id": self.search_id,
            "earliest": self.earliest,
            "latest": self.latest,
            "max_results": self.max_results,
            "result_count": self.result_count,
            "status": self.status,
            "query_hash": self.query_hash,
        }

    def to_node_payload(self) -> dict[str, Any]:
        return {
            "query": self.to_query_record(),
            "evidence": [item.to_node_payload() for item in self.evidence],
            "error": self.error.model_dump() if self.error else None,
        }


_SELECTED_FIELD_NAMES = (
    "_time",
    "host",
    "source",
    "sourcetype",
    "user",
    "process",
    "process.name",
    "src_ip",
    "dest_ip",
    "dest_port",
    "scenario_id",
    "scenario.id",
    "service_name",
    "service.name",
    "count",
    "latest",
    "message",
)


class SplunkTemplateClient:
    """Execute allowlisted Splunk templates through an injected transport."""

    def __init__(
        self,
        *,
        transport: SplunkTransport,
        settings: OpenclawSettings | None = None,
    ) -> None:
        self._transport = transport
        self._settings = settings or OpenclawSettings()

    def splunk_run_curated_template(
        self, envelope: SplunkQueryEnvelope | dict[str, Any]
    ) -> SplunkTemplateResult:
        """Render, bound-check, execute, and summarize one curated template."""

        request = SplunkQueryEnvelope.model_validate(envelope)
        emit_log(
            _LOGGER,
            event="splunk.template.started",
            component="splunk",
            status="started",
            template_id=request.template_id,
        )
        query_hash = _safe_hash(
            f"{request.template_id}:{request.earliest}:{request.latest}:{request.max_results}"
        )

        try:
            window_minutes = _duration_minutes(request.earliest)
            max_window_minutes = _duration_minutes(self._settings.splunk_max_window)
        except ValueError as exc:
            return _failed_result(
                request,
                query_hash=query_hash,
                code="splunk_query_rejected",
                message=str(exc),
            )

        if window_minutes > max_window_minutes:
            return _failed_result(
                request,
                query_hash=query_hash,
                code="splunk_window_exceeds_global_max",
                message="query earliest exceeds SPLUNK_MAX_WINDOW",
            )
        if request.max_results > self._settings.splunk_max_results:
            return _failed_result(
                request,
                query_hash=query_hash,
                code="splunk_result_cap_exceeds_global_max",
                message="query max_results exceeds SPLUNK_MAX_RESULTS",
            )

        try:
            rendered = render_curated_query(
                request.template_id,
                request.params,
                earliest=request.earliest,
                latest=request.latest,
                max_results=request.max_results,
            )
        except CuratedTemplateError as exc:
            return _failed_result(
                request,
                query_hash=query_hash,
                code="splunk_query_rejected",
                message=str(exc),
            )

        query_hash = _safe_hash(rendered.query)
        try:
            transport_result = self._transport.run_search(
                query=rendered.query,
                earliest=rendered.earliest,
                latest=rendered.latest,
                max_results=rendered.max_results,
            )
        except Exception as exc:  # noqa: BLE001 - boundary converts all transport errors.
            return _failed_result(
                request,
                query_hash=query_hash,
                code="splunk_query_failed",
                message=str(exc),
            )

        bounded_results = transport_result.results[: rendered.max_results]
        evidence = _summarize_evidence(
            template_id=request.template_id,
            results=bounded_results,
        )
        result = SplunkTemplateResult(
            template_id=request.template_id,
            status="ok",
            earliest=rendered.earliest,
            latest=rendered.latest,
            max_results=rendered.max_results,
            query_hash=query_hash,
            search_id=transport_result.search_id,
            result_count=len(bounded_results),
            evidence=evidence,
        )
        _emit_splunk_result(result)
        return result


def _failed_result(
    request: SplunkQueryEnvelope,
    *,
    query_hash: str,
    code: str,
    message: str,
) -> SplunkTemplateResult:
    result = SplunkTemplateResult(
        template_id=request.template_id,
        status="failed",
        earliest=request.earliest,
        latest=request.latest,
        max_results=request.max_results,
        query_hash=query_hash,
        error=ErrorRecord(code=code, message=message, component="splunk"),
    )
    _emit_splunk_result(result)
    return result


def _emit_splunk_result(result: SplunkTemplateResult) -> None:
    splunk_event = (
        "splunk.template.completed"
        if result.status == "ok"
        else "splunk.template.failed"
    )
    emit_log(
        _LOGGER,
        event=splunk_event,
        component="splunk",
        status="ok" if result.status == "ok" else "failed",
        template_id=result.template_id,
        result_count=result.result_count,
        search_id=result.search_id,
        query_hash=result.query_hash,
        error_code=result.error.code if result.error else None,
        message=result.error.message if result.error else None,
    )


def _summarize_evidence(
    *, template_id: str, results: list[dict[str, Any]]
) -> list[EvidenceSummary]:
    if not results:
        return []

    selected_rows = [_select_compact_fields(row) for row in results]
    redacted = redact_payload(selected_rows)
    summary = _template_summary(template_id, len(results))
    return [
        EvidenceSummary(
            kind="splunk_template_summary",
            summary=summary,
            template_id=template_id,
            selected_fields=redacted.sanitized_payload,
            redactions=list(redacted.summary.categories),
            untrusted_evidence_locations=list(
                redacted.summary.untrusted_evidence_locations
            ),
        )
    ]


def _template_summary(template_id: str, result_count: int) -> str:
    if template_id == "agentops_telemetry_disable_canary":
        return (
            f"{result_count} bounded Splunk result(s) matched the synthetic "
            "disable telemetry canary template; selected fields only, raw event "
            "body omitted."
        )
    return (
        f"{result_count} bounded Splunk result(s) for {template_id}; "
        f"selected fields only, raw event body omitted."
    )


def _select_compact_fields(row: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for field_name in _SELECTED_FIELD_NAMES:
        if field_name in row:
            selected[field_name] = row[field_name]
    return selected


def _safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _duration_minutes(value: str) -> int:
    if not isinstance(value, str) or len(value) < 2:
        raise ValueError("duration must be a bounded string")
    signless = value[1:] if value.startswith("-") else value
    amount_text = signless[:-1]
    unit = signless[-1]
    if not amount_text.isdigit() or unit not in {"m", "h", "d"}:
        raise ValueError("duration must be a bounded m/h/d string")
    amount = int(amount_text)
    if unit == "m":
        return amount
    if unit == "h":
        return amount * 60
    return amount * 24 * 60
