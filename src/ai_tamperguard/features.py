from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from ai_tamperguard.labels import apply_weak_label

FEATURE_COLUMNS = (
    "feature_event_count",
    "feature_search_count",
    "feature_admin_action_count",
    "feature_config_action_count",
    "feature_token_or_rbac_action_count",
    "feature_index_or_input_action_count",
    "feature_failed_action_count",
    "feature_success_action_count",
    "feature_after_hours_admin_activity",
    "feature_distinct_action_category_count",
)
_ADMIN_MARKERS = ("admin", "edit", "create", "delete", "update", "change", "modify", "enable", "disable")
_TOKEN_RBAC_MARKERS = ("token", "role", "rbac", "capability", "permission", "user")
_INDEX_INPUT_MARKERS = ("index", "indexes", "input", "inputs", "forwarder", "sourcetype")
_CONFIG_SOURCETYPES = {"splunk_configuration_change", "configtracker"}
_AUDIT_SOURCETYPES = {"audittrail", "audit"}


def actor_surrogate(raw: Mapping[str, Any], salt: str) -> str:
    """Return a deterministic salted actor surrogate for private grouping."""
    actor = _first_text(raw, ("user", "username", "actor", "user_name", "src_user"), default="unknown")
    digest = hashlib.sha256(f"{salt}:{actor}".encode("utf-8")).hexdigest()
    return f"actor_{digest[:24]}"


def normalize_event(raw: Mapping[str, Any], *, salt: str) -> dict[str, Any]:
    """Normalize a Splunk control-plane event into safe categorical flags."""
    timestamp = _parse_timestamp(raw.get("_time") or raw.get("time") or raw.get("timestamp"))
    source_type = _normalize_text(_first_text(raw, ("sourcetype", "source_type"), default="unknown"))
    action_text = _normalize_text(_first_text(raw, ("action", "operation", "command", "eventtype", "data.action"), default="unknown"))
    object_text = _normalize_text(
        _first_text(
            raw,
            ("object_category", "object_type", "object", "stanza", "component", "data.changes{}.stanza", "data.path"),
            default="",
        )
    )
    status = _normalize_status(_first_text(raw, ("status", "result", "info"), default="unknown"))
    is_config = int(source_type in _CONFIG_SOURCETYPES or "config" in source_type)
    category = _action_category(source_type=source_type, action_text=action_text, object_text=object_text)
    is_token_or_rbac = int(category == "token_or_rbac")
    is_index_or_input = int(category == "index_or_input")
    is_admin = int(is_config or is_token_or_rbac or is_index_or_input or _contains_any(action_text, _ADMIN_MARKERS))
    is_after_hours = int(timestamp.hour < 6 or timestamp.hour >= 18)

    return {
        "timestamp": timestamp.isoformat(),
        "actor_surrogate_private": actor_surrogate(raw, salt),
        "source_type": source_type,
        "action_category": category,
        "status": status,
        "is_admin_action": is_admin,
        "is_config_action": is_config,
        "is_token_or_rbac_action": is_token_or_rbac,
        "is_index_or_input_action": is_index_or_input,
        "is_after_hours": is_after_hours,
    }


def build_actor_60m_windows(
    events: Iterable[Mapping[str, Any]],
    *,
    salt: str,
    source_dataset: str,
) -> list[dict[str, Any]]:
    """Aggregate normalized Splunk control-plane events into actor_60m windows."""
    return build_actor_windows(events, salt=salt, source_dataset=source_dataset, window_minutes=60)


def build_actor_windows(
    events: Iterable[Mapping[str, Any]],
    *,
    salt: str,
    source_dataset: str,
    window_minutes: int,
) -> list[dict[str, Any]]:
    """Aggregate normalized Splunk control-plane events into actor windows."""
    if window_minutes not in {15, 60}:
        raise ValueError("window_minutes must be 15 or 60")
    groups: dict[tuple[str, datetime], list[dict[str, Any]]] = defaultdict(list)
    for raw in events:
        normalized = normalize_event(raw, salt=salt)
        timestamp = datetime.fromisoformat(normalized["timestamp"])
        bucket_minute = (timestamp.minute // window_minutes) * window_minutes
        window_start = timestamp.replace(minute=bucket_minute, second=0, microsecond=0)
        groups[(normalized["actor_surrogate_private"], window_start)].append(normalized)

    window_type = f"actor_{window_minutes}m"
    windows: list[dict[str, Any]] = []
    for (actor, window_start), rows in sorted(groups.items(), key=lambda item: (item[0][1], item[0][0])):
        window_end = window_start + timedelta(minutes=window_minutes)
        action_categories = {str(row["action_category"]) for row in rows}
        features = {
            "feature_event_count": len(rows),
            "feature_search_count": sum(1 for row in rows if row["action_category"] == "search"),
            "feature_admin_action_count": sum(int(row["is_admin_action"]) for row in rows),
            "feature_config_action_count": sum(int(row["is_config_action"]) for row in rows),
            "feature_token_or_rbac_action_count": sum(int(row["is_token_or_rbac_action"]) for row in rows),
            "feature_index_or_input_action_count": sum(int(row["is_index_or_input_action"]) for row in rows),
            "feature_failed_action_count": sum(1 for row in rows if row["status"] in {"failure", "failed", "error"}),
            "feature_success_action_count": sum(1 for row in rows if row["status"] in {"success", "succeeded", "modified"}),
            "feature_after_hours_admin_activity": int(
                any(int(row["is_after_hours"]) and int(row["is_admin_action"]) for row in rows)
            ),
            "feature_distinct_action_category_count": len(action_categories),
        }
        window = {
            "window_id": f"{window_type}:{_format_z(window_start)}:{actor}",
            "window_type": window_type,
            "window_start": _format_z(window_start),
            "window_end": _format_z(window_end),
            "source_dataset": source_dataset,
            "actor_surrogate_private": actor,
            **features,
        }
        windows.append(apply_weak_label(window))
    return windows


def _parse_timestamp(value: Any) -> datetime:
    if value is None or value == "":
        raise ValueError("event is missing _time")
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    text = str(value).strip()
    if _is_epoch_text(text):
        return datetime.fromtimestamp(float(text), tz=UTC)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def _normalize_text(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized or "unknown"


def _normalize_status(value: str) -> str:
    status = _normalize_text(value)
    if status in {"success", "succeeded", "ok", "allow", "allowed"}:
        return "success"
    if status in {"failure", "failed", "fail", "error", "deny", "denied"}:
        return "failure"
    return status


def _first_text(raw: Mapping[str, Any], keys: Iterable[str], *, default: str) -> str:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _action_category(*, source_type: str, action_text: str, object_text: str) -> str:
    haystack = f"{action_text} {object_text}"
    if _contains_any(haystack, _TOKEN_RBAC_MARKERS):
        return "token_or_rbac"
    if _contains_any(haystack, _INDEX_INPUT_MARKERS):
        return "index_or_input"
    if source_type in _CONFIG_SOURCETYPES or "config" in source_type:
        return "config"
    if source_type in _AUDIT_SOURCETYPES and "search" in action_text:
        return "search"
    if _contains_any(haystack, _ADMIN_MARKERS):
        return "admin"
    return "other"


def _is_epoch_text(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return text.replace(".", "", 1).isdigit()


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)
