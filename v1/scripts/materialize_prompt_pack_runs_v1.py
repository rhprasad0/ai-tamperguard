from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.prompt_pack import PromptVariant, variants_for_scenario  # noqa: E402

PRIVATE_RUN_MANIFEST_PREFIX = Path("data/private/run_manifests")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize private AI TamperGuard nondeterministic prompt-pack run manifests.")
    parser.add_argument("--prompt-pack", required=True, type=Path)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--attempts", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--prompt-variant-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true", help="Write local private artifacts only; never contacts live services.")
    parser.add_argument("--force", action="store_true", help="Replace an existing output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    materialize_prompt_pack_runs(
        prompt_pack=args.prompt_pack,
        scenario_id=args.scenario,
        batch_id=args.batch_id,
        attempts=args.attempts,
        seed=args.seed,
        output_dir=args.output_dir,
        prompt_variant_ids=tuple(args.prompt_variant_id),
        dry_run=args.dry_run,
        force=args.force,
    )
    return 0


def materialize_prompt_pack_runs(
    *,
    prompt_pack: Path,
    scenario_id: str,
    batch_id: str,
    attempts: int,
    seed: int,
    output_dir: Path,
    prompt_variant_ids: tuple[str, ...] = (),
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if attempts < 1:
        raise SystemExit("--attempts must be >= 1")
    normalized_output = _normalize_relative_output_dir(output_dir)
    if not _is_under_private_run_manifests(normalized_output):
        raise SystemExit("--output-dir must be under data/private/run_manifests")

    variants = variants_for_scenario(prompt_pack, scenario_id)
    if prompt_variant_ids:
        allowed = set(prompt_variant_ids)
        variants = [variant for variant in variants if variant.prompt_variant_id in allowed]
        missing = allowed - {variant.prompt_variant_id for variant in variants}
        if missing:
            raise SystemExit(f"requested prompt variants are unavailable for {scenario_id}: {sorted(missing)}")
    if not variants:
        raise SystemExit(f"no prompt variants allow scenario {scenario_id}")

    if normalized_output.exists():
        if not force:
            raise SystemExit(f"output directory already exists; pass --force to replace: {normalized_output}")
        shutil.rmtree(normalized_output)
    prompt_dir = normalized_output / "actor_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for variant in variants:
        for attempt_index in range(1, attempts + 1):
            run_id = _scenario_run_id(scenario_id, variant.prompt_variant_id, attempt_index)
            synthetic_case_id = f"synthetic_case_{scenario_id[-3:]}_{seed}_{attempt_index:03d}"
            sacrificial_report_id = f"report_{scenario_id[-3:]}_{attempt_index:03d}"
            render_values = {
                "synthetic_case_id": synthetic_case_id,
                "scenario_id": scenario_id,
                "scenario_run_id": run_id,
                "batch_id": batch_id,
                "attempt_index": attempt_index,
                "max_tool_budget": variant.max_tool_budget,
                "object_family": "synthetic_visibility_note",
                "sacrificial_report_id": sacrificial_report_id,
            }
            prompt_text = _render_private_prompt(variant, render_values, dry_run=dry_run)
            prompt_path = prompt_dir / f"{run_id}.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")
            rows.append(
                {
                    "scenario_run_id": run_id,
                    "scenario_id": scenario_id,
                    "batch_id": batch_id,
                    "prompt_variant_id": variant.prompt_variant_id,
                    "prompt_family": variant.prompt_family,
                    "prompt_pack_version": variant.prompt_pack_version,
                    "trajectory_goal_family": variant.trajectory_goal_family,
                    "prompt_seed": seed + attempt_index - 1,
                    "attempt_index": attempt_index,
                    "max_tool_budget": variant.max_tool_budget,
                    "synthetic_case_id": synthetic_case_id,
                    "sacrificial_report_id": sacrificial_report_id,
                    "private_actor_prompt_path": prompt_path.as_posix(),
                    "public_release_ready": False,
                }
            )

    scenario_runs_path = normalized_output / "scenario_runs_private.jsonl"
    scenario_runs_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "batch_id": batch_id,
        "scenario_id": scenario_id,
        "prompt_pack_path": prompt_pack.as_posix(),
        "prompt_variant_ids": [variant.prompt_variant_id for variant in variants],
        "attempts_per_variant": attempts,
        "seed": seed,
        "dry_run": dry_run,
        "scenario_run_count": len(rows),
        "private_actor_prompt_dir": prompt_dir.as_posix(),
        "scenario_runs_private_path": scenario_runs_path.as_posix(),
        "public_release_ready": False,
    }
    (normalized_output / "prompt_pack_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return manifest


def _normalize_relative_output_dir(output_dir: Path) -> Path:
    cwd = Path.cwd().resolve()
    resolved = output_dir.resolve()
    try:
        return resolved.relative_to(cwd)
    except ValueError as exc:
        raise SystemExit("--output-dir must be relative to the v1 project root") from exc


def _is_under_private_run_manifests(path: Path) -> bool:
    parts = path.parts
    prefix = PRIVATE_RUN_MANIFEST_PREFIX.parts
    return parts[: len(prefix)] == prefix and len(parts) > len(prefix)


def _scenario_run_id(scenario_id: str, prompt_variant_id: str, attempt_index: int) -> str:
    return f"{scenario_id}_nondet_{prompt_variant_id}_attempt_{attempt_index:03d}"


def _render_private_prompt(variant: PromptVariant, values: dict[str, Any], *, dry_run: bool) -> str:
    body = variant.render(values)
    mode = "DRY RUN" if dry_run else "AUTHORIZED PRIVATE HARNESS"
    return (
        f"# AI TamperGuard Actor Prompt ({mode})\n\n"
        f"scenario_run_id: {values['scenario_run_id']}\n"
        f"prompt_variant_id: {variant.prompt_variant_id}\n"
        f"prompt_family: {variant.prompt_family}\n"
        f"safety_boundary: {variant.safety_boundary}\n"
        f"max_tool_budget: {variant.max_tool_budget}\n\n"
        f"{body}\n\n"
        "Safety reminder: use only synthetic lab fixtures and keep raw outputs private.\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
