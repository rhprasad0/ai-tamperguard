"""Safe structured logging helpers for Openclaw v1.

Logs are compact operational metadata only. Raw prompts, raw Splunk events,
model responses, credentials, and full state payloads do not belong here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from openclaw_ai_soc.redaction import redact_payload

_FORBIDDEN_LOG_KEYS = {
    "raw",
    "_raw",
    "events",
    "raw_events",
    "raw_event",
    "raw_prompt",
    "prompt",
    "model_response",
    "raw_model_output",
    "full_prompt",
    "messages",
    "state",
    "source_alert",
}

LogStatus = Literal["ok", "failed", "skipped", "started", "completed", "running"]
LogFormat = Literal["json", "plain"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class StructuredLogEvent(BaseModel):
    """Compact metadata event allowed to leave the process through logs."""

    model_config = ConfigDict(extra="forbid")

    event: str
    component: str
    incident_id: str | None = None
    node: str | None = None
    status: LogStatus | str
    duration_ms: int | None = None
    classification: str | None = None
    template_id: str | None = None
    result_count: int | None = None
    memory_write_status: str | None = None
    notification_status: str | None = None
    trace_mode: str | None = None
    group_id: str | None = None
    model_name: str | None = None
    model_endpoint: str | None = None
    search_id: str | None = None
    query_hash: str | None = None
    match_count: int | None = None
    error_code: str | None = None
    message: str | None = None

    @field_validator(
        "event",
        "component",
        "incident_id",
        "node",
        "status",
        "classification",
        "template_id",
        "memory_write_status",
        "notification_status",
        "trace_mode",
        "group_id",
        "model_name",
        "model_endpoint",
        "search_id",
        "query_hash",
        "error_code",
        "message",
    )
    @classmethod
    def reject_secret_shaped_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if "<redacted:" in value:
            return value
        redaction = redact_payload(value)
        if redaction.summary.secrets_removed:
            raise ValueError("structured log event contains a secret-shaped value")
        return value

    @field_validator("duration_ms", "result_count", "match_count")
    @classmethod
    def require_non_negative_int(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("structured log counts and durations must be non-negative")
        return value

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_extra_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        forbidden = set(data) & _FORBIDDEN_LOG_KEYS
        if forbidden:
            raise ValueError("structured logs must not include raw payload fields")
        return data


class JsonLogFormatter(logging.Formatter):
    """Render Openclaw structured log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "openclaw_event", None)
        if isinstance(event, dict):
            payload = {key: value for key, value in event.items() if value is not None}
        else:
            payload = {"event": record.getMessage()}
        payload.setdefault("logger", record.name)
        payload.setdefault("level", record.levelname)
        payload.setdefault("timestamp", self.formatTime(record, self.datefmt))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


class PlainLogFormatter(logging.Formatter):
    """Human-readable formatter for local debugging."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "openclaw_event", None)
        if isinstance(event, dict):
            safe_event = {
                key: value for key, value in event.items() if value is not None
            }
            rendered = json.dumps(safe_event, sort_keys=True)
            return f"{record.levelname} {record.name} {rendered}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """Return a package logger without configuring global handlers."""

    return logging.getLogger(name)


def configure_logging(*, level: str = "INFO", log_format: LogFormat = "json") -> None:
    """Configure root package logging for CLI/manual runs."""

    normalized_level = normalize_log_level(level)
    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    elif log_format == "plain":
        handler.setFormatter(PlainLogFormatter("%(levelname)s %(name)s %(message)s"))
    else:
        raise ValueError("log_format must be json or plain")

    package_logger = logging.getLogger("openclaw_ai_soc")
    package_logger.handlers.clear()
    package_logger.addHandler(handler)
    package_logger.setLevel(normalized_level)
    package_logger.propagate = True


def normalize_log_level(value: str) -> LogLevel:
    """Normalize and validate a logging level name."""

    normalized = value.upper()
    allowed: set[LogLevel] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if normalized not in allowed:
        raise ValueError("AI_SOC_LOG_LEVEL must be a standard logging level")
    return cast(LogLevel, normalized)


def safe_log_extra(values: dict[str, Any]) -> dict[str, Any]:
    """Drop forbidden fields and redact secret-shaped metadata before logging."""

    safe: dict[str, Any] = {}
    for key, value in values.items():
        if key in _FORBIDDEN_LOG_KEYS or key.startswith("raw_"):
            continue
        if isinstance(value, str):
            safe[key] = redact_payload(value).sanitized_payload
        elif isinstance(value, int | float | bool) or value is None:
            safe[key] = value
        else:
            # Keep log records scalar and metadata-only; nested data risks raw
            # payload leaks.
            safe[key] = redact_payload(str(value)).sanitized_payload
    return safe


def emit_log(
    logger: logging.Logger,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Validate and emit one safe structured log event."""

    safe_fields = safe_log_extra(fields)
    event = StructuredLogEvent.model_validate(safe_fields)
    message = f"{event.component}.{event.event}"
    _remove_closed_stream_handlers(logger)
    logger.log(level, message, extra={"openclaw_event": event.model_dump()})


def _remove_closed_stream_handlers(logger: logging.Logger) -> None:
    """Drop stale stream handlers left behind by redirected test streams."""

    current: logging.Logger | None = logger
    while current is not None:
        for handler in list(current.handlers):
            stream = getattr(handler, "stream", None)
            if getattr(stream, "closed", False):
                current.removeHandler(handler)
        current = current.parent if current.propagate else None
