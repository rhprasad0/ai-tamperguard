"""Optional summary-only notification stub for v1."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from openclaw_ai_soc.logging import emit_log, get_logger
from openclaw_ai_soc.summary import render_hermes_summary, render_summary_node

_LOGGER = get_logger(__name__)


class SummaryClient(Protocol):
    """Minimal client protocol: send exactly the Hermes summary text."""

    def send_summary(self, body: str) -> str | None: ...


@dataclass(frozen=True)
class NotificationResult:
    """Safe notification result with no raw payload echoes."""

    status: str
    message_id: str | None = None
    error: str | None = None


class SummaryOnlyNotifier:
    """Notification boundary that is disabled by default and summary-only when on."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        client_factory: Callable[[], SummaryClient] | None = None,
    ) -> None:
        self._enabled = enabled
        self._client_factory = client_factory

    def notify(self, summary_text: str) -> NotificationResult:
        """Send summary text if enabled; never build a Slack client when disabled."""

        if not self._enabled:
            return NotificationResult(status="not_configured")
        if self._client_factory is None:
            return NotificationResult(status="not_configured")
        try:
            message_id = self._client_factory().send_summary(summary_text)
        except Exception as exc:  # noqa: BLE001 - notification must not fail graph.
            return NotificationResult(status="failed", error=_safe_error(exc))
        return NotificationResult(status="sent", message_id=message_id)


def notify_summary(
    state: dict,
    *,
    enabled: bool = False,
    client_factory: Callable[[], SummaryClient] | None = None,
) -> dict:
    """Render and optionally send the same redacted Hermes summary text."""

    summary_update = render_summary_node(state)
    summary_text = summary_update["summary"]["rendered_text"]
    result = SummaryOnlyNotifier(enabled=enabled, client_factory=client_factory).notify(
        summary_text
    )
    notification_skipped = result.status in {"not_configured", "skipped"}
    notification_event = (
        "notification.summary.completed"
        if result.status == "sent"
        else "notification.summary.skipped"
        if notification_skipped
        else "notification.summary.failed"
    )
    if result.status == "sent":
        notification_log_status = "ok"
    elif notification_skipped:
        notification_log_status = "skipped"
    else:
        notification_log_status = "failed"
    emit_log(
        _LOGGER,
        event=notification_event,
        component="notify_summary",
        status=notification_log_status,
        incident_id=state.get("incident_id"),
        notification_status=result.status,
        error_code="notification_failed" if result.error else None,
        message=result.error,
    )
    update = {
        "summary": summary_update["summary"],
        "notification_status": result.status,
    }
    if "investigation_status" in state:
        update["investigation_status"] = state["investigation_status"]
    if result.message_id:
        update["trace_ids"] = {
            **state.get("trace_ids", {}),
            "notification_message_id": result.message_id,
        }
    if result.error:
        update["errors"] = [
            *state.get("errors", []),
            {
                "code": "notification_failed",
                "message": result.error,
                "component": "notify_summary",
            },
        ]
    return update


def notify_summary_node(state: dict) -> dict:
    """Default graph node: summary-only notification disabled unless injected."""

    return notify_summary(state, enabled=False)


def _safe_error(exc: Exception) -> str:
    rendered = render_hermes_summary(
        {
            "incident_id": "notification-error",
            "classification": "inconclusive",
            "confidence": "low",
            "investigation_status": "completed",
            "analysis": {"key_findings": [str(exc)]},
            "evidence": [],
            "memory_matches": [],
            "recommended_actions": [],
            "remediation_plan": {"executed": False},
            "human_review_required": True,
            "summary": {"short": str(exc), "details": str(exc)},
            "trace_ids": {},
        }
    )
    for line in rendered.splitlines():
        if line.startswith("top_findings:"):
            return line.removeprefix("top_findings: ")[:240]
    return "notification failed"
