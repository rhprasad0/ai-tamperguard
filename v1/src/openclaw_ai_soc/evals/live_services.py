"""Gated live service adapters for full-LAN nondeterministic evals.

This module is imported only after the explicit live eval gate has passed. The
adapters keep the graph on existing safe boundaries: curated Splunk templates,
Graphiti precedent lookup with writes disabled by default, compact LLM payloads,
and summary-only notifications.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urljoin

import httpx

from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.live_smoke import assert_endpoint_allowed, redact_for_output
from openclaw_ai_soc.llm import LLMBridgeClient
from openclaw_ai_soc.memory.graphiti import GraphitiMemoryClient
from openclaw_ai_soc.nodes import (
    ServiceBundle,
    collect_splunk_evidence,
    notify_summary_node,
)
from openclaw_ai_soc.splunk.client import SplunkTemplateClient, TransportSearchResult


def build_live_full_lan_services(
    *,
    settings: OpenclawSettings,
    counters: dict[str, int],
    graphiti_write: bool = False,
    temperature: float = 0.1,
) -> ServiceBundle:
    """Construct full live-LAN eval services with conservative defaults.

    The caller is responsible for enforcing ``AI_SOC_LIVE_TESTS=1`` before this
    function is imported/called. This factory still validates endpoints and
    placeholder credentials before constructing network clients.
    """

    _validate_safe_settings(settings)
    assert_endpoint_allowed(settings.splunk_host)
    assert_endpoint_allowed(settings.graphiti_mcp_url)
    assert_endpoint_allowed(settings.openai_base_url)

    splunk_transport = SplunkRestTransport(settings=settings)
    graphiti_transport = GraphitiMcpTransport(settings=settings)
    llm_client = LLMBridgeClient(settings=settings, temperature=temperature)
    return ServiceBundle(
        splunk=CountingSplunkService(
            counters=counters,
            client=SplunkTemplateClient(transport=splunk_transport, settings=settings),
            settings=settings,
        ),
        graphiti=CountingGraphitiService(
            counters=counters,
            client=GraphitiMemoryClient(
                settings=settings,
                transport=graphiti_transport,
            ),
            write_enabled=graphiti_write,
        ),
        llm=CountingLLMService(counters=counters, client=llm_client),
        notifier=SummaryOnlyNotifier(counters=counters),
    )


class CountingSplunkService:
    """Splunk graph boundary that counts calls and returns compact evidence."""

    def __init__(
        self,
        *,
        counters: dict[str, int],
        client: SplunkTemplateClient,
        settings: OpenclawSettings,
    ) -> None:
        self.counters = counters
        self.client = client
        self.settings = settings

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.counters["splunk"] += 1
        return collect_splunk_evidence(
            state,
            splunk_client=self.client,
            settings=self.settings,
        )


class CountingGraphitiService:
    """Graphiti graph boundary; writes are opt-in and skipped by default."""

    def __init__(
        self,
        *,
        counters: dict[str, int],
        client: GraphitiMemoryClient,
        write_enabled: bool,
    ) -> None:
        self.counters = counters
        self.client = client
        self.write_enabled = write_enabled
        self.written_payloads: list[dict[str, Any]] = []

    async def lookup(self, state: dict[str, Any]) -> dict[str, Any]:
        from openclaw_ai_soc.memory.graphiti import lookup_graphiti_precedents

        self.counters["graphiti_lookup"] += 1
        return await lookup_graphiti_precedents(state, memory_client=self.client)

    async def write(self, state: dict[str, Any]) -> dict[str, Any]:
        if not self.write_enabled:
            return {"memory_write_status": "skipped"}

        from openclaw_ai_soc.memory.graphiti import (
            build_case_law_payload,
            write_case_law_memory,
        )

        self.counters["graphiti_write"] += 1
        payload = build_case_law_payload(state).model_dump()
        self.written_payloads.append(payload)
        return await write_case_law_memory(state, memory_client=self.client)


class CountingLLMService:
    """LLM graph boundary that records one model-analysis call per invocation."""

    def __init__(self, *, counters: dict[str, int], client: LLMBridgeClient) -> None:
        self.counters = counters
        self.client = client

    def analyze(self, state: dict[str, Any]) -> Any:
        self.counters["llm"] += 1
        return self.client.analyze(state)


class SummaryOnlyNotifier:
    """Summary-only notifier; no Slack or remediation side effects."""

    def __init__(self, *, counters: dict[str, int]) -> None:
        self.counters = counters

    def notify(self, state: dict[str, Any]) -> dict[str, Any]:
        self.counters["notifier"] += 1
        return notify_summary_node(state)


class SplunkRestTransport:
    """Minimal Splunk REST transport for already-rendered curated SPL."""

    def __init__(self, *, settings: OpenclawSettings, timeout: float = 30.0) -> None:
        self.settings = settings
        self.timeout = timeout
        self.base_url = settings.splunk_host.rstrip("/") + "/"
        self.mcp_url = urljoin(self.base_url, "services/mcp")
        self._mcp_token = os.environ.get("MCP_SPLUNK_MCP_SERVER_API_KEY")
        self._use_mcp = _is_placeholder(settings.splunk_token) and bool(
            self._mcp_token
        )

    def run_search(
        self, *, query: str, earliest: str, latest: str, max_results: int
    ) -> TransportSearchResult:
        if self._use_mcp:
            return self._run_search_via_mcp(
                query=query,
                earliest=earliest,
                latest=latest,
                max_results=max_results,
            )

        endpoint = urljoin(self.base_url, "services/search/jobs/export")
        headers: dict[str, str] = {}
        auth: tuple[str, str] | None = None
        if not _is_placeholder(settings_value := self.settings.splunk_token):
            headers["Authorization"] = f"Bearer {settings_value}"
        else:
            auth = (self.settings.splunk_username, self.settings.splunk_password)

        request_kwargs: dict[str, Any] = {
            "data": {
                "search": query,
                "earliest_time": earliest,
                "latest_time": latest,
                "output_mode": "json",
                "count": str(max_results),
            },
            "headers": headers,
        }
        if auth is not None:
            request_kwargs["auth"] = auth

        try:
            with httpx.Client(verify=False, timeout=self.timeout) as client:
                response = client.post(endpoint, **request_kwargs)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"splunk REST search failed: {redact_for_output(exc)}"
            ) from exc

        results: list[dict[str, Any]] = []
        search_id: str | None = None
        for line in response.text.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("sid") and search_id is None:
                search_id = str(payload["sid"])
            result = payload.get("result")
            if isinstance(result, dict):
                results.append(result)
                if len(results) >= max_results:
                    break
        return TransportSearchResult(search_id=search_id, results=results)

    def _run_search_via_mcp(
        self, *, query: str, earliest: str, latest: str, max_results: int
    ) -> TransportSearchResult:
        headers = {
            "Authorization": f"Bearer {self._mcp_token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "splunk_run_query",
                "arguments": {
                    "query": query,
                    "earliest_time": earliest,
                    "latest_time": latest,
                    "row_limit": max_results,
                },
            },
        }
        try:
            with httpx.Client(verify=False, timeout=self.timeout) as client:
                response = client.post(self.mcp_url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"splunk MCP search failed: {redact_for_output(exc)}"
            ) from exc

        rpc = _decode_rpc_response(response.text)
        if "error" in rpc:
            message = rpc["error"].get("message", "Splunk MCP search failed")
            raise RuntimeError(redact_for_output(message))
        result = _decode_mcp_tool_result(rpc.get("result", {}))
        rows = result.get("results", [])
        if not isinstance(rows, list):
            rows = []
        bounded_rows = [row for row in rows if isinstance(row, dict)][:max_results]
        return TransportSearchResult(search_id=None, results=bounded_rows)


class GraphitiMcpTransport:
    """Tiny streamable-HTTP MCP transport for Graphiti lookup/write tools."""

    def __init__(self, *, settings: OpenclawSettings, timeout: float = 15.0) -> None:
        self.settings = settings
        self.timeout = timeout
        self.url = settings.graphiti_mcp_url
        self._session_id: str | None = None
        self._rpc_id = 0

    async def search_memory_facts(
        self, *, query: str, group_ids: list[str], max_facts: int
    ) -> dict[str, Any]:
        return await self._call_tool(
            "search_memory_facts",
            {"query": query, "group_ids": group_ids, "max_facts": max_facts},
        )

    async def add_memory(
        self,
        *,
        name: str,
        episode_body: str,
        group_id: str,
        source: str,
        source_description: str,
    ) -> dict[str, Any]:
        return await self._call_tool(
            "add_memory",
            {
                "name": name,
                "episode_body": episode_body,
                "group_id": group_id,
                "source": source,
                "source_description": source_description,
            },
        )

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_session()
        response = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in response:
            message = response["error"].get("message", "Graphiti MCP tool failed")
            raise RuntimeError(redact_for_output(message))
        return _decode_mcp_tool_result(response.get("result", {}))

    async def _ensure_session(self) -> None:
        if self._session_id is not None:
            return
        response = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "openclaw-live-eval", "version": "0"},
                },
            },
            initialize=True,
        )
        if "error" in response:
            message = response["error"].get("message", "Graphiti MCP initialize failed")
            raise RuntimeError(redact_for_output(message))
        await self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_response=False,
        )

    async def _post(
        self,
        payload: dict[str, Any],
        *,
        initialize: bool = False,
        expect_response: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._session_id is not None:
            headers["mcp-session-id"] = self._session_id
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers=headers,
                follow_redirects=True,
            )
        if initialize:
            self._session_id = response.headers.get("mcp-session-id")
        response.raise_for_status()
        if not expect_response or not response.content:
            return {}
        return _decode_rpc_response(response.text)

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id


def _decode_rpc_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("data:") or "\ndata:" in stripped:
        for line in stripped.splitlines():
            if line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
                if data and data != "[DONE]":
                    parsed = json.loads(data)
                    return parsed if isinstance(parsed, dict) else {"data": parsed}
        return {}
    parsed = json.loads(stripped)
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _decode_mcp_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text = item["text"]
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return {"text": text}
                if isinstance(parsed, dict):
                    return parsed
                return {"data": parsed}
    if isinstance(result, dict):
        return result
    return {}


def _validate_safe_settings(settings: OpenclawSettings) -> None:
    if settings.ai_soc_remediation_enabled is not False:
        raise ValueError("live-full-lan eval requires remediation disabled")
    # The local Codex bridge is intentionally no-auth in this LAN lab, so
    # placeholder OpenAI/Codex API keys must not block live eval construction.
    splunk_has_mcp_token = bool(os.environ.get("MCP_SPLUNK_MCP_SERVER_API_KEY"))
    splunk_mcp_allowed = (
        os.environ.get("AI_SOC_LIVE_TESTS") == "1" and splunk_has_mcp_token
    )
    if (
        not splunk_mcp_allowed
        and _is_placeholder(settings.splunk_token)
        and (
            _is_placeholder(settings.splunk_username)
            or _is_placeholder(settings.splunk_password)
        )
    ):
        raise ValueError("placeholder credential configured for Splunk access")


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return not normalized or "replace-with" in normalized or normalized in {
        "changeme",
        "placeholder",
        "none",
    }
