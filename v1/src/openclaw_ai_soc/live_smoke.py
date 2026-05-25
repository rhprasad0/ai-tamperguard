"""Opt-in guardrails for Sergeant Openclaw live LAN smoke checks.

The helpers in this module are intentionally boring: they prove that live checks
are gated, target only the v1 LAN endpoints, and redact values before anything
can be printed. They do not read .env by default and do not construct network
clients until the explicit process-env gate has passed.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import urlparse

import pytest

from openclaw_ai_soc.config import OpenclawSettings

LIVE_TEST_ENV_VAR = "AI_SOC_LIVE_TESTS"
ALLOWED_LAN_HOSTS = frozenset({"kube1.lan", "192.168.0.101", "192.168.0.102"})
_SECRET_PATTERN = re.compile(
    r"sk" + r"-[A-Za-z0-9_-]+|xox[baprs]-[A-Za-z0-9-]+|"
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|"
    r"Bearer\s+[A-Za-z0-9._-]+|"
    r"(password|token|api[_-]?key|secret)=\S+",
    re.IGNORECASE,
)


def live_tests_enabled(environ: dict[str, str] | None = None) -> bool:
    """Return true only for the single supported live-smoke process env gate."""

    source = os.environ if environ is None else environ
    return source.get(LIVE_TEST_ENV_VAR) == "1"


def require_live_gate(environ: dict[str, str] | None = None) -> None:
    """Skip unless the operator explicitly set AI_SOC_LIVE_TESTS=1."""

    if not live_tests_enabled(environ):
        pytest.skip("live LAN smoke tests require AI_SOC_LIVE_TESTS=1")


def live_smoke_target_hosts(settings: OpenclawSettings | None = None) -> set[str]:
    """Return the spec-defined LAN hosts that live smoke is allowed to touch."""

    active_settings = settings or OpenclawSettings()
    return {
        _host_from_url(active_settings.openai_base_url),
        _host_from_url(active_settings.graphiti_mcp_url),
        _host_from_url(active_settings.splunk_host),
    }


def assert_endpoint_allowed(
    endpoint: str, resolved_hosts: Iterable[str] | None = None
) -> None:
    """Fail closed if an endpoint host or DNS result is outside the LAN allowlist."""

    endpoint_host = _host_from_url(endpoint)
    candidates = {endpoint_host, *(resolved_hosts or [])}
    outside = sorted(host for host in candidates if host not in ALLOWED_LAN_HOSTS)
    if outside:
        safe_hosts = ", ".join(redact_for_output(host) for host in outside)
        raise ValueError(f"endpoint resolves outside allowed LAN hosts: {safe_hosts}")


def build_live_clients(
    *,
    settings: OpenclawSettings | None = None,
    constructor_spy: Callable[[str], Any] | None = None,
) -> dict[str, str]:
    """Build minimal live-smoke client descriptors after the explicit gate.

    The returned descriptors are enough for smoke tests and operator diagnostics;
    real clients can be added later behind this same gate. The constructor_spy
    hook exists so tests can prove no live constructor runs before the gate.
    """

    require_live_gate()
    active_settings = settings or OpenclawSettings()

    endpoints = {
        "model_endpoint": active_settings.openai_base_url,
        "graphiti_endpoint": active_settings.graphiti_mcp_url,
        "splunk_endpoint": active_settings.splunk_host,
    }
    for label, endpoint in endpoints.items():
        assert_endpoint_allowed(endpoint)
        if constructor_spy is not None:
            constructor_spy(label)
    return endpoints


def redact_for_output(value: object) -> str:
    """Redact secret-shaped values before placing them in failures or logs."""

    text = str(value)
    if _SECRET_PATTERN.search(text):
        return _SECRET_PATTERN.sub("<redacted:secret>", text)
    return text


def _host_from_url(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    host = parsed.hostname
    if not host:
        raise ValueError("endpoint must include a hostname")
    return host
