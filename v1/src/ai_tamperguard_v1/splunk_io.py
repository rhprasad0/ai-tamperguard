from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from ai_tamperguard_v1.lab_config import LabConfig

SACRIFICIAL_INDEX = "openclaw_tamper_lab"
FORBIDDEN_EVENT_KEYS = {"_raw", "host", "user", "username", "private_name", "token", "password", "url", "uri"}
REQUIRED_EVENT_KEYS = {"scenario_run_id", "scenario_id", "event_id", "redaction_level"}


@dataclass(frozen=True)
class SplunkWriteResult:
    status: str
    event_count: int
    request_id: str | None = None


@dataclass(frozen=True)
class SplunkSearchResult:
    status: str
    rows: list[dict[str, Any]]


class SplunkIoError(RuntimeError):
    pass


def write_scenario_events_hec(
    *,
    config: LabConfig,
    events: list[dict[str, Any]],
    batch_id: str,
    dry_run: bool = False,
    http_client: Any | None = None,
) -> SplunkWriteResult:
    if config.splunk_hec is None:
        raise SplunkIoError("Splunk HEC config is missing")
    hec = config.splunk_hec
    if hec.index != SACRIFICIAL_INDEX:
        raise SplunkIoError("Splunk HEC target index must be openclaw_tamper_lab")
    _validate_events(events)
    if dry_run:
        return SplunkWriteResult(status="dry_run_validated", event_count=len(events))

    token = os.environ.get(hec.token_env)
    if not token:
        raise SplunkIoError(f"required Splunk HEC token env var is not set: {hec.token_env}")

    close_client = False
    client = http_client
    if client is None:
        import httpx

        client = httpx.Client(timeout=10.0)
        close_client = True
    try:
        request_id: str | None = None
        for event in events:
            payload = {
                "index": hec.index,
                "sourcetype": hec.sourcetype,
                "source": hec.source,
                "event": dict(event, batch_id=batch_id),
            }
            response = client.post(
                hec.url,
                headers={"Authorization": f"Splunk {token}"},
                json=payload,
            )
            if getattr(response, "status_code", 200) >= 300:
                raise SplunkIoError(f"Splunk HEC write failed with status {getattr(response, 'status_code', 'unknown')} at <redacted-endpoint>")
            response_json = _safe_response_json(response)
            request_id = str(response_json.get("request_id") or response_json.get("ackId") or request_id or "") or None
        return SplunkWriteResult(status="written", event_count=len(events), request_id=request_id)
    except SplunkIoError:
        raise
    except Exception as exc:  # pragma: no cover - exercised through fake transport errors
        raise SplunkIoError(f"Splunk HEC write failed at <redacted-endpoint>: {_redacted_exception(exc)}") from exc
    finally:
        if close_client:
            client.close()


def search_scenario_events(
    *,
    config: LabConfig,
    scenario_run_id: str,
    earliest_epoch: int,
    latest: str = "now",
    http_client: Any | None = None,
) -> SplunkSearchResult:
    if config.splunk_search is None:
        raise SplunkIoError("Splunk search config is missing")
    search = config.splunk_search
    token = os.environ.get(search.token_env)
    if not token:
        raise SplunkIoError(f"required Splunk search token env var is not set: {search.token_env}")
    query = f'search index={SACRIFICIAL_INDEX} earliest={int(earliest_epoch)} scenario_run_id="{_escape_spl(scenario_run_id)}"'
    close_client = False
    client = http_client
    if client is None:
        import httpx

        client = httpx.Client(timeout=20.0)
        close_client = True
    try:
        response = client.post(
            search.url,
            headers={"Authorization": f"Bearer {token}"},
            data={"search": query, "output_mode": "json", "latest_time": latest},
        )
        if getattr(response, "status_code", 200) >= 300:
            raise SplunkIoError(f"Splunk search failed with status {getattr(response, 'status_code', 'unknown')} at <redacted-endpoint>")
        rows = _parse_search_rows(response)
        return SplunkSearchResult(status="searched", rows=rows)
    except SplunkIoError:
        raise
    except Exception as exc:  # pragma: no cover
        raise SplunkIoError(f"Splunk search failed at <redacted-endpoint>: {_redacted_exception(exc)}") from exc
    finally:
        if close_client:
            client.close()


def _validate_events(events: list[dict[str, Any]]) -> None:
    for idx, event in enumerate(events, 1):
        missing = REQUIRED_EVENT_KEYS - set(event)
        if missing:
            raise SplunkIoError(f"event {idx} missing required public-safe keys: {', '.join(sorted(missing))}")
        if event.get("redaction_level") != "public_safe":
            raise SplunkIoError(f"event {idx} must have redaction_level=public_safe")
        forbidden = FORBIDDEN_EVENT_KEYS.intersection(event)
        if forbidden:
            raise SplunkIoError(f"event {idx} contains forbidden public-unsafe keys: {', '.join(sorted(forbidden))}")


def _safe_response_json(response: Any) -> dict[str, Any]:
    try:
        value = response.json()
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _parse_search_rows(response: Any) -> list[dict[str, Any]]:
    try:
        value = response.json()
    except Exception:
        text = getattr(response, "text", "")
        rows: list[dict[str, Any]] = []
        for line in str(text).splitlines():
            if not line.strip():
                continue
            parsed = json.loads(line)
            result = parsed.get("result", parsed)
            if isinstance(result, dict):
                rows.append(result)
        return rows
    if isinstance(value, dict):
        if isinstance(value.get("results"), list):
            return [row for row in value["results"] if isinstance(row, dict)]
        if isinstance(value.get("result"), dict):
            return [value["result"]]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _escape_spl(value: str) -> str:
    return value.replace('"', '\\"')


def _redacted_exception(exc: Exception) -> str:
    text = str(exc)
    for marker in ("http://", "https://"):
        if marker in text:
            return "<redacted>"
    return text.replace(os.environ.get("AI_TAMPERGUARD_SPLUNK_HEC_TOKEN", "\0"), "<redacted>")
