from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_materializer(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/materialize_prompt_pack_runs_v1.py", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_materializer_emits_private_run_manifests(tmp_path: Path) -> None:
    v1_root = Path(__file__).resolve().parents[1]
    output_dir = v1_root / "data" / "private" / "run_manifests" / "pytest_nondet_batch"
    if output_dir.exists():
        for child in sorted(output_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        output_dir.rmdir()

    result = run_materializer(
        "--prompt-pack",
        "scenarios/nondeterministic_prompt_pack_v1.jsonl",
        "--scenario",
        "scenario_006",
        "--batch-id",
        "pytest_nondet_batch",
        "--attempts",
        "2",
        "--seed",
        "20260525",
        "--output-dir",
        "data/private/run_manifests/pytest_nondet_batch",
        "--dry-run",
        cwd=v1_root,
    )

    assert result.returncode == 0, result.stderr
    scenario_runs_path = output_dir / "scenario_runs_private.jsonl"
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

    for row in rows:
        assert row["scenario_id"] == "scenario_006"
        assert row["batch_id"] == "pytest_nondet_batch"
        assert row["prompt_variant_id"]
        assert row["prompt_family"]
        assert row["prompt_pack_version"].startswith("nondet-v1-")
        assert row["prompt_seed"] == 20260525
        assert row["attempt_index"] in {1, 2}
        assert 2 <= row["max_tool_budget"] <= 8
        assert row["public_release_ready"] is False
        prompt_path = v1_root / row["private_actor_prompt_path"]
        assert prompt_path.exists()
        prompt_text = prompt_path.read_text(encoding="utf-8")
        assert row["synthetic_case_id"] in prompt_text
        assert "{synthetic_case_id}" not in prompt_text


def test_materializer_rejects_public_output_dir(tmp_path: Path) -> None:
    v1_root = Path(__file__).resolve().parents[1]

    result = run_materializer(
        "--prompt-pack",
        "scenarios/nondeterministic_prompt_pack_v1.jsonl",
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
        cwd=v1_root,
    )

    assert result.returncode != 0
    assert "data/private/run_manifests" in result.stderr


def test_materializer_rejects_traversal_out_of_private_run_manifests(tmp_path: Path) -> None:
    v1_root = Path(__file__).resolve().parents[1]

    result = run_materializer(
        "--prompt-pack",
        "scenarios/nondeterministic_prompt_pack_v1.jsonl",
        "--scenario",
        "scenario_006",
        "--batch-id",
        "bad_batch",
        "--attempts",
        "1",
        "--seed",
        "20260525",
        "--output-dir",
        "data/private/run_manifests/../../public_sample/bad_prompt_leak",
        "--dry-run",
        cwd=v1_root,
    )

    assert result.returncode != 0
    assert "data/private/run_manifests" in result.stderr
