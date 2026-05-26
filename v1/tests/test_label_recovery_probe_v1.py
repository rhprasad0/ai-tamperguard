from __future__ import annotations

import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

V1_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = V1_ROOT / "scripts" / "generate_training_batch_v1.py"
SCENARIO_CATALOG = V1_ROOT / "scenarios" / "scenario_catalog_v1.jsonl"
PATH_TEMPLATES = V1_ROOT / "scenarios" / "path_templates_v1.jsonl"
PROMPT_PACK = V1_ROOT / "scenarios" / "nondeterministic_prompt_pack_v1.jsonl"

POSITIVE_POLICIES = {"positive_proxy"}


def _entropy(values: list[str]) -> float:
    total = len(values)
    counts = Counter(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def _mutual_information(left: list[str], right: list[str]) -> float:
    total = len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    joint_counts = Counter(zip(left, right))
    return sum(
        (joint_count / total)
        * math.log2((joint_count / total) / ((left_counts[left_value] / total) * (right_counts[right_value] / total)))
        for (left_value, right_value), joint_count in joint_counts.items()
    )


def _run_generator(tmp_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    batch_id = "pytest_label_recovery_probe"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--scenario-catalog",
            str(SCENARIO_CATALOG),
            "--path-templates",
            str(PATH_TEMPLATES),
            "--prompt-pack",
            str(PROMPT_PACK),
            "--batch-id",
            batch_id,
            "--target-runs",
            "560",
            "--seed",
            "123",
            "--no-reset-required",
            "--output-dir",
            f"data/run_manifests/{batch_id}",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    manifest_dir = tmp_path / "data" / "run_manifests" / batch_id
    manifest = manifest_dir / "scenario_runs.jsonl"
    coverage = json.loads((manifest_dir / "coverage_summary.json").read_text(encoding="utf-8"))
    return [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()], coverage


def test_variation_metadata_cannot_recover_label_by_itself(tmp_path: Path) -> None:
    rows, coverage = _run_generator(tmp_path)
    assert coverage["leakage_check"] == "pass"
    labels = ["1" if row["label_binary_policy"] in POSITIVE_POLICIES else "0" for row in rows]
    label_entropy = _entropy(labels)
    metadata_axes = [
        "actor_profile",
        "evidence_order",
        "conflict_intensity",
        "distractor_count",
        "object_family",
    ]

    for axis in metadata_axes:
        axis_values = [str(row[axis]) for row in rows]
        assert _mutual_information(labels, axis_values) < 0.05 * label_entropy, axis

    # A one-column frequency baseline should not get a free ride from harness metadata.
    train = rows[::2]
    test = rows[1::2]
    for axis in metadata_axes:
        label_by_value = {}
        global_majority = Counter("1" if row["label_binary_policy"] in POSITIVE_POLICIES else "0" for row in train).most_common(1)[0][0]
        global_accuracy = sum(
            1
            for row in test
            if ("1" if row["label_binary_policy"] in POSITIVE_POLICIES else "0") == global_majority
        ) / len(test)
        for value in {str(row[axis]) for row in train}:
            labels_for_value = ["1" if row["label_binary_policy"] in POSITIVE_POLICIES else "0" for row in train if str(row[axis]) == value]
            label_by_value[value] = Counter(labels_for_value).most_common(1)[0][0]
        correct = 0
        for row in test:
            predicted = label_by_value.get(str(row[axis]), global_majority)
            actual = "1" if row["label_binary_policy"] in POSITIVE_POLICIES else "0"
            correct += int(predicted == actual)
        assert (correct / len(test)) <= global_accuracy + 0.02, axis


def test_variation_metadata_cannot_recover_path_type_by_itself(tmp_path: Path) -> None:
    rows, coverage = _run_generator(tmp_path)
    assert coverage["leakage_check"] == "pass"
    path_types = [str(row["path_type"]) for row in rows]
    scenario_ids = [str(row["scenario_id"]) for row in rows]
    metadata_axes = [
        "actor_profile",
        "evidence_order",
        "conflict_intensity",
        "distractor_count",
        "object_family",
    ]

    for target_values in (path_types, scenario_ids):
        target_entropy = _entropy(target_values)
        for axis in metadata_axes:
            axis_values = [str(row[axis]) for row in rows]
            assert _mutual_information(target_values, axis_values) < 0.1 * target_entropy, axis
