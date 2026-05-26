from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.leakage_metrics import entropy, mutual_information  # noqa: E402
from ai_tamperguard_v1.path_templates import load_path_templates  # noqa: E402
from ai_tamperguard_v1.prompt_pack import PromptVariant, variants_for_scenario  # noqa: E402
from ai_tamperguard_v1.scenario_catalog import load_scenario_catalog  # noqa: E402

RUN_MANIFEST_PREFIX = Path("data/run_manifests")
ID_KEY = b"ai-tamperguard-v1-public-dry-run-id-v1"
ACTOR_PROFILES = ("cautious_analyst", "rushed_operator", "skeptical_reviewer", "automation_helper")
EVIDENCE_ORDERS = ("audit_first", "config_first", "report_first", "mixed_conflict_first")
CONFLICT_LEVELS = ("low", "medium", "high")
DISTRACTOR_COUNTS = (0, 1, 2, 3)
GLOBAL_OBJECT_FAMILIES = ("visibility_object", "report_artifact", "search_artifact", "control_plane_fixture")
ACTOR_IDS = ("actor_001", "actor_002", "actor_003", "actor_004")
LABEL_SOURCE_BY_POLICY = {
    "benign": "paired_benign_control",
    "hard_negative": "scenario_answer_key",
    "positive_proxy": "scenario_answer_key",
    "needs_review": "manual_review",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an all-scenario AI TamperGuard v1 dry-run training batch manifest.")
    parser.add_argument("--scenario-catalog", required=True, type=Path)
    parser.add_argument("--path-templates", required=True, type=Path)
    parser.add_argument("--prompt-pack", required=True, type=Path)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--target-runs", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--no-reset-required", action="store_true")
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
        seed=args.seed,
        output_dir=args.output_dir,
        no_reset_required=args.no_reset_required,
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
    seed: int,
    output_dir: Path,
    no_reset_required: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if target_runs < 1:
        raise SystemExit("--target-runs must be >= 1")
    if not no_reset_required:
        raise SystemExit("dry-run generation requires --no-reset-required until reset manifests are wired in")
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
    templates_by_scenario_type: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    templates_by_id: dict[str, Any] = {}
    for template in templates:
        templates_by_scenario_type[template.scenario_id][template.path_type].append(template)
        templates_by_id[template.path_template_id] = template

    if target_runs < len(scenarios):
        raise SystemExit("--target-runs must be at least the canonical scenario count for all-scenario coverage")

    rows: list[dict[str, Any]] = []
    attempt_counts: Counter[str] = Counter()
    selected_template_counts: Counter[tuple[str, str]] = Counter()
    scenarios_by_id = {scenario.scenario_id: scenario for scenario in scenarios}

    for run_index in range(1, target_runs + 1):
        scenario = scenarios[(run_index - 1) % len(scenarios)]
        attempt_counts[scenario.scenario_id] += 1
        attempt_index = attempt_counts[scenario.scenario_id]
        run_seed = _seed_for(batch_id=batch_id, seed=seed, scenario_id=scenario.scenario_id, attempt_index=attempt_index)
        rng = random.Random(run_seed)

        prompt_variants = variants_for_scenario(prompt_pack, scenario.scenario_id)
        if not prompt_variants:
            raise SystemExit(f"no prompt variants allow scenario {scenario.scenario_id}")
        prompt_variant = _balanced_choice(prompt_variants, attempt_index=attempt_index, rng=rng)
        path_template = _select_path_template(
            templates_by_scenario_type[scenario.scenario_id],
            supported_path_types=scenario.path_types_supported,
            attempt_index=attempt_index,
            selected_template_counts=selected_template_counts,
            rng=rng,
        )
        object_family = _balanced_choice(GLOBAL_OBJECT_FAMILIES, attempt_index=attempt_index, rng=rng)
        actor_profile = _balanced_choice(ACTOR_PROFILES, attempt_index=attempt_index, rng=rng)
        evidence_order = _balanced_choice(EVIDENCE_ORDERS, attempt_index=attempt_index, rng=rng)
        conflict_intensity = _balanced_choice(CONFLICT_LEVELS, attempt_index=attempt_index, rng=rng)
        distractor_count = _balanced_choice(DISTRACTOR_COUNTS, attempt_index=attempt_index, rng=rng)

        id_basis = {
            "batch_id": batch_id,
            "scenario_id": scenario.scenario_id,
            "path_template_id": path_template.path_template_id,
            "prompt_variant_id": prompt_variant.prompt_variant_id,
            "attempt_index": attempt_index,
            "seed": seed,
            "run_seed": run_seed,
        }
        run_id = _opaque_id("run", id_basis)
        synthetic_case_id = _opaque_id("case", id_basis)
        sacrificial_report_id = _opaque_id("report", id_basis)
        reset_id = _opaque_id("reset", id_basis)
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
                "label_binary_policy": path_template.label_binary_policy,
                "label_source": LABEL_SOURCE_BY_POLICY[path_template.label_binary_policy],
                "prompt_variant_id": prompt_variant.prompt_variant_id,
                "prompt_family": prompt_variant.prompt_family,
                "prompt_pack_version": prompt_variant.prompt_pack_version,
                "prompt_seed": run_seed,
                "attempt_index": attempt_index,
                "actor_id": _actor_id(attempt_index),
                "actor_profile": actor_profile,
                "environment_id": "environment_001",
                "run_start_relative_sec": 0,
                "run_end_relative_sec": 900,
                "source_derivation": "synthetic_control_plane_fixture",
                "evidence_order": evidence_order,
                "conflict_intensity": conflict_intensity,
                "distractor_count": distractor_count,
                "object_family": object_family,
                "max_tool_budget": prompt_variant.max_tool_budget,
                "synthetic_case_id": synthetic_case_id,
                "sacrificial_report_id": sacrificial_report_id,
                "reset_id": reset_id,
                "paired_control_run_id": None,
                "release_eligibility": "fixture_smoke_only",
                "actor_prompt_path": actor_prompt_path.as_posix(),
                "public_release_ready": False,
            }
        )

    _assign_pairings(rows, templates_by_id)

    scenario_runs_path = normalized_output / "scenario_runs.jsonl"
    scenario_runs_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    coverage = _coverage_summary(
        rows,
        batch_id=batch_id,
        target_runs=target_runs,
        scenario_ids=scenario_ids,
        scenario_count=len(scenarios),
    )
    coverage["scenario_runs_path"] = scenario_runs_path.as_posix()
    coverage["actor_prompt_dir"] = prompt_dir.as_posix()
    (normalized_output / "coverage_summary.json").write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return coverage


def _actor_id(attempt_index: int) -> str:
    return ACTOR_IDS[(attempt_index - 1) % len(ACTOR_IDS)]


def _select_path_template(
    templates_by_type: dict[str, list[Any]],
    *,
    supported_path_types: tuple[str, ...],
    attempt_index: int,
    selected_template_counts: Counter[tuple[str, str]],
    rng: random.Random,
) -> Any:
    path_type = supported_path_types[(attempt_index - 1) % len(supported_path_types)]
    candidates = templates_by_type[path_type]
    min_count = min(selected_template_counts[(path_type, candidate.path_template_id)] for candidate in candidates)
    least_used = [candidate for candidate in candidates if selected_template_counts[(path_type, candidate.path_template_id)] == min_count]
    selected = rng.choice(least_used)
    selected_template_counts[(path_type, selected.path_template_id)] += 1
    return selected


def _balanced_choice(values: tuple[Any, ...] | list[Any], *, attempt_index: int, rng: random.Random) -> Any:
    items = list(values)
    offset = rng.randrange(len(items))
    return items[(attempt_index - 1 + offset) % len(items)]


def _seed_for(*, batch_id: str, seed: int, scenario_id: str, attempt_index: int) -> int:
    digest = _digest(
        "seed",
        {
            "batch_id": batch_id,
            "seed": seed,
            "scenario_id": scenario_id,
            "attempt_index": attempt_index,
        },
    )
    return int(digest[:16], 16)


def _opaque_id(kind: str, basis: dict[str, Any]) -> str:
    scenario_number = str(basis.get("scenario_id", "")).removeprefix("scenario_")
    forbidden_tokens = {scenario_number} if len(scenario_number) >= 3 else set()
    for nonce in range(1000):
        candidate_basis = {**basis, "id_nonce": nonce}
        identifier = f"{kind}_{_digest(kind, candidate_basis)[:16]}"
        if not any(token in identifier for token in forbidden_tokens):
            return identifier
    raise RuntimeError(f"could not generate opaque {kind} id without forbidden scenario token")


def _digest(kind: str, basis: dict[str, Any]) -> str:
    payload = json.dumps({"kind": kind, **basis}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(ID_KEY, payload, hashlib.sha256).hexdigest()


def _assign_pairings(rows: list[dict[str, Any]], templates_by_id: dict[str, Any]) -> None:
    rows_by_template: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_template[row["path_template_id"]].append(row)
    for row in rows:
        template = templates_by_id[row["path_template_id"]]
        paired_template_id = template.paired_control_path_template_id
        if not paired_template_id:
            continue
        partners = rows_by_template.get(paired_template_id, [])
        if not partners:
            continue
        row["paired_control_run_id"] = partners[(row["attempt_index"] - 1) % len(partners)]["scenario_run_id"]


def _coverage_summary(
    rows: list[dict[str, Any]],
    *,
    batch_id: str,
    target_runs: int,
    scenario_ids: list[str],
    scenario_count: int,
) -> dict[str, Any]:
    axes = ("actor_profile", "evidence_order", "conflict_intensity", "distractor_count", "object_family")
    per_scenario_axis_counts: dict[str, dict[str, dict[str, int]]] = {}
    for scenario_id in sorted({row["scenario_id"] for row in rows}):
        scenario_rows = [row for row in rows if row["scenario_id"] == scenario_id]
        per_scenario_axis_counts[scenario_id] = {
            axis: dict(Counter(str(row[axis]) for row in scenario_rows))
            for axis in (*axes, "path_type", "prompt_variant_id")
        }
    scenario_values = [row["scenario_id"] for row in rows]
    scenario_entropy = entropy(scenario_values)
    mi_checks = {}
    leakage_pass = True
    if len(rows) < 140:
        leakage_check = "insufficient_sample"
    else:
        for axis in axes:
            axis_values = [str(row[axis]) for row in rows]
            mi = mutual_information(scenario_values, axis_values)
            budget = 0.1 * scenario_entropy
            passed = mi < budget
            leakage_pass = leakage_pass and passed
            mi_checks[axis] = {"mi": mi, "budget": budget, "passed": passed}
        leakage_check = "pass" if leakage_pass else "fail"
    return {
        "batch_id": batch_id,
        "mode": "dry-run",
        "target_runs": target_runs,
        "scenario_count": scenario_count,
        "scenario_run_count": len(rows),
        "actor_prompt_count": len(rows),
        "scenario_ids": scenario_ids,
        "covered_scenario_ids": sorted({row["scenario_id"] for row in rows}),
        "all_catalog_scenarios_covered": set(scenario_ids) <= {row["scenario_id"] for row in rows},
        "family_counts": dict(Counter(row["scenario_family"] for row in rows)),
        "path_type_counts": dict(Counter(row["path_type"] for row in rows)),
        "label_source_counts": dict(Counter(row["label_source"] for row in rows)),
        "per_scenario_axis_counts": per_scenario_axis_counts,
        "mutual_information_checks": mi_checks,
        "leakage_check": leakage_check,
        "public_release_ready": False,
    }


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
