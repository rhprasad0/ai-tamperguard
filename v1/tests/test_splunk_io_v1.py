from __future__ import annotations

from pathlib import Path

import pytest

from ai_tamperguard_v1.lab_config import load_lab_config
from ai_tamperguard_v1.scenario_events import public_safe_scenario_events
from ai_tamperguard_v1.splunk_io import SplunkIoError, search_scenario_events, write_scenario_events_hec


def _config(tmp_path: Path, *, hec_index: str = "openclaw_tamper_lab") -> Path:
    private_dir = tmp_path / "splunk" / "private"
    private_dir.mkdir(parents=True)
    cfg = private_dir / "lab.toml"
    cfg.write_text(
        'authorized_lab_marker = "ai_tamperguard_v1_lab"\n'
        'target_namespace = "ai_tamperguard_v1"\n'
        'capture_destination = "data/raw_exports"\n'
        'allowed_indexes = ["_audit", "_configtracker", "openclaw_tamper_lab"]\n'
        'protected_indexes = ["_audit", "_configtracker"]\n'
        'synthetic_evidence_index = "openclaw_tamper_lab"\n'
        '\n[sacrificial]\n'
        'allowed_app = "ai_tamperguard_v1"\n'
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report"]\n'
        '\n[splunk_hec]\n'
        'url = "https://example.invalid/services/collector/event"\n'
        'token_env = "AI_TAMPERGUARD_SPLUNK_HEC_TOKEN"\n'
        f'index = "{hec_index}"\n'
        'sourcetype = "ai_tamperguard:v1:scenario_evidence"\n'
        'source = "ai_tamperguard:v1:seed"\n'
        '\n[splunk_search]\n'
        'url = "https://example.invalid/services/search/jobs/export"\n'
        'token_env = "AI_TAMPERGUARD_SPLUNK_SEARCH_TOKEN"\n',
        encoding="utf-8",
    )
    return cfg


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self.posts = []

    def post(self, *args, **kwargs):
        self.posts.append((args, kwargs))
        return FakeResponse({"request_id": "req_001", "results": [{"event_id": "evt_000004001"}]})


def test_hec_dry_run_validates_without_network(tmp_path: Path) -> None:
    config = load_lab_config(_config(tmp_path))
    events = public_safe_scenario_events(scenario_id="scenario_004", scenario_run_id="scenario_004_run_001")
    fake = FakeClient()

    result = write_scenario_events_hec(config=config, events=events, batch_id="batch_001", dry_run=True, http_client=fake)

    assert result.status == "dry_run_validated"
    assert result.event_count == 3
    assert fake.posts == []


def test_hec_rejects_forbidden_public_unsafe_keys(tmp_path: Path) -> None:
    config = load_lab_config(_config(tmp_path))
    events = public_safe_scenario_events(scenario_id="scenario_004", scenario_run_id="scenario_004_run_001")
    events[0]["private_name"] = "do-not-send"

    with pytest.raises(SplunkIoError, match="forbidden"):
        write_scenario_events_hec(config=config, events=events, batch_id="batch_001", dry_run=True)


def test_hec_posts_only_to_sacrificial_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_lab_config(_config(tmp_path))
    events = public_safe_scenario_events(scenario_id="scenario_007", scenario_run_id="scenario_007_run_001")
    fake = FakeClient()
    monkeypatch.setenv("AI_TAMPERGUARD_SPLUNK_HEC_TOKEN", "secret-token")

    result = write_scenario_events_hec(config=config, events=events, batch_id="batch_001", http_client=fake)

    assert result.status == "written"
    assert len(fake.posts) == 2
    assert all(call[1]["json"]["index"] == "openclaw_tamper_lab" for call in fake.posts)
    assert all("secret-token" not in str(call[1]["json"]) for call in fake.posts)


def test_search_uses_fake_client_and_returns_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_lab_config(_config(tmp_path))
    fake = FakeClient()
    monkeypatch.setenv("AI_TAMPERGUARD_SPLUNK_SEARCH_TOKEN", "secret-token")

    result = search_scenario_events(config=config, scenario_run_id="scenario_004_run_001", earliest_epoch=123, http_client=fake)

    assert result.rows == [{"event_id": "evt_000004001"}]
    data = fake.posts[0][1]["data"]
    assert "index=openclaw_tamper_lab" in data["search"]
    assert "scenario_004_run_001" in data["search"]
