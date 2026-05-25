"""Hermes-first summary rendering for Sergeant Openclaw v1."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from openclaw_ai_soc.redaction import redact_payload

_SAFE_UNTRUSTED_SUMMARY = "Untrusted evidence text was sanitized before rendering."


def render_summary_node(state: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted summary payload for graph state merging."""

    rendered = render_hermes_summary(state)
    raw_summary = state.get("summary")
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    return {
        "summary": {
            "short": _safe_summary_text(
                summary.get("short"),
                fallback=_fallback_short(state),
                state=state,
            ),
            "details": _safe_summary_text(
                summary.get("details"),
                fallback=_fallback_details(state),
                state=state,
            ),
            "rendered_text": rendered,
        }
    }


def render_hermes_summary(state: dict[str, Any]) -> str:
    """Render the v1 handoff surface without raw events, prompts, or secrets."""

    safe_state = redact_payload(state).sanitized_payload
    summary = (
        safe_state.get("summary") if isinstance(safe_state.get("summary"), dict) else {}
    )
    findings = _safe_text_list(
        (safe_state.get("analysis") or {}).get("key_findings", [])
    )
    evidence_sources = _evidence_sources(safe_state.get("evidence", []))
    memory_precedent = _memory_precedent(safe_state.get("memory_matches", []))
    actions = _recommended_actions(safe_state.get("recommended_actions", []))
    anchors = _trace_search_anchors(safe_state)
    redaction_notes = _redaction_notes(safe_state)

    short = _safe_summary_text(
        summary.get("short"), fallback=_fallback_short(safe_state), state=safe_state
    )
    details = _safe_summary_text(
        summary.get("details"), fallback=_fallback_details(safe_state), state=safe_state
    )

    incident_id = safe_state.get("incident_id", "unknown")
    classification = safe_state.get("classification") or "inconclusive"
    confidence = safe_state.get("confidence") or "low"
    human_review = str(safe_state.get("human_review_required", True)).lower()
    remediation_executed = str(_remediation_executed(safe_state)).lower()
    memory_status = safe_state.get("memory_write_status", "not_attempted")
    notification_status = safe_state.get("notification_status", "not_configured")

    lines = [
        "Sergeant Openclaw investigation summary",
        f"Incident: {incident_id}",
        f"Classification: {classification}",
        f"Confidence: {confidence}",
        f"Human review required: {human_review}",
        f"Remediation executed: {remediation_executed}",
        f"incident_id: {incident_id}",
        f"classification: {classification}",
        f"confidence: {confidence}",
        f"investigation_status: {safe_state.get('investigation_status', 'unknown')}",
        f"top_findings: {_join_or_none(findings)}",
        f"evidence_sources: {_join_or_none(evidence_sources)}",
        f"memory_precedent: {_join_or_none(memory_precedent)}",
        f"recommended_actions: {_join_or_none(actions)}",
        f"human_review_required: {human_review}",
        f"remediation_executed: {remediation_executed}",
        f"trace/search anchors: {_join_or_none(anchors)}",
        f"summary_short: {short}",
        f"summary_details: {details}",
        f"redaction_notes: {_join_or_none(redaction_notes)}",
        f"memory_write_status: {memory_status}",
        f"notification_status: {notification_status}",
    ]
    return "\n".join(lines)


def _fallback_short(state: dict[str, Any]) -> str:
    return (
        "Openclaw classified incident as "
        f"{state.get('classification') or 'inconclusive'} "
        f"({state.get('confidence') or 'low'})."
    )


def _fallback_details(state: dict[str, Any]) -> str:
    return (
        "Review curated Splunk evidence anchors, Graphiti precedent, and "
        "non-executed recommendations in Hermes."
    )


def _evidence_sources(evidence: Any) -> list[str]:
    sources: list[str] = []
    if not isinstance(evidence, list):
        return sources
    for item in evidence:
        if not isinstance(item, dict):
            continue
        parts = [str(item.get("kind") or "evidence")]
        if item.get("template_id"):
            parts.append(str(item["template_id"]))
        summary = _safe_summary_text(
            item.get("summary"), fallback="summary unavailable", state=item
        )
        parts.append(summary)
        sources.append(" | ".join(parts))
    return sources


def _memory_precedent(matches: Any) -> list[str]:
    precedent: list[str] = []
    if not isinstance(matches, list):
        return precedent
    for match in matches:
        if not isinstance(match, dict):
            continue
        case_id = str(match.get("case_id") or "case-unknown")
        relevance = str(match.get("relevance") or "unknown")
        classification = str(match.get("classification") or "unclassified")
        summary = _safe_summary_text(
            match.get("summary"), fallback="summary unavailable", state=match
        )
        precedent.append(f"{case_id} ({relevance}, {classification}): {summary}")
    return precedent


def _recommended_actions(actions: Any) -> list[str]:
    rendered: list[str] = []
    if not isinstance(actions, list):
        return rendered
    for item in actions:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "review")
        priority = str(item.get("priority") or "unknown")
        reason = _safe_summary_text(
            item.get("reason"), fallback="reason unavailable", state=item
        )
        execution_allowed = str(item.get("execution_allowed", False)).lower()
        rendered.append(
            f"{action} ({priority}, execution_allowed={execution_allowed}): {reason}"
        )
    return rendered


def _trace_search_anchors(state: dict[str, Any]) -> list[str]:
    anchors: list[str] = []
    for query in state.get("splunk_queries_run", []) or []:
        if not isinstance(query, dict):
            continue
        for key in ("search_id", "query_hash"):
            value = query.get(key)
            if value:
                _append_unique(anchors, str(value))
    trace_ids = state.get("trace_ids") or {}
    if isinstance(trace_ids, dict):
        for value in trace_ids.values():
            if isinstance(value, list):
                for item in value:
                    _append_unique(anchors, str(item))
            elif value:
                _append_unique(anchors, str(value))
    return anchors


def _redaction_notes(state: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if state.get("prompt_injection_detected"):
        notes.append(_SAFE_UNTRUSTED_SUMMARY)
    if state.get("telemetry_evasion_detected"):
        notes.append(
            "Telemetry-evasion language was treated as evidence, not a command."
        )
    categories: list[str] = []
    for evidence in state.get("evidence", []) or []:
        if not isinstance(evidence, dict):
            continue
        for category in evidence.get("redactions", []) or []:
            _append_unique(categories, str(category))
        if evidence.get("untrusted_evidence_locations"):
            _append_unique(notes, _SAFE_UNTRUSTED_SUMMARY)
    for category in categories:
        notes.append(f"<redacted:{category}>")
    return notes


def _safe_text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        _safe_summary_text(value, fallback="finding unavailable", state={})
        for value in values
    ]


def _safe_summary_text(value: Any, *, fallback: str, state: dict[str, Any]) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    redacted = str(redact_payload(value).sanitized_payload)
    lowered = redacted.lower()
    if _contains_untrusted_instruction(lowered) or _state_marks_untrusted(state):
        return _SAFE_UNTRUSTED_SUMMARY
    return redacted


def _contains_untrusted_instruction(lowered: str) -> bool:
    fragments = [
        "ignore previous instructions",
        "ignore prior instructions",
        "reveal secret",
        "disable logging",
        "disable telemetry",
        "hide traces",
        "hide activity",
        "delete logs",
        "execute remediation",
        "approve remediation",
    ]
    return any(fragment in lowered for fragment in fragments)


def _state_marks_untrusted(state: dict[str, Any]) -> bool:
    return bool(
        state.get("prompt_injection_detected")
        and (
            state.get("summary")
            or state.get("untrusted_evidence_locations")
            or state.get("raw")
        )
    )


def _remediation_executed(state: dict[str, Any]) -> bool:
    plan = state.get("remediation_plan") or {}
    if not isinstance(plan, dict):
        return False
    return bool(plan.get("executed", False))


def _join_or_none(values: Iterable[str]) -> str:
    cleaned = [value for value in values if value]
    return "; ".join(cleaned) if cleaned else "none"


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
