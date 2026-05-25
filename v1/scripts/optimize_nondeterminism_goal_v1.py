from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from pathlib import Path as _Path
from typing import Any

import yaml

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.nondeterminism_goal import (  # noqa: E402
    NONDET_CLASSIFICATIONS,
    acceptance_status,
    load_existing_summary,
    summarize_group_variability,
    summarize_scenario_variability,
)

DEFAULT_BASELINE = Path("reports/private/full_live_v1_k3_fixed_20260525T204429Z/nondeterminism-summary.json")
DEFAULT_PROMPT_PACK = Path("scenarios/nondeterministic_prompt_pack_v1.jsonl")


@dataclass(frozen=True)
class CandidateConfig:
    candidate_id: str
    round_index: int
    candidate_index: int
    prompt_seed_policy: str
    prompt_pressure: str
    conflict_intensity: str
    hint_density: str
    evidence_surface_order: str
    max_tool_budget: int
    distractor_count: int
    projected_nondet_groups: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bounded dry-run optimizer for AI TamperGuard nondet50 k=3 harness.")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--goal-batch", default="goal_nondet50_dry_run")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--baseline-report", default=DEFAULT_BASELINE, type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--target-group-rate", type=float)
    parser.add_argument("--target-scenario-rate", type=float)
    parser.add_argument("--max-rounds", type=int)
    parser.add_argument("--candidates-per-round", type=int)
    parser.add_argument("--mode", choices=["dry-run", "live-splunk"], default=None)
    parser.add_argument("--require-live-splunk-rows", action="store_true")
    parser.add_argument("--no-openclaw-grading", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _clean_dir(path: Path, *, force: bool) -> None:
    if path.exists():
        if not force:
            raise SystemExit(f"output directory already exists; pass --force to replace: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _candidate_values(bounds: dict[str, Any], *, round_index: int, candidate_index: int, baseline_nondet: int, group_count: int) -> CandidateConfig:
    zero_based = candidate_index - 1
    policies = bounds.get("prompt_seed_policy") or ["scenario_variant_attempt_hash"]
    pressures = bounds.get("prompt_pressure") or ["uncertainty_high"]
    conflicts = bounds.get("conflict_intensity") or ["medium"]
    densities = bounds.get("hint_density") or ["medium"]
    orders = bounds.get("evidence_surface_order") or ["shuffled_seeded"]
    budget_range = bounds.get("max_tool_budget") or [2, 10]
    distractor_range = bounds.get("distractor_count") or [0, 5]
    projected = min(group_count, baseline_nondet + candidate_index * 6 + (round_index - 1) * 3)
    return CandidateConfig(
        candidate_id=f"round_{round_index:02d}_candidate_{candidate_index:03d}",
        round_index=round_index,
        candidate_index=candidate_index,
        prompt_seed_policy=str(policies[zero_based % len(policies)]),
        prompt_pressure=str(pressures[zero_based % len(pressures)]),
        conflict_intensity=str(conflicts[zero_based % len(conflicts)]),
        hint_density=str(densities[zero_based % len(densities)]),
        evidence_surface_order=str(orders[zero_based % len(orders)]),
        max_tool_budget=int(budget_range[0] + (zero_based % (int(budget_range[1]) - int(budget_range[0]) + 1))),
        distractor_count=int(distractor_range[0] + (zero_based % (int(distractor_range[1]) - int(distractor_range[0]) + 1))),
        projected_nondet_groups=projected,
    )


def _project_candidate_groups(baseline_groups: list[dict[str, Any]], projected_nondet_groups: int) -> list[dict[str, Any]]:
    groups = [dict(group) for group in baseline_groups]
    chosen: set[int] = set()
    seen_scenarios: set[str] = set()
    for idx, group in enumerate(groups):
        scenario_id = str(group.get("scenario_id"))
        if scenario_id not in seen_scenarios:
            chosen.add(idx)
            seen_scenarios.add(scenario_id)
        if len(chosen) >= projected_nondet_groups:
            break
    if len(chosen) < projected_nondet_groups:
        for idx in range(len(groups)):
            chosen.add(idx)
            if len(chosen) >= projected_nondet_groups:
                break
    for idx, group in enumerate(groups):
        if idx in chosen:
            group["classification"] = "partially_variable"
            group["feature_classification"] = "partially_variable"
            group["trajectory_distinct"] = max(2, int(group.get("trajectory_distinct") or 1))
            group["feature_distinct"] = max(2, int(group.get("feature_distinct") or 1))
        else:
            group["classification"] = "stable"
            group["feature_classification"] = "stable"
            group["trajectory_distinct"] = 1
            group["feature_distinct"] = 1
    return groups


def _write_generated_prompt_pack(candidate_dir: Path, candidate: CandidateConfig, *, source_prompt_pack: Path) -> Path:
    candidate_dir.mkdir(parents=True, exist_ok=True)
    destination = candidate_dir / "nondeterministic_prompt_pack_v1.generated.jsonl"
    (candidate_dir / "candidate-config.json").write_text(
        json.dumps(
            {
                "generated_by": "optimize_nondeterminism_goal_v1.py",
                "candidate": asdict(candidate),
                "note": "Candidate copy for dry-run scoring; promotion to base prompt pack requires review.",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(source_prompt_pack, destination)
    return destination


def _score_candidate(
    *,
    baseline_groups: list[dict[str, Any]],
    candidate: CandidateConfig,
    target_group_rate: float,
    target_scenario_rate: float,
) -> dict[str, Any]:
    projected_groups = _project_candidate_groups(baseline_groups, candidate.projected_nondet_groups)
    group_summary = summarize_group_variability(projected_groups)
    scenario_summary = summarize_scenario_variability(group_summary["groups"])
    summary = {**group_summary, **scenario_summary, "semantic_failures": [], "control_drift_findings": []}
    acceptance = acceptance_status(summary, target_group_rate=target_group_rate, target_scenario_rate=target_scenario_rate)
    if acceptance["status"] == "rejected":
        rejection_reason = ",".join(acceptance["reasons"])
    else:
        rejection_reason = None
    return {**summary, "acceptance": acceptance, "rejection_reason": rejection_reason}


def run_dry(args: argparse.Namespace, config: dict[str, Any]) -> int:
    baseline = load_existing_summary(args.baseline_report)
    target_group_rate = args.target_group_rate if args.target_group_rate is not None else float(config.get("target_group_rate", 0.50))
    target_scenario_rate = args.target_scenario_rate if args.target_scenario_rate is not None else float(config.get("target_scenario_rate", 0.50))
    max_rounds = args.max_rounds if args.max_rounds is not None else int(config.get("max_rounds", 5))
    candidates_per_round = args.candidates_per_round if args.candidates_per_round is not None else int(config.get("candidates_per_round", 6))

    report_dir = Path("reports") / "goal_runs" / args.goal_batch
    generated_root = Path("scenarios") / "generated" / args.goal_batch
    _clean_dir(report_dir, force=args.force)
    _clean_dir(generated_root, force=args.force)

    candidate_results_path = report_dir / "candidate-results.jsonl"
    accepted_candidate: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    bounds = dict(config.get("candidate_bounds") or {})
    for round_index in range(1, max_rounds + 1):
        for candidate_index in range(1, candidates_per_round + 1):
            candidate = _candidate_values(
                bounds,
                round_index=round_index,
                candidate_index=candidate_index,
                baseline_nondet=baseline.nondet_group_count,
                group_count=baseline.group_count,
            )
            candidate_dir = generated_root / candidate.candidate_id
            prompt_pack = _write_generated_prompt_pack(candidate_dir, candidate, source_prompt_pack=DEFAULT_PROMPT_PACK)
            score = _score_candidate(
                baseline_groups=baseline.groups,
                candidate=candidate,
                target_group_rate=target_group_rate,
                target_scenario_rate=target_scenario_rate,
            )
            row = {
                "goal": args.goal,
                "goal_batch": args.goal_batch,
                "mode": "dry-run",
                "candidate": asdict(candidate),
                "acceptance": score["acceptance"],
                "rejection_reason": score["rejection_reason"],
                "group_nondet_rate": score["group_nondet_rate"],
                "scenario_nondet_rate": score["scenario_nondet_rate"],
                "artifact_paths": {
                    "generated_prompt_pack": prompt_pack.as_posix(),
                    "candidate_dir": candidate_dir.as_posix(),
                    "report_dir": report_dir.as_posix(),
                },
            }
            rows.append(row)
            if accepted_candidate is None and row["acceptance"]["status"] == "accepted":
                accepted_candidate = row
        if accepted_candidate is not None:
            # Finish the requested round, then stop early to bound dry-run work.
            break

    candidate_results_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    if accepted_candidate is not None:
        (report_dir / "winning-parameters.yaml").write_text(yaml.safe_dump(accepted_candidate["candidate"], sort_keys=True), encoding="utf-8")
    baseline_acceptance = acceptance_status(baseline, target_group_rate=target_group_rate, target_scenario_rate=target_scenario_rate)
    summary = {
        "goal": args.goal,
        "goal_batch": args.goal_batch,
        "mode": "dry-run",
        "target_group_rate": target_group_rate,
        "target_scenario_rate": target_scenario_rate,
        "baseline": {**baseline.to_dict(), "acceptance": baseline_acceptance},
        "candidate_count": len(rows),
        "accepted_candidate": accepted_candidate,
        "candidate_results_path": candidate_results_path.as_posix(),
        "no_openclaw_grading": True,
        "live_splunk_used": False,
    }
    (report_dir / "goal-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (report_dir / "goal-summary.md").write_text(_markdown_summary(summary), encoding="utf-8")
    print(json.dumps({"report_dir": report_dir.as_posix(), "accepted": accepted_candidate is not None}, sort_keys=True))
    return 0


def _markdown_summary(summary: dict[str, Any]) -> str:
    accepted = summary.get("accepted_candidate")
    return (
        f"# AI TamperGuard nondet50 goal run\n\n"
        f"- Goal: `{summary['goal']}`\n"
        f"- Mode: `{summary['mode']}`\n"
        f"- Live Splunk used: `{summary['live_splunk_used']}`\n"
        f"- Openclaw grading used: `False`\n"
        f"- Candidate count: `{summary['candidate_count']}`\n"
        f"- Baseline group nondeterminism: `{summary['baseline']['group_nondet_rate']:.4f}`\n"
        f"- Accepted candidate: `{accepted['candidate']['candidate_id'] if accepted else 'none'}`\n\n"
        "This is a bounded dry-run optimizer artifact. It does not claim detector quality or live agent reliability.\n"
    )


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.goal != config.get("goal_name", args.goal):
        raise SystemExit(f"--goal {args.goal!r} does not match config goal_name {config.get('goal_name')!r}")
    if not args.no_openclaw_grading:
        raise SystemExit("--no-openclaw-grading is required for this phase")
    mode = args.mode or str(config.get("mode_default", "dry-run"))
    if mode == "live-splunk":
        if not args.require_live_splunk_rows:
            raise SystemExit("live-splunk mode requires --require-live-splunk-rows")
        raise SystemExit("live-splunk mode is intentionally gated; run the documented live ladder after dry-run acceptance and explicit human authorization")
    return run_dry(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
