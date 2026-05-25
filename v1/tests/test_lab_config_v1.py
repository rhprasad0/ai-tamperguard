from __future__ import annotations

from pathlib import Path

import pytest

from ai_tamperguard_v1.lab_config import (
    LabConfigError,
    load_lab_config,
    load_sacrificial_inventory,
)


def test_load_lab_config_rejects_public_config_path(tmp_path: Path) -> None:
    cfg = tmp_path / "lab.toml"
    cfg.write_text(
        'authorized_lab_marker = "ai_tamperguard_v1_lab"\n'
        'target_namespace = "ai_tamperguard_v1"\n'
        'capture_destination = "data/raw_exports"\n',
        encoding="utf-8",
    )

    with pytest.raises(LabConfigError, match="splunk/private"):
        load_lab_config(cfg)


def test_load_lab_config_requires_mandatory_indexes_and_private_capture_destination(tmp_path: Path) -> None:
    private_dir = tmp_path / "splunk" / "private"
    private_dir.mkdir(parents=True)
    cfg = private_dir / "lab.toml"
    cfg.write_text(
        'authorized_lab_marker = "ai_tamperguard_v1_lab"\n'
        'target_namespace = "ai_tamperguard_v1"\n'
        'capture_destination = "public/raw_exports"\n'
        'allowed_indexes = ["_audit"]\n',
        encoding="utf-8",
    )

    with pytest.raises(LabConfigError) as excinfo:
        load_lab_config(cfg)

    message = str(excinfo.value)
    assert "data/raw_exports" in message
    assert "_configtracker" in message
    assert "openclaw_tamper_lab" in message


def test_load_lab_config_accepts_defaults_and_keeps_agentops_optional(tmp_path: Path) -> None:
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
        'public_sample_policy = "live_run_required"\n'
        '\n[sacrificial]\n'
        'allowed_app = "ai_tamperguard_v1"\n'
        'allowed_object_id_prefixes = ["tg_v1_", "ai_tamperguard_v1_"]\n'
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report", "lookup"]\n',
        encoding="utf-8",
    )

    loaded = load_lab_config(cfg)

    assert loaded.target_namespace == "ai_tamperguard_v1"
    assert loaded.required_indexes == ("_audit", "_configtracker", "openclaw_tamper_lab")
    assert loaded.optional_indexes == ("agentops",)
    assert loaded.capture_destination.as_posix() == "data/raw_exports"
    assert loaded.splunk_hec is None
    assert loaded.splunk_search is None


def test_load_lab_config_accepts_optional_splunk_hec_and_search_env_refs(tmp_path: Path) -> None:
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
        'allowed_object_types = ["dashboard", "saved_search", "alert", "report", "lookup"]\n'
        '\n[splunk_hec]\n'
        'url = "https://example.invalid/services/collector/event"\n'
        'index = "openclaw_tamper_lab"\n'
        'sourcetype = "ai_tamperguard:v1:scenario_evidence"\n'
        'source = "ai_tamperguard:v1:seed"\n'
        '\n[splunk_search]\n'
        'url = "https://example.invalid/services/search/jobs/export"\n'
        'token_env = "AI_TAMPERGUARD_SPLUNK_SEARCH_TOKEN"\n',
        encoding="utf-8",
    )

    loaded = load_lab_config(cfg)

    assert loaded.splunk_hec is not None
    assert loaded.splunk_hec.token_env == "AI_TAMPERGUARD_SPLUNK_HEC_TOKEN"
    assert loaded.splunk_hec.index == "openclaw_tamper_lab"
    assert loaded.splunk_search is not None
    assert loaded.splunk_search.token_env == "AI_TAMPERGUARD_SPLUNK_SEARCH_TOKEN"


def test_load_lab_config_rejects_unsafe_splunk_hec_index_and_token_env(tmp_path: Path) -> None:
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
        'allowed_object_types = ["dashboard"]\n'
        '\n[splunk_hec]\n'
        'url = "https://example.invalid/services/collector/event"\n'
        'token_env = "not a token env"\n'
        'index = "main"\n',
        encoding="utf-8",
    )

    with pytest.raises(LabConfigError) as excinfo:
        load_lab_config(cfg)
    assert "openclaw_tamper_lab" in str(excinfo.value)
    assert "environment variable name" in str(excinfo.value)


def test_load_sacrificial_inventory_rejects_private_names_without_public_object_ids(tmp_path: Path) -> None:
    private_dir = tmp_path / "splunk" / "private"
    private_dir.mkdir(parents=True)
    inventory = private_dir / "sacrificial_inventory.toml"
    inventory.write_text(
        'namespace = "ai_tamperguard_v1"\n'
        'synthetic_index = "openclaw_tamper_lab"\n'
        '\n[[artifacts]]\n'
        'private_name = "tg_v1_dashboard_alibi_factory"\n'
        'object_type = "dashboard"\n'
        'scenario_ids = ["scenario_010"]\n',
        encoding="utf-8",
    )

    with pytest.raises(LabConfigError, match="object_id"):
        load_sacrificial_inventory(inventory, expected_namespace="ai_tamperguard_v1")


def test_load_sacrificial_inventory_accepts_public_safe_artifact_mapping(tmp_path: Path) -> None:
    private_dir = tmp_path / "splunk" / "private"
    private_dir.mkdir(parents=True)
    inventory = private_dir / "sacrificial_inventory.toml"
    inventory.write_text(
        'namespace = "ai_tamperguard_v1"\n'
        'synthetic_index = "openclaw_tamper_lab"\n'
        '\n[[artifacts]]\n'
        'object_id = "object_000010"\n'
        'private_name = "tg_v1_dashboard_alibi_factory"\n'
        'object_type = "dashboard"\n'
        'scenario_ids = ["scenario_010"]\n',
        encoding="utf-8",
    )

    loaded = load_sacrificial_inventory(inventory, expected_namespace="ai_tamperguard_v1")

    assert loaded.namespace == "ai_tamperguard_v1"
    assert loaded.artifacts[0].object_id == "object_000010"
    assert loaded.artifacts[0].scenario_ids == ("scenario_010",)
