from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ai_tamperguard_v1.prompt_pack import variants_for_scenario
from ai_tamperguard_v1.scenario_catalog import load_scenario_catalog

V1_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = V1_ROOT / "scripts" / "generate_training_batch_v1.py"
SCENARIO_CATALOG = V1_ROOT / "scenarios" / "scenario_catalog_v1.jsonl"
PATH_TEMPLATES = V1_ROOT / "scenarios" / "path_templates_v1.jsonl"
PROMPT_PACK = V1_ROOT / "scenarios" / "nondeterministic_prompt_pack_v1.jsonl"
ALLOCATION_CONFIG = V1_ROOT / "config" / "v1_5k_all_scenarios.yaml"

OPAQUE_RUN_ID = re.compile(r"^run_[a-f0-9]{16}$")
OPAQUE_CASE_ID = re.compile(r"^case_[a-f0-9]{16}$")
OPAQUE_REPORT_ID = re.compile(r"^report_[a-f0-9]{16}$")


def _run_generator(
    tmp_path: Path,
    *,
    batch_id: str,
    target_runs: int | None = 84,
    seed: int = 260526,
    allocation_config: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output_dir = Path("data") / "run_manifests" / batch_id
    cmd = [
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
            "--seed",
            str(seed),
            "--no-reset-required",
            "--output-dir",
            output_dir.as_posix(),
    ]
    if target_runs is not None:
        cmd.extend(["--target-runs", str(target_runs)])
    if allocation_config is not None:
        cmd.extend(["--allocation-config", str(allocation_config)])
    result = subprocess.run(
        cmd,
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, tmp_path / output_dir


def _read_rows(output_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (output_dir / "scenario_runs.jsonl").read_text(encoding="utf-8").splitlines()]


def _entropy(values: list[str]) -> float:
    total = len(values)
    counts = Counter(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def _mutual_information(left: list[str], right: list[str]) -> float:
    if len(left) != len(right):
        raise AssertionError("MI inputs must have equal length")
    total = len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    joint_counts = Counter(zip(left, right))
    mi = 0.0
    for (left_value, right_value), joint_count in joint_counts.items():
        p_xy = joint_count / total
        p_x = left_counts[left_value] / total
        p_y = right_counts[right_value] / total
        mi += p_xy * math.log2(p_xy / (p_x * p_y))
    return mi


def test_generate_training_batch_writes_all_scenario_dry_run_manifest(tmp_path: Path) -> None:
    batch_id = "pytest_all_scenarios_dry"
    target_runs = 84
    result, output_dir = _run_generator(tmp_path, batch_id=batch_id, target_runs=target_runs)

    assert result.returncode == 0, result.stderr
    scenario_runs_path = output_dir / "scenario_runs.jsonl"
    coverage_path = output_dir / "coverage_summary.json"
    assert scenario_runs_path.exists()
    assert coverage_path.exists()

    rows = _read_rows(output_dir)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    assert coverage["batch_id"] == batch_id
    assert coverage["mode"] == "dry-run"
    assert "target_windows_min" not in coverage
    assert "target_windows_max" not in coverage
    assert coverage["actor_prompt_count"] == target_runs
    assert coverage["all_catalog_scenarios_covered"] is True
    assert coverage["scenario_count"] == 28
    assert coverage["scenario_run_count"] == target_runs
    assert len(rows) == target_runs
    assert {row["scenario_id"] for row in rows} == set(coverage["scenario_ids"])
    assert coverage["leakage_check"] in {"pass", "insufficient_sample"}
    assert "mutual_information_checks" in coverage
    assert "per_scenario_axis_counts" in coverage

    required_manifest_fields = {
        "scenario_run_id",
        "scenario_id",
        "path_type",
        "ground_truth_family",
        "outcome",
        "prompt_variant_id",
        "label_source",
        "actor_prompt_path",
        "actor_profile",
        "evidence_order",
        "conflict_intensity",
        "distractor_count",
        "object_family",
        "reset_id",
        "paired_control_run_id",
        "release_eligibility",
    }
    for row in rows:
        assert required_manifest_fields <= set(row)
        assert (tmp_path / row["actor_prompt_path"]).exists()
        assert row["label_source"] in {"scenario_answer_key", "paired_benign_control", "manual_review"}

    scenario_run_schema = json.loads((V1_ROOT / "schemas" / "scenario_run_v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(scenario_run_schema)
    for row in rows:
        validator.validate(row)


def test_generated_public_ids_are_opaque_and_do_not_encode_labels(tmp_path: Path) -> None:
    result, output_dir = _run_generator(tmp_path, batch_id="pytest_opaque_ids", target_runs=84)
    assert result.returncode == 0, result.stderr
    rows = _read_rows(output_dir)
    controlled_vocab = {
        "benign",
        "positive_proxy",
        "needs_review",
        "hard_negative",
        "benign_control",
        "hard_negative",
        "gray_zone",
        "attempted_positive",
        "successful_synthetic",
        "blocked",
    }

    for row in rows:
        ids = [row["scenario_run_id"], row["synthetic_case_id"], row["sacrificial_report_id"]]
        assert OPAQUE_RUN_ID.fullmatch(row["scenario_run_id"])
        assert OPAQUE_CASE_ID.fullmatch(row["synthetic_case_id"])
        assert OPAQUE_REPORT_ID.fullmatch(row["sacrificial_report_id"])
        forbidden_tokens = {
            row["scenario_id"],
            row["scenario_id"].removeprefix("scenario_"),
            row["scenario_family"],
            row["path_type"],
            row["outcome"],
            row["ground_truth_family"],
            row["prompt_variant_id"],
            *controlled_vocab,
        }
        for identifier in ids:
            for token in forbidden_tokens:
                if token and len(token) >= 3:
                    assert token not in identifier


def test_scenario_run_ids_are_batch_bound(tmp_path: Path) -> None:
    first_result, first_dir = _run_generator(tmp_path, batch_id="pytest_batch_a", target_runs=84, seed=7)
    second_result, second_dir = _run_generator(tmp_path, batch_id="pytest_batch_b", target_runs=84, seed=7)
    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr

    first_ids = {row["scenario_run_id"] for row in _read_rows(first_dir)}
    second_ids = {row["scenario_run_id"] for row in _read_rows(second_dir)}
    assert first_ids.isdisjoint(second_ids)


def test_variation_axes_are_diverse_per_scenario_and_low_information(tmp_path: Path) -> None:
    target_runs = 560
    result, output_dir = _run_generator(tmp_path, batch_id="pytest_variation_independence", target_runs=target_runs, seed=88)
    assert result.returncode == 0, result.stderr
    rows = _read_rows(output_dir)
    scenarios = {scenario.scenario_id: scenario for scenario in load_scenario_catalog(SCENARIO_CATALOG)}

    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[row["scenario_id"]].append(row)

    diversity_axes = [
        "actor_profile",
        "evidence_order",
        "conflict_intensity",
        "distractor_count",
        "object_family",
        "path_type",
        "prompt_variant_id",
    ]
    randomized_axes = [
        "actor_profile",
        "evidence_order",
        "conflict_intensity",
        "distractor_count",
        "object_family",
    ]
    for scenario_id, scenario_rows in by_scenario.items():
        scenario = scenarios[scenario_id]
        assert len({row["actor_profile"] for row in scenario_rows}) >= 3
        assert len({row["evidence_order"] for row in scenario_rows}) >= 3
        assert len({row["conflict_intensity"] for row in scenario_rows}) >= 3
        assert len({row["distractor_count"] for row in scenario_rows}) >= 3
        assert len({row["path_type"] for row in scenario_rows}) >= min(2, len(scenario.path_types_supported))
        assert len({row["object_family"] for row in scenario_rows}) >= min(2, len(scenario.allowed_object_types))
        assert len({row["prompt_variant_id"] for row in scenario_rows}) >= min(
            2, len(variants_for_scenario(PROMPT_PACK, scenario_id))
        )

    scenario_ids = [row["scenario_id"] for row in rows]
    scenario_entropy = _entropy(scenario_ids)
    for axis in randomized_axes:
        axis_values = [str(row[axis]) for row in rows]
        mi = _mutual_information(scenario_ids, axis_values)
        assert mi < 0.1 * scenario_entropy, f"{axis} MI too high: {mi:.3f} vs H={scenario_entropy:.3f}"

    assert set(diversity_axes) >= set(randomized_axes) | {"path_type", "prompt_variant_id"}


def test_generator_rejects_removed_target_window_args(tmp_path: Path) -> None:
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
            "pytest_removed_window_args",
            "--target-runs",
            "14",
            "--target-windows-min",
            "0",
            "--target-windows-max",
            "0",
            "--seed",
            "1",
            "--no-reset-required",
            "--output-dir",
            "data/run_manifests/pytest_removed_window_args",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr


def test_5k_all_scenarios_allocation_config_hits_bucket_counts(tmp_path: Path) -> None:
    batch_id = "pytest_all_scenarios_5k"
    result, output_dir = _run_generator(
        tmp_path,
        batch_id=batch_id,
        target_runs=None,
        seed=260526,
        allocation_config=ALLOCATION_CONFIG,
    )

    assert result.returncode == 0, result.stderr
    rows = _read_rows(output_dir)
    coverage = json.loads((output_dir / "coverage_summary.json").read_text(encoding="utf-8"))

    assert len(rows) == 5000
    assert coverage["scenario_count"] == 28
    assert coverage["all_catalog_scenarios_covered"] is True
    assert coverage["allocation_config_path"].endswith("v1_5k_all_scenarios.yaml")
    assert coverage["allocation_total"] == 5000
    assert coverage["allocation_bucket_counts"] == {
        "successful_synthetic": 950,
        "attempted_positive": 625,
        "blocked": 400,
        "gray_zone": 425,
        "paired_benign_controls": 1050,
        "hard_negatives": 950,
        "background_benign_admin": 600,
    }
    assert set(coverage["covered_scenario_ids"]) == {f"scenario_{idx:03d}" for idx in range(1, 29)}
    assert sum(coverage["allocation_bucket_counts"].values()) == coverage["scenario_run_count"]
    assert coverage["leakage_check"] == "pass"
