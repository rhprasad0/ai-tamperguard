"""Curated SPL template registry and renderer.

This module intentionally exposes only template-id based rendering. It does not
accept model-authored raw SPL; callers must select an allowlisted template and
supply declared, field-typed params.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Any, cast

import yaml


class CuratedTemplateError(ValueError):
    """Raised when a curated Splunk template request fails closed."""


@dataclass(frozen=True)
class SplunkTemplate:
    """One allowlisted SPL template definition."""

    template_id: str
    description: str
    params: dict[str, str]
    allowed_indexes: tuple[str, ...]
    default_earliest: str
    max_window: str
    max_results: int
    risk: str
    query: str


@dataclass(frozen=True)
class RenderedSplunkQuery:
    """Bounded rendered query metadata for later Splunk execution."""

    template_id: str
    query: str
    earliest: str
    latest: str
    max_results: int
    allowed_indexes: tuple[str, ...]
    risk: str


_TEMPLATE_PATH = Path(__file__).with_name("templates.yaml")
_DURATION_RE = re.compile(r"^-?(?P<amount>[1-9][0-9]*)(?P<unit>[mhd])$")
_SAFE_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "host": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$"),
    "user": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@\\-]{0,127}$"),
    "process": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+-]{0,127}$"),
    "source": re.compile(r"^[A-Za-z0-9_./:-]{1,255}$"),
    "sourcetype": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
    "scenario_id": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"),
    "service_name": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"),
}
_INDEX_RE = re.compile(r"^_?[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_RISK_VALUES = {"standard", "elevated"}


def load_template_registry() -> dict[str, SplunkTemplate]:
    """Load the packaged YAML registry as immutable template objects."""

    return dict(_load_template_registry_cached())


@lru_cache(maxsize=1)
def _load_template_registry_cached() -> dict[str, SplunkTemplate]:
    raw = yaml.safe_load(_TEMPLATE_PATH.read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("templates"), list):
        raise CuratedTemplateError("templates.yaml must contain a templates list")

    registry: dict[str, SplunkTemplate] = {}
    for item in raw["templates"]:
        template = _parse_template(item)
        if template.template_id in registry:
            raise CuratedTemplateError(f"duplicate template id: {template.template_id}")
        registry[template.template_id] = template

    return registry


def default_template_ids() -> tuple[str, ...]:
    """Return standard-risk templates allowed for default v1 selection."""

    return tuple(
        template_id
        for template_id, template in load_template_registry().items()
        if template.risk == "standard"
    )


def render_curated_query(
    template_id: str,
    params: dict[str, Any],
    *,
    earliest: str | None = None,
    latest: str = "now",
    max_results: int | None = None,
    allow_elevated: bool = False,
) -> RenderedSplunkQuery:
    """Render an allowlisted template with declared typed parameters only."""

    registry = load_template_registry()
    if template_id not in registry:
        raise CuratedTemplateError(f"unknown template: {template_id}")

    template = registry[template_id]
    if template.risk == "elevated" and not allow_elevated:
        raise CuratedTemplateError(
            f"template {template_id} is elevated and requires an approval gate"
        )

    earliest = earliest or template.default_earliest
    _validate_duration(earliest, field_name="earliest")
    _validate_latest(latest)
    if _duration_minutes(earliest) > _duration_minutes(template.max_window):
        raise CuratedTemplateError("earliest exceeds template max_window")

    effective_max_results = (
        max_results if max_results is not None else template.max_results
    )
    if effective_max_results <= 0 or effective_max_results > template.max_results:
        raise CuratedTemplateError("max_results exceeds template bounds")

    sanitized_params = _validate_params(template, params)
    indexes = " OR ".join(f"index={index}" for index in template.allowed_indexes)
    body = template.query.format(**sanitized_params)
    query = (
        f"search ({indexes}) earliest={earliest} latest={latest} "
        f"{body} | head {effective_max_results}"
    )

    return RenderedSplunkQuery(
        template_id=template.template_id,
        query=" ".join(query.split()),
        earliest=earliest,
        latest=latest,
        max_results=effective_max_results,
        allowed_indexes=template.allowed_indexes,
        risk=template.risk,
    )


def _parse_template(raw: Any) -> SplunkTemplate:
    if not isinstance(raw, dict):
        raise CuratedTemplateError("template definitions must be mappings")

    required_fields = {
        "template_id",
        "description",
        "params",
        "allowed_indexes",
        "default_earliest",
        "max_window",
        "max_results",
        "risk",
        "query",
    }
    missing = required_fields - raw.keys()
    if missing:
        raise CuratedTemplateError(f"template missing fields: {sorted(missing)}")

    template_id = _validate_identifier(raw["template_id"], "template_id")
    description = _validate_non_empty(raw["description"], "description")
    params = _validate_param_declarations(raw["params"])
    allowed_indexes = _validate_allowed_indexes(raw["allowed_indexes"])
    default_earliest = _validate_duration(raw["default_earliest"], "default_earliest")
    max_window = _validate_duration(raw["max_window"], "max_window")
    max_results = _validate_max_results(raw["max_results"])
    risk = _validate_risk(raw["risk"])
    query = _validate_non_empty(raw["query"], "query")

    return SplunkTemplate(
        template_id=template_id,
        description=description,
        params=params,
        allowed_indexes=allowed_indexes,
        default_earliest=default_earliest,
        max_window=max_window,
        max_results=max_results,
        risk=risk,
        query=query,
    )


def _validate_params(
    template: SplunkTemplate, params: dict[str, Any]
) -> dict[str, str]:
    if not isinstance(params, dict):
        raise CuratedTemplateError("params must be a mapping")

    declared = set(template.params)
    supplied = set(params)
    undeclared = supplied - declared
    if undeclared:
        raise CuratedTemplateError(f"undeclared params: {sorted(undeclared)}")

    missing = declared - supplied
    if missing:
        raise CuratedTemplateError(f"missing params: {sorted(missing)}")

    return {
        name: _validate_field_value(name, field_type, params[name])
        for name, field_type in template.params.items()
    }


def _validate_field_value(name: str, field_type: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise CuratedTemplateError(f"{name} must be a non-empty string")

    if field_type == "ip":
        try:
            return str(ip_address(value))
        except ValueError as exc:
            raise CuratedTemplateError(f"{name} must be a valid IP address") from exc

    pattern = _SAFE_FIELD_PATTERNS.get(field_type)
    if pattern is None:
        raise CuratedTemplateError(f"unknown field validator: {field_type}")
    if not pattern.fullmatch(value):
        raise CuratedTemplateError(f"{name} failed {field_type} validation")

    return f'"{value}"'


def _validate_param_declarations(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise CuratedTemplateError("params must be a mapping")

    params: dict[str, str] = {}
    allowed_types = set(_SAFE_FIELD_PATTERNS) | {"ip"}
    for name, field_type in value.items():
        param_name = _validate_identifier(name, "param name")
        if field_type not in allowed_types:
            raise CuratedTemplateError(f"unsupported field type for {param_name}")
        params[param_name] = field_type
    return params


def _validate_allowed_indexes(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CuratedTemplateError("allowed_indexes must be a non-empty list")
    indexes: list[str] = []
    for index in value:
        if not isinstance(index, str) or not _INDEX_RE.fullmatch(index):
            raise CuratedTemplateError("allowed_indexes contain an invalid index name")
        if index == "*":
            raise CuratedTemplateError("wildcard indexes are not allowed")
        indexes.append(index)
    return tuple(indexes)


def _validate_identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,127}", value):
        raise CuratedTemplateError(f"{field_name} must be a safe identifier")
    return value


def _validate_non_empty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CuratedTemplateError(f"{field_name} must be non-empty text")
    return value.strip()


def _validate_duration(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _DURATION_RE.fullmatch(value):
        raise CuratedTemplateError(f"{field_name} must be a bounded duration")
    if value.startswith("-"):
        return value
    return value


def _validate_latest(value: str) -> None:
    if value == "now":
        return
    _validate_duration(value, "latest")


def _duration_minutes(value: str) -> int:
    match = _DURATION_RE.fullmatch(value)
    if match is None:
        raise CuratedTemplateError("duration must be bounded")

    amount = int(match.group("amount"))
    unit = match.group("unit")
    if unit == "m":
        return amount
    if unit == "h":
        return amount * 60
    return amount * 24 * 60


def _validate_max_results(value: Any) -> int:
    if not isinstance(value, int) or value <= 0 or value > 100:
        raise CuratedTemplateError("max_results must be between 1 and 100")
    return value


def _validate_risk(value: Any) -> str:
    if value not in _RISK_VALUES:
        raise CuratedTemplateError("risk must be standard or elevated")
    return cast(str, value)
