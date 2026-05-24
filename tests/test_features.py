import json
import subprocess
import sys

import pandas as pd

from ai_tamperguard.features import (
    FEATURE_COLUMNS,
    actor_surrogate,
    build_actor_60m_windows,
    build_actor_windows,
    normalize_event,
)
from ai_tamperguard.schema import validate_behavior_window


def test_normalize_audit_event_uses_controlled_fields_without_raw_identity():
    row = normalize_event(
        {
            "_time": "2026-05-24T12:05:00Z",
            "sourcetype": "audittrail",
            "user": "raw-admin-user",
            "action": "search",
            "search": "index=_audit | table user",
            "status": "success",
        },
        salt="synthetic-salt",
    )

    assert row == {
        "timestamp": "2026-05-24T12:05:00+00:00",
        "actor_surrogate_private": actor_surrogate({"user": "raw-admin-user"}, "synthetic-salt"),
        "source_type": "audittrail",
        "action_category": "search",
        "status": "success",
        "is_admin_action": 0,
        "is_config_action": 0,
        "is_token_or_rbac_action": 0,
        "is_index_or_input_action": 0,
        "is_after_hours": 0,
    }
    assert "raw-admin-user" not in json.dumps(row)
    assert "search" in row["action_category"]


def test_normalize_configtracker_event_marks_config_and_admin_action():
    row = normalize_event(
        {
            "_time": 1779620700,
            "sourcetype": "splunk_configuration_change",
            "user": "config-owner",
            "action": "edit",
            "object_category": "indexes",
            "status": "modified",
        },
        salt="synthetic-salt",
    )

    assert row["source_type"] == "splunk_configuration_change"
    assert row["action_category"] == "index_or_input"
    assert row["status"] == "modified"
    assert row["is_admin_action"] == 1
    assert row["is_config_action"] == 1
    assert row["is_index_or_input_action"] == 1
    assert "config-owner" not in json.dumps(row)


def test_normalize_configtracker_dotted_fields_for_action_and_object_context():
    row = normalize_event(
        {
            "_time": "2026-05-24T12:05:00Z",
            "sourcetype": "splunk_configuration_change",
            "user": "config-owner",
            "data.action": "update",
            "data.changes{}.stanza": "indexes",
            "data.path": "system/local/indexes.conf",
        },
        salt="synthetic-salt",
    )

    assert row["action_category"] == "index_or_input"
    assert row["is_admin_action"] == 1
    assert row["is_config_action"] == 1
    assert row["is_index_or_input_action"] == 1
    assert "config-owner" not in json.dumps(row)
    assert "indexes.conf" not in json.dumps(row)


def test_normalize_missing_fields_defaults_unknown_or_zero_without_nulls():
    row = normalize_event({"_time": "2026-05-24T12:05:00Z"}, salt="synthetic-salt")

    assert row["actor_surrogate_private"] == actor_surrogate({}, "synthetic-salt")
    assert row["source_type"] == "unknown"
    assert row["action_category"] == "other"
    assert row["status"] == "unknown"
    assert all(value is not None for value in row.values())


def test_normalize_decimal_epoch_string_and_buckets_unrecognized_raw_action():
    row = normalize_event(
        {
            "_time": "1779620700.123",
            "sourcetype": "audittrail",
            "user": "alice",
            "action": "view_/secret/customer123",
            "object": "sensitive/object/name",
        },
        salt="synthetic-salt",
    )

    assert row["timestamp"] == "2026-05-24T11:05:00.123000+00:00"
    assert row["action_category"] == "other"
    assert "secret" not in json.dumps(row)
    assert "customer123" not in json.dumps(row)
    assert "sensitive" not in json.dumps(row)
    assert "alice" not in json.dumps(row)


def test_actor_60m_windows_group_by_actor_and_utc_hour_with_stable_features():
    events = [
        {
            "_time": "2026-05-24T12:05:00Z",
            "sourcetype": "audittrail",
            "user": "alice",
            "action": "search",
            "status": "success",
        },
        {
            "_time": "2026-05-24T12:35:00Z",
            "sourcetype": "audittrail",
            "user": "alice",
            "action": "edit_user",
            "status": "failure",
        },
        {
            "_time": "2026-05-24T13:01:00Z",
            "sourcetype": "audittrail",
            "user": "alice",
            "action": "create_token",
            "status": "success",
        },
        {
            "_time": "2026-05-24T12:15:00Z",
            "sourcetype": "splunk_configuration_change",
            "user": "bob",
            "action": "edit",
            "object_category": "inputs",
            "status": "modified",
        },
    ]

    windows = build_actor_60m_windows(events, salt="synthetic-salt", source_dataset="synthetic-unit")

    assert [row["window_start"] for row in windows] == [
        "2026-05-24T12:00:00Z",
        "2026-05-24T12:00:00Z",
        "2026-05-24T13:00:00Z",
    ]
    assert 8 <= len(FEATURE_COLUMNS) <= 20
    assert all(name.startswith("feature_") for name in FEATURE_COLUMNS)
    assert all(set(FEATURE_COLUMNS).issubset(row) for row in windows)
    assert all(isinstance(row[name], int) for row in windows for name in FEATURE_COLUMNS)
    assert all("alice" not in json.dumps(row) and "bob" not in json.dumps(row) for row in windows)

    alice_noon = next(row for row in windows if row["window_start"] == "2026-05-24T12:00:00Z" and row["feature_event_count"] == 2)
    assert alice_noon["feature_search_count"] == 1
    assert alice_noon["feature_admin_action_count"] == 1
    assert alice_noon["feature_failed_action_count"] == 1
    assert alice_noon["feature_distinct_action_category_count"] == 2

    bob_noon = next(row for row in windows if row["window_start"] == "2026-05-24T12:00:00Z" and row["feature_config_action_count"] == 1)
    assert bob_noon["feature_index_or_input_action_count"] == 1


def test_actor_60m_windows_validate_against_public_behavior_schema():
    events = [
        {"_time": "2026-05-24T12:05:00Z", "sourcetype": "audittrail", "user": "alice", "action": "search"},
        {"_time": "2026-05-24T12:30:00Z", "sourcetype": "audittrail", "user": "alice", "action": "edit_user"},
    ]

    [window] = build_actor_60m_windows(events, salt="synthetic-salt", source_dataset="synthetic-unit")

    public_window = {key: value for key, value in window.items() if not key.endswith("_private")}
    validate_behavior_window(public_window, public=True)


def test_actor_15m_windows_group_by_actor_and_quarter_hour_with_schema():
    events = [
        {"_time": "2026-05-24T12:05:00Z", "sourcetype": "audittrail", "user": "alice", "action": "search"},
        {"_time": "2026-05-24T12:16:00Z", "sourcetype": "audittrail", "user": "alice", "action": "search"},
    ]

    windows = build_actor_windows(events, salt="synthetic-salt", source_dataset="synthetic-unit", window_minutes=15)

    assert [row["window_type"] for row in windows] == ["actor_15m", "actor_15m"]
    assert [row["window_start"] for row in windows] == ["2026-05-24T12:00:00Z", "2026-05-24T12:15:00Z"]
    assert [row["window_end"] for row in windows] == ["2026-05-24T12:15:00Z", "2026-05-24T12:30:00Z"]
    public_window = {key: value for key, value in windows[0].items() if not key.endswith("_private")}
    validate_behavior_window(public_window, public=True)


def test_extract_windows_cli_writes_private_csv_without_raw_columns_or_nulls(tmp_path):
    input_path = tmp_path / "raw_events.jsonl"
    output_path = tmp_path / "windows.csv"
    salt_path = tmp_path / "salt.txt"
    salt_path.write_text("synthetic-salt\n", encoding="utf-8")
    events = [
        {"_time": "2026-05-24T12:05:00Z", "sourcetype": "audittrail", "user": "alice", "action": "search"},
        {"_time": "2026-05-24T12:30:00Z", "sourcetype": "audittrail", "user": "alice", "action": "edit_user"},
    ]
    input_path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_windows_v0.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--salt-file",
            str(salt_path),
            "--source-dataset",
            "synthetic-cli",
            "--window-minutes",
            "15",
        ],
        check=True,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert "wrote 2 actor_15m windows" in result.stdout
    frame = pd.read_csv(output_path)
    assert not frame.isnull().any().any()
    assert "actor_surrogate_private" in frame.columns
    assert not {"user", "username", "object", "path", "search"}.intersection(frame.columns)
    public_rows = frame.drop(columns=["actor_surrogate_private"]).to_dict(orient="records")
    validate_behavior_window(public_rows[0], public=True)
