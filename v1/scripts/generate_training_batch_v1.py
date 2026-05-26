from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.path_templates import load_path_templates  # noqa: E402
from ai_tamperguard_v1.prompt_pack import PromptVariant, variants_for_scenario  # noqa: E402
from ai_tamperguard_v1.scenario_catalog import load_scenario_catalog  # noqa: E402

RUN_MANIFEST_PREFIX = Path("data/run_manifests")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an all-scenario AI TamperGuard v1 dry-run training batch manifest.")
    parser.add_argument("--scenario-catalog", required=True, type=Path)
    parser.add_argument("--path-templates", required=True, type=Path)
    parser.add_argument("--prompt-pack", required=True, type=Path)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--target-runs", required=True, type=int)
    parser.add_argument("--target-windows-min", required=True, type=int)
    parser.add_argument("--target-windows-max", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--mode", choices={"dry-run"}, default="dry-run")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = generate_training_batch(
        scenario_catalog=args.scenario_catalog,
        path_templates=args.path_templates,
        prompt_pack=args.prompt_pack,
        batch_id=args.batch_id,
        target_runs=args.target_runs,
        target_windows_min=args.target_windows_min,
        target_windows_max=args.target_windows_max,
        seed=args.seed,
        mode=args.mode,
        output_dir=args.output_dir,
        force=args.force,
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


def generate_training_batch(
    *,
    scenario_catalog: Path,
    path_templates: Path,
    prompt_pack: Path,
    batch_id: str,
    target_runs: int,
    target_windows_min: int,
    target_windows_max: int,
    seed: int,
    mode: str,
    output_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    if target_runs < 1:
        raise SystemExit("--target-runs must be >= 1")
    if target_windows_min > target_windows_max:
        raise SystemExit("--target-windows-min cannot exceed --target-windows-max")
    normalized_output = _normalize_relative_output_dir(output_dir)
    if not _is_under_run_manifests(normalized_output):
        raise SystemExit("--output-dir must be under data/run_manifests")
    if normalized_output.exists():
        if not force:
            raise SystemExit(f"output directory already exists; pass --force to replace: {normalized_output}")
        shutil.rmtree(normalized_output)
    prompt_dir = normalized_output / "actor_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    scenarios = load_scenario_catalog(scenario_catalog)
    templates = load_path_templates(path_templates, scenarios=scenarios)
    templates_by_scenario: dict[str, list[Any]] = defaultdict(list)
    for template in templates:
        templates_by_scenario[template.scenario_id].append(template)

    if target_runs < len(scenarios):
        raise SystemExit("--target-runs must be at least the canonical scenario count for all-scenario coverage")

    rows: list[dict[str, Any]] = []
    attempt_counts: Counter[str] = Counter()
    actor_profiles = ("cautious_analyst", "rushed_operator", "skeptical_reviewer", "automation_helper")
    evidence_orders = ("audit_first", "config_first", "report_first", "mixed_conflict_first")
    conflict_levels = ("low", "medium", "high")
    distractor_counts = (0, 1, 2, 3)

    for run_index in range(1, target_runs + 1):
        scenario = scenarios[(run_index - 1) % len(scenarios)]
        attempt_counts[scenario.scenario_id] += 1
        attempt_index = attempt_counts[scenario.scenario_id]
        prompt_variants = variants_for_scenario(prompt_pack, scenario.scenario_id)
        if not prompt_variants:
            raise SystemExit(f"no prompt variants allow scenario {scenario.scenario_id}")
        prompt_variant = prompt_variants[(attempt_index - 1) % len(prompt_variants)]
        scenario_templates = templates_by_scenario[scenario.scenario_id]
        path_template = scenario_templates[(attempt_index - 1) % len(scenario_templates)]
        object_family = scenario.allowed_object_types[(attempt_index - 1) % len(scenario.allowed_object_types)]
        actor_profile = actor_profiles[(run_index + seed) % len(actor_profiles)]
        evidence_order = evidence_orders[(attempt_index + seed) % len(evidence_orders)]
        conflict_intensity = conflict_levels[(run_index + attempt_index + seed) % len(conflict_levels)]
        distractor_count = distractor_counts[(run_index + seed) % len(distractor_counts)]
        run_id = f"{scenario.scenario_id}_{path_template.path_type}_{prompt_variant.prompt_variant_id}_attempt_{attempt_index:03d}"
        synthetic_case_id = f"synthetic_case_{scenario.scenario_id[-3:]}_{seed}_{attempt_index:03d}"
        sacrificial_report_id = f"report_{scenario.scenario_id[-3:]}_{attempt_index:03d}"
        actor_prompt_path = prompt_dir / f"{run_id}.txt"
        prompt_text = prompt_variant.render(
            {
                "synthetic_case_id": synthetic_case_id,
                "scenario_id": scenario.scenario_id,
                "scenario_run_id": run_id,
                "batch_id": batch_id,
                "attempt_index": attempt_index,
                "max_tool_budget": prompt_variant.max_tool_budget,
                "object_family": object_family,
                "sacrificial_report_id": sacrificial_report_id,
            }
        )
        actor_prompt_path.write_text(
            "# AI TamperGuard Actor Prompt (DRY RUN)\n\n"
            f"scenario_run_id: {run_id}\n"
            f"prompt_variant_id: {prompt_variant.prompt_variant_id}\n"
            f"path_template_id: {path_template.path_template_id}\n"
            f"path_type: {path_template.path_type}\n"
            f"actor_profile: {actor_profile}\n"
            f"evidence_order: {evidence_order}\n"
            f"conflict_intensity: {conflict_intensity}\n"
            f"distractor_count: {distractor_count}\n"
            f"safety_boundary: {prompt_variant.safety_boundary}\n\n"
            f"{prompt_text}\n\n"
            "Safety reminder: use only synthetic lab fixtures and keep raw exports ignored.\n",
            encoding="utf-8",
        )
        rows.append(
            {
                "scenario_run_id": run_id,
                "scenario_id": scenario.scenario_id,
                "scenario_family": scenario.family,
                "batch_id": batch_id,
                "path_template_id": path_template.path_template_id,
                "path_type": path_template.path_type,
                "ground_truth_family": path_template.label_family,
                "outcome": path_template.outcome,
                "label_source": path_template.label_binary_policy,
                "prompt_variant_id": prompt_variant.prompt_variant_id,
                "prompt_family": prompt_variant.prompt_family,
                "prompt_pack_version": prompt_variant.prompt_pack_version,
                "prompt_seed": seed + run_index - 1,
                "attempt_index": attempt_index,
                "actor_profile": actor_profile,
                "evidence_order": evidence_order,
                "conflict_intensity": conflict_intensity,
                "distractor_count": distractor_count,
                "object_family": object_family,
                "max_tool_budget": prompt_variant.max_tool_budget,
                "synthetic_case_id": synthetic_case_id,
                "sacrificial_report_id": sacrificial_report_id,
                "actor_prompt_path": actor_prompt_path.as_posix(),
                "public_release_ready": False,
            }
        )

    scenario_runs_path = normalized_output / "scenario_runs.jsonl"
    scenario_runs_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    coverage = {
        "batch_id": batch_id,
        "mode": mode,
        "target_runs": target_runs,
        "target_windows_min": target_windows_min,
        "target_windows_max": target_windows_max,
        "scenario_count": len(scenarios),
        "scenario_run_count": len(rows),
        "scenario_ids": scenario_ids,
        "covered_scenario_ids": sorted({row["scenario_id"] for row in rows}),
        "all_catalog_scenarios_covered": set(scenario_ids) <= {row["scenario_id"] for row in rows},
        "family_counts": dict(Counter(row["scenario_family"] for row in rows)),
        "path_type_counts": dict(Counter(row["path_type"] for row in rows)),
        "label_source_counts": dict(Counter(row["label_source"] for row in rows)),
        "scenario_runs_path": scenario_runs_path.as_posix(),
        "actor_prompt_dir": prompt_dir.as_posix(),
        "public_release_ready": False,
    }
    (normalized_output / "coverage_summary.json").write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return coverage


def _first_variant_for_scenario(prompt_pack: Path, scenario_id: str) -> PromptVariant:
    variants = variants_for_scenario(prompt_pack, scenario_id)
    if not variants:
        raise SystemExit(f"no prompt variants allow scenario {scenario_id}")
    return variants[0]


def _normalize_relative_output_dir(output_dir: Path) -> Path:
    cwd = Path.cwd().resolve()
    resolved = output_dir.resolve()
    try:
        return resolved.relative_to(cwd)
    except ValueError as exc:
        raise SystemExit("--output-dir must be relative to the v1 project root") from exc


def _is_under_run_manifests(path: Path) -> bool:
    parts = path.parts
    prefix = RUN_MANIFEST_PREFIX.parts
    return parts[: len(prefix)] == prefix and len(parts) > len(prefix)


if __name__ == "__main__":
    raise SystemExit(main())
