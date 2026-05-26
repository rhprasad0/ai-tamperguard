from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.io import read_csv_rows, read_jsonl, write_csv_rows

SPLITS = ("train", "validate", "test")
ID_COLUMNS = {"window_id", "scenario_run_id", "actor_id", "window_start_relative_sec", "window_end_relative_sec"}
LABEL_COLUMNS = {"label_binary", "label_family", "label_source", "split_id"}
OPTIONAL_PUBLIC_COLUMNS = {"reset_id", "window_type", "label_confidence", "outcome"}
FORBIDDEN_PUBLIC_WINDOW_COLUMNS = {
    "scenario_id",
    "path_type",
    "prompt_variant_id",
    "actor_prompt_path",
    "synthetic_case_id",
    "source_batch_id",
    "source_input_path_count",
    "allocation_bucket",
}


class UserInputError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate leakage-aware train/validate/test CSV splits.")
    parser.add_argument("--windows", required=True)
    parser.add_argument("--scenario-runs", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=20260525)
    args = parser.parse_args()

    try:
        rows = read_csv_rows(Path(args.windows))
        runs = read_jsonl(Path(args.scenario_runs))
        if not rows:
            raise UserInputError("windows CSV is empty")
        _validate_public_window_columns(rows)
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        split_rows, leakage_report = build_splits(rows, seed=args.seed)
        for split, split_rs in split_rows.items():
            write_csv_rows(out / f"{split}_windows.csv", sorted(split_rs, key=lambda row: row["window_id"]))
        _write_heldout_scenarios(out, runs)
        manifest = build_manifest(
            rows=rows,
            split_rows=split_rows,
            runs=runs,
            seed=args.seed,
            source_window_file=Path(args.windows),
            leakage_report=leakage_report,
        )
        (out / "split_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except UserInputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def _validate_public_window_columns(rows: list[dict[str, Any]]) -> None:
    columns = set().union(*(row.keys() for row in rows))
    forbidden = sorted(columns & FORBIDDEN_PUBLIC_WINDOW_COLUMNS)
    if forbidden:
        raise UserInputError("forbidden public window columns: " + ", ".join(forbidden))
    unexpected = sorted(
        key for key in columns
        if key not in ID_COLUMNS and key not in LABEL_COLUMNS and key not in OPTIONAL_PUBLIC_COLUMNS and not key.startswith("feature_")
    )
    if unexpected:
        raise UserInputError("unexpected public window columns: " + ", ".join(unexpected))


def build_splits(rows: list[dict[str, Any]], *, seed: int) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        run_id = str(row.get("scenario_run_id", ""))
        if not run_id:
            raise UserInputError("scenario_run_id is required for split grouping")
        groups[run_id].append(row)

    run_ids = sorted(groups)
    random.Random(seed).shuffle(run_ids)
    run_to_split = {run_id: SPLITS[idx % len(SPLITS)] for idx, run_id in enumerate(run_ids)}
    split_rows = {split: [] for split in SPLITS}
    for run_id in sorted(groups):
        split = run_to_split[run_id]
        for row in groups[run_id]:
            updated = dict(row)
            updated["split_id"] = split
            split_rows[split].append(updated)

    leakage_report = _leakage_report(split_rows)
    if leakage_report["scenario_run_overlap"]:
        raise UserInputError("scenario_run_id overlap across splits")
    return split_rows, leakage_report


def _leakage_report(split_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    run_to_splits: dict[str, set[str]] = defaultdict(set)
    window_to_splits: dict[str, set[str]] = defaultdict(set)
    for split, rows in split_rows.items():
        for row in rows:
            run_to_splits[str(row.get("scenario_run_id", ""))].add(split)
            window_to_splits[str(row.get("window_id", ""))].add(split)
    return {
        "scenario_run_overlap": any(len(splits) > 1 for splits in run_to_splits.values()),
        "window_id_overlap": any(len(splits) > 1 for splits in window_to_splits.values()),
        "forbidden_public_window_columns_present": [],
        "split_grouping_key": "scenario_run_id",
    }


def _write_heldout_scenarios(out: Path, runs: list[dict[str, Any]]) -> None:
    scenario_ids = sorted({str(row.get("scenario_id")) for row in runs if row.get("scenario_id")})
    with (out / "heldout_scenarios.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scenario_id", "holdout_reason"])
        writer.writeheader()
        if scenario_ids:
            writer.writerow({"scenario_id": scenario_ids[-1], "holdout_reason": "scenario-family holdout exercise"})


def build_manifest(
    *,
    rows: list[dict[str, Any]],
    split_rows: dict[str, list[dict[str, Any]]],
    runs: list[dict[str, Any]],
    seed: int,
    source_window_file: Path,
    leakage_report: dict[str, Any],
) -> dict[str, Any]:
    counts = {split: dict(Counter(row.get("label_binary", "") for row in split_rs)) for split, split_rs in split_rows.items()}
    split_summary = {
        split: {"row_count": len(split_rs), "label_counts": counts[split]}
        for split, split_rs in split_rows.items()
    }
    leakage_check = "pass" if not leakage_report["scenario_run_overlap"] and not leakage_report["window_id_overlap"] else "fail"
    return {
        "dataset_build_id": "v1-public-fixture-20260525",
        "seed": seed,
        "split_strategy": "scenario_run_grouped_seeded_round_robin",
        "source_window_file": source_window_file.as_posix(),
        "scenario_run_manifest_count": len(runs),
        "splits": split_summary,
        "public_window_column_policy": "ids_labels_and_feature_prefix_only",
        "leakage_check": leakage_check,
        "leakage_report": leakage_report,
        "relaxations": [],
    }


if __name__ == "__main__":
    raise SystemExit(main())
