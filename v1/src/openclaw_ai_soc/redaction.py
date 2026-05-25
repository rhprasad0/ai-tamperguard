"""Pure redaction helpers for Openclaw payload safety gates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

T = TypeVar("T")

RedactionCategory = Literal[
    "bearer_token",
    "api_key",
    "password",
    "private_key_block",
    "jwt",
    "cookie",
    "splunk_session_key",
    "oauth_refresh_token",
]


@dataclass(frozen=True)
class RedactionFinding:
    """Safe metadata about one redaction, without the original secret value."""

    category: RedactionCategory
    location: str


@dataclass(frozen=True)
class RedactionSummary:
    """Safe summary of redaction and untrusted-evidence findings."""

    secrets_removed: bool = False
    categories: list[RedactionCategory] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    redaction_count: int = 0
    findings: list[RedactionFinding] = field(default_factory=list)
    prompt_injection_detected: bool = False
    telemetry_evasion_detected: bool = False
    untrusted_evidence_locations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RedactionResult:
    """Sanitized payload plus safe redaction metadata."""

    sanitized_payload: Any
    summary: RedactionSummary


@dataclass(frozen=True)
class _RedactionRule:
    category: RedactionCategory
    pattern: re.Pattern[str]
    replacement: str


_OPENAI_KEY_PATTERN = r"\b" + "s" + r"k-(?:proj-)?[A-Za-z0-9_-]{20,}"

_REDACTION_RULES: tuple[_RedactionRule, ...] = (
    _RedactionRule(
        "private_key_block",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "<redacted:private_key_block>",
    ),
    _RedactionRule(
        "bearer_token",
        re.compile(r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9_./+=-]{20,}"),
        "Authorization: <redacted:bearer_token>",
    ),
    _RedactionRule(
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_./+=-]{20,}"),
        "<redacted:bearer_token>",
    ),
    _RedactionRule(
        "oauth_refresh_token",
        re.compile(r"(?i)\b(refresh_token)\s*=\s*[^\s,;}\]]{12,}"),
        r"\1=<redacted:oauth_refresh_token>",
    ),
    _RedactionRule(
        "api_key",
        re.compile(_OPENAI_KEY_PATTERN),
        "<redacted:api_key>",
    ),
    _RedactionRule(
        "api_key",
        re.compile(r"(?i)\b(api[_-]?key)\s*=\s*[^\s,;}\]]{20,}"),
        r"\1=<redacted:api_key>",
    ),
    _RedactionRule(
        "password",
        re.compile(r"(?i)\b(password|passwd|pwd)\s*=\s*[^\s,;}\]]+"),
        r"\1=<redacted:password>",
    ),
    _RedactionRule(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
        "<redacted:jwt>",
    ),
    _RedactionRule(
        "cookie",
        re.compile(r"(?i)\b(sessionid|session|csrftoken|cookie)\s*=\s*[^\s,;}\]]+"),
        r"\1=<redacted:cookie>",
    ),
    _RedactionRule(
        "splunk_session_key",
        re.compile(r"\bsplunkd_[A-Za-z0-9_-]{20,}\b"),
        "<redacted:splunk_session_key>",
    ),
)

_PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bignore (?:all )?(?:previous|prior) instructions\b"),
    re.compile(r"(?i)\breveal secrets?\b"),
    re.compile(r"(?i)\bdo not follow (?:the )?(?:system|developer|policy)\b"),
    re.compile(r"(?i)\boverride (?:the )?(?:system|developer|policy)\b"),
)

_TELEMETRY_EVASION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bdisable (?:the )?(?:telemetry|logging|logs|monitoring)\b"),
    re.compile(r"(?i)\bhide (?:this|activity|evidence|traces?)\b"),
    re.compile(r"(?i)\bdelete (?:the )?(?:evidence|logs|traces?)\b"),
    re.compile(r"(?i)\bmake this quieter\b"),
)


def redact_payload(payload: Any) -> RedactionResult:
    """Return a sanitized copy of a payload and safe metadata.

    The redactor is pure: it recursively copies JSON-like payloads, replaces
    secret-shaped substrings with deterministic category markers, and records
    safe locations/categories without storing original values.
    """
    findings: list[RedactionFinding] = []
    untrusted_locations: list[str] = []
    prompt_injection_detected = False
    telemetry_evasion_detected = False

    def redact_value(value: Any, location: str) -> Any:
        nonlocal prompt_injection_detected, telemetry_evasion_detected

        if isinstance(value, dict):
            return {
                key: redact_value(child, f"{location}.{key}")
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [
                redact_value(child, f"{location}[{index}]")
                for index, child in enumerate(value)
            ]
        if isinstance(value, tuple):
            return tuple(
                redact_value(child, f"{location}[{index}]")
                for index, child in enumerate(value)
            )
        if not isinstance(value, str):
            return value

        text = value
        if any(pattern.search(text) for pattern in _PROMPT_INJECTION_PATTERNS):
            prompt_injection_detected = True
            _append_unique(untrusted_locations, location)
        if any(pattern.search(text) for pattern in _TELEMETRY_EVASION_PATTERNS):
            telemetry_evasion_detected = True
            _append_unique(untrusted_locations, location)

        redacted = text
        for rule in _REDACTION_RULES:
            redacted, count = rule.pattern.subn(rule.replacement, redacted)
            for _ in range(count):
                findings.append(
                    RedactionFinding(category=rule.category, location=location)
                )
        return redacted

    sanitized_payload = redact_value(payload, "$")
    categories = _unique_preserving_order([finding.category for finding in findings])
    locations = _unique_preserving_order([finding.location for finding in findings])
    summary = RedactionSummary(
        secrets_removed=bool(findings),
        categories=categories,
        locations=locations,
        redaction_count=len(findings),
        findings=findings,
        prompt_injection_detected=prompt_injection_detected,
        telemetry_evasion_detected=telemetry_evasion_detected,
        untrusted_evidence_locations=untrusted_locations,
    )
    return RedactionResult(sanitized_payload=sanitized_payload, summary=summary)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _unique_preserving_order(values: list[T]) -> list[T]:  # noqa: UP047
    unique_values: list[T] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return unique_values
