import json
import subprocess
import sys

import pandas as pd
import pytest

from ai_tamperguard.features import FEATURE_COLUMNS
from ai_tamperguard.split import SplitError, split_windows, write_split


def synthetic_windows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(12):
        label = index % 2
        row: dict[str, object] = {
            "window_id": f"actor_60m:2026-05-24T{index:02d}:00:00Z:actor_{index:02d}",
            "window_type": "actor_60m",
            "window_start": f"2026-05-24T{index:02d}:00:00Z",
            "window_end": f"2026-05-24T{index + 1:02d}:00:00Z",
            "source_dataset": "synthetic-unit",
            "actor_surrogate_private": f"actor_private_{index:02d}",
            "label": label,
            "label_binary": label,
            "label_value_description": "working_model_positive_proxy" if label else "needs_review",
            "label_source": "weak_proxy_v0",
            "label_rule_id": "weak_proxy_v0_admin_control_plane_activity",
            "label_rule_description": "synthetic weak proxy label",
        }
        for feature_name in FEATURE_COLUMNS:
            row[feature_name] = index + label
        rows.append(row)
    return rows


def test_split_is_deterministic_for_same_input_and_seed():
    first = split_windows(synthetic_windows(), seed=20260524, holdout_fraction=0.25)
    second = split_windows(reversed(synthetic_windows()), seed=20260524, holdout_fraction=0.25)

    assert [row["window_id"] for row in first.train] == [row["window_id"] for row in second.train]
    assert [row["window_id"] for row in first.holdout] == [row["window_id"] for row in second.holdout]
    assert first.manifest["random_seed"] == 20260524
    assert first.manifest["holdout_fraction"] == 0.25


def test_train_and_holdout_window_ids_are_disjoint():
    result = split_windows(synthetic_windows(), seed=20260524, holdout_fraction=0.25)

    train_ids = {row["window_id"] for row in result.train}
    holdout_ids = {row["window_id"] for row in result.holdout}
    assert train_ids
    assert holdout_ids
    assert train_ids.isdisjoint(holdout_ids)
    assert train_ids | holdout_ids == {row["window_id"] for row in synthetic_windows()}


def test_stratified_split_preserves_both_classes_when_available():
    result = split_windows(synthetic_windows(), seed=20260524, holdout_fraction=0.25)

    assert {row["label_binary"] for row in result.train} == {0, 1}
    assert {row["label_binary"] for row in result.holdout} == {0, 1}
    assert result.manifest["counts"]["train_by_label"] == {"0": 4, "1": 4}
    assert result.manifest["counts"]["holdout_by_label"] == {"0": 2, "1": 2}


def test_split_fails_loud_if_either_class_has_zero_rows():
    rows = synthetic_windows()
    for row in rows:
        row["label_binary"] = 0
        row["label"] = 0
        row["label_value_description"] = "needs_review"

    with pytest.raises(SplitError, match="requires both label classes"):
        split_windows(rows, seed=20260524, holdout_fraction=0.25)


def test_split_fails_loud_on_duplicate_window_ids():
    rows = synthetic_windows()
    rows[1]["window_id"] = rows[0]["window_id"]

    with pytest.raises(SplitError, match="duplicate window_id"):
        split_windows(rows, seed=20260524, holdout_fraction=0.25)


def test_write_split_writes_manifest_with_seed_counts_and_file_hashes(tmp_path):
    input_path = tmp_path / "windows.csv"
    train_path = tmp_path / "train.csv"
    holdout_path = tmp_path / "holdout.csv"
    manifest_path = tmp_path / "split_manifest.json"
    pd.DataFrame(synthetic_windows()).to_csv(input_path, index=False)

    manifest = write_split(
        input_path=input_path,
        train_output_path=train_path,
        holdout_output_path=holdout_path,
        manifest_output_path=manifest_path,
        seed=20260524,
        holdout_fraction=0.25,
    )

    assert train_path.exists()
    assert holdout_path.exists()
    assert manifest_path.exists()
    manifest_from_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_from_disk == manifest
    assert manifest["random_seed"] == 20260524
    assert manifest["counts"] == {
        "input_total": 12,
        "train_total": 8,
        "holdout_total": 4,
        "input_by_label": {"0": 6, "1": 6},
        "train_by_label": {"0": 4, "1": 4},
        "holdout_by_label": {"0": 2, "1": 2},
    }
    assert set(manifest["file_hashes_sha256"]) == {"input", "train", "holdout"}
    assert all(len(value) == 64 for value in manifest["file_hashes_sha256"].values())


def test_split_holdout_cli_writes_outputs_and_manifest(tmp_path):
    input_path = tmp_path / "windows.csv"
    train_path = tmp_path / "train.csv"
    holdout_path = tmp_path / "holdout.csv"
    manifest_path = tmp_path / "split_manifest.json"
    pd.DataFrame(synthetic_windows()).to_csv(input_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/split_holdout_v0.py",
            "--input",
            str(input_path),
            "--train-output",
            str(train_path),
            "--holdout-output",
            str(holdout_path),
            "--manifest-output",
            str(manifest_path),
            "--seed",
            "20260524",
            "--holdout-fraction",
            "0.25",
        ],
        check=True,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert "wrote 8 train rows and 4 holdout rows" in result.stdout
    assert pd.read_csv(train_path).shape[0] == 8
    assert pd.read_csv(holdout_path).shape[0] == 4
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["random_seed"] == 20260524
