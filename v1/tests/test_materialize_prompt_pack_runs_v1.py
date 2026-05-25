from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

V1_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = V1_ROOT / "scripts" / "materialize_prompt_pack_runs_v1.py"
PROMPT_PACK = V1_ROOT / "scenarios" / "nondeterministic_prompt_pack_v1.jsonl"


def run_materializer(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_materializer_emits_public_safe_run_manifests(tmp_path: Path) -> None:
    output_dir = tmp_path / "data" / "run_manifests" / "pytest_nondet_batch"

    result = run_materializer(
        "--prompt-pack",
        str(PROMPT_PACK),
        "--scenario",
        "scenario_006",
        "--batch-id",
        "pytest_nondet_batch",
        "--attempts",
        "2",
        "--seed",
        "20260525",
        "--output-dir",
        "data/run_manifests/pytest_nondet_batch",
        "--dry-run",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    scenario_runs_path = output_dir / "scenario_runs.jsonl"
    manifest_path = output_dir / "prompt_pack_manifest.json"
    prompt_dir = output_dir / "actor_prompts"
    assert scenario_runs_path.exists()
    assert manifest_path.exists()
    assert prompt_dir.is_dir()

    rows = [json.loads(line) for line in scenario_runs_path.read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    variant_count = len(manifest["prompt_variant_ids"])
    assert variant_count >= 5
    assert len(rows) == variant_count * 2
    assert manifest["scenario_id"] == "scenario_006"
    assert manifest["attempts_per_variant"] == 2
    assert manifest["public_release_ready"] is False

    seeds_by_variant: dict[str, set[int]] = {}
    for row in rows:
        assert row["scenario_id"] == "scenario_006"
        assert row["batch_id"] == "pytest_nondet_batch"
        assert row["prompt_variant_id"]
        assert row["prompt_family"]
        assert row["prompt_pack_version"].startswith("nondet-v1-")
        assert row["prompt_seed"] in {20260525, 20260526}
        assert row["attempt_index"] in {1, 2}
        assert row["prompt_seed"] == 20260524 + row["attempt_index"]
        seeds_by_variant.setdefault(row["prompt_variant_id"], set()).add(row["prompt_seed"])
        assert 2 <= row["max_tool_budget"] <= 8
        assert row["public_release_ready"] is False
        prompt_path = tmp_path / row["actor_prompt_path"]
        assert prompt_path.exists()
        prompt_text = prompt_path.read_text(encoding="utf-8")
        assert row["synthetic_case_id"] in prompt_text
        assert "{synthetic_case_id}" not in prompt_text

    assert all(seeds == {20260525, 20260526} for seeds in seeds_by_variant.values())


def test_materializer_rejects_public_output_dir(tmp_path: Path) -> None:
    result = run_materializer(
        "--prompt-pack",
        str(PROMPT_PACK),
        "--scenario",
        "scenario_006",
        "--batch-id",
        "bad_batch",
        "--attempts",
        "1",
        "--seed",
        "20260525",
        "--output-dir",
        "data/public_sample/bad_prompt_leak",
        "--dry-run",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "data/run_manifests" in result.stderr


def test_materializer_rejects_traversal_out_of_run_manifests(tmp_path: Path) -> None:
    result = run_materializer(
        "--prompt-pack",
        str(PROMPT_PACK),
        "--scenario",
        "scenario_006",
        "--batch-id",
        "bad_batch",
        "--attempts",
        "1",
        "--seed",
        "20260525",
        "--output-dir",
        "data/run_manifests/../../public_sample/bad_prompt_leak",
        "--dry-run",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "data/run_manifests" in result.stderr
