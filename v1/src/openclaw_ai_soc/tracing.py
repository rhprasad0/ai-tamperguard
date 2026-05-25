"""Trace policy and masking helpers for Openclaw v1."""

from __future__ import annotations

from typing import Any, Literal, cast

from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.redaction import RedactionSummary, redact_payload

IncidentMode = Literal["synthetic", "real_home_telemetry", "private_test"]
TraceMode = Literal["synthetic_full", "redacted", "minimal", "disabled"]
PromptInjectionCorroboration = Literal[
    "not_detected", "model_asserted_only", "redaction_detected", "corroborated"
]

_BASE_TRACE_MODE: dict[IncidentMode, TraceMode] = {
    "synthetic": "synthetic_full",
    "real_home_telemetry": "redacted",
    "private_test": "minimal",
}
_TRACE_MODE_RANK: dict[TraceMode, int] = {
    "disabled": 0,
    "minimal": 1,
    "redacted": 2,
    "synthetic_full": 3,
}
_RAW_TRACE_KEYS = {
    "raw",
    "_raw",
    "raw_event",
    "raw_events",
    "event",
    "events",
    "prompt",
    "raw_prompt",
    "model_prompt",
    "full_prompt",
}
_MINIMAL_TRACE_KEYS = {
    "incident_id",
    "node",
    "status",
    "duration_ms",
    "trace_id",
    "run_id",
}


def resolve_trace_mode(
    incident_mode: IncidentMode,
    *,
    settings: OpenclawSettings,
    requested_trace_mode: TraceMode | None = None,
) -> TraceMode:
    """Resolve the safe trace mode for a run.

    The base mode is derived from incident mode. Runtime overrides are allowed
    only when they lower detail; they can never elevate real or private payloads
    to synthetic-full traces.
    """

    if not settings.langsmith_tracing:
        return "disabled"

    base_mode = _BASE_TRACE_MODE[incident_mode]
    if requested_trace_mode is None:
        return base_mode

    if _TRACE_MODE_RANK[requested_trace_mode] <= _TRACE_MODE_RANK[base_mode]:
        return requested_trace_mode
    return base_mode


def mask_trace_payload(
    payload: dict[str, Any],
    *,
    trace_mode: TraceMode,
    redaction_summary: RedactionSummary | None = None,
) -> dict[str, Any]:
    """Return a payload safe for the selected LangSmith trace detail level."""

    if trace_mode == "disabled":
        return {}
    if trace_mode == "minimal":
        return {key: payload[key] for key in _MINIMAL_TRACE_KEYS if key in payload}
    if trace_mode == "synthetic_full":
        return dict(payload)

    compact_payload = _drop_raw_trace_fields(payload)
    redacted_payload = redact_payload(compact_payload).sanitized_payload
    if redaction_summary and redaction_summary.categories:
        redacted_payload["redactions"] = [
            f"<redacted:{category}>" for category in redaction_summary.categories
        ]
    return cast(dict[str, Any], redacted_payload)


def corroborate_prompt_injection(
    *,
    model_prompt_injection_detected: bool,
    redaction_summary: RedactionSummary,
) -> PromptInjectionCorroboration:
    """Cross-check model prompt-injection claims against redaction metadata."""

    redaction_detected = redaction_summary.prompt_injection_detected
    if model_prompt_injection_detected and redaction_detected:
        return "corroborated"
    if model_prompt_injection_detected:
        return "model_asserted_only"
    if redaction_detected:
        return "redaction_detected"
    return "not_detected"


def _drop_raw_trace_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_raw_trace_fields(child)
            for key, child in value.items()
            if key not in _RAW_TRACE_KEYS
        }
    if isinstance(value, list):
        return [_drop_raw_trace_fields(child) for child in value]
    return value
