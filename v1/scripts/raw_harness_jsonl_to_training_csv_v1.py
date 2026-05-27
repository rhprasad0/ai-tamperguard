from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path as _Path
from typing import Any

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.derive import derive_windows  # noqa: E402
from ai_tamperguard_v1.io import read_jsonl, write_csv_rows  # noqa: E402
from ai_tamperguard_v1.schema import load_schema, validate_rows  # noqa: E402

EVENT_FILE_NAME = "public_safe_events.jsonl"
ID_COLUMNS = [
    "window_id",
    "scenario_run_id",
    "reset_id",
    "actor_id",
    "window_type",
    "window_start_relative_sec",
    "window_end_relative_sec",
]
LABEL_COLUMNS = ["label_binary", "label_family", "label_source", "label_confidence", "outcome", "split_id"]
AUDIT_COLUMNS = ["source_batch_id"]


class UserInputError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert AI TamperGuard V1 raw harness JSONL into window-level training CSV.")
    parser.add_argument("--input", action="append", required=True, help="Batch dir, scenario dir, or public_safe_events.jsonl file. Repeatable.")
    parser.add_argument("--answer-key", help="JSONL answer key with scenario_run_id and label_family.")
    parser.add_argument("--run-manifest", help="Run manifest JSONL used to synthesize labels when no answer key is provided.")
    parser.add_argument("--output", required=True, help="Output training CSV path.")
    parser.add_argument("--window-size-sec", type=int, default=900, help="Behavior window size in seconds. Default: 900.")
    parser.add_argument("--allow-unlabeled", action="store_true", help="Emit background_unlabeled labels for debug exports.")
    parser.add_argument("--add-source-batch-column", action="store_true", help="Deprecated no-op; source_batch_id is always emitted.")
    parser.add_argument("--allow-public-output", action="store_true", help="Allow output outside data/training for explicitly reviewed public fixtures.")
    parser.add_argument("--fail-on-empty", dest="fail_on_empty", action="store_true", default=True)
    parser.add_argument("--no-fail-on-empty", dest="fail_on_empty", action="store_false")
    args = parser.parse_args()

    try:
        if args.window_size_sec <= 0:
            raise UserInputError("--window-size-sec must be positive")
        output = _Path(args.output)
        if not args.allow_public_output and not _is_under_training(output):
            raise UserInputError("output must stay under data/training unless --allow-public-output is set")
        event_files = discover_event_files([_Path(value) for value in args.input])
        if not event_files and args.fail_on_empty:
            raise UserInputError("no public_safe_events.jsonl files discovered")
        events, source_by_run = load_events(event_files)
        if not events and args.fail_on_empty:
            raise UserInputError("no input event rows discovered")
        validate_rows("normalized_event_v1.schema.json", events)
        reject_duplicate_runs_across_batches(source_by_run)
        answer_key = load_labels(
            events,
            answer_key_path=_Path(args.answer_key) if args.answer_key else None,
            run_manifest_path=_Path(args.run_manifest) if args.run_manifest else None,
            allow_unlabeled=args.allow_unlabeled,
        )
        require_labels_for_events(events, answer_key, allow_unlabeled=args.allow_unlabeled)
        rows = derive_windows(_ordered_events(events), answer_key, size_sec=args.window_size_sec)
        if not rows and args.fail_on_empty:
            raise UserInputError("no derived behavior-window rows produced")
        validate_rows("behavior_window_v1.schema.json", rows)
        rows = add_source_audit_columns(rows, source_by_run, len(event_files))
        rows = published_training_rows(rows)
        fieldnames = output_fieldnames(rows)
        write_csv_rows(output, rows, fieldnames=fieldnames)
    except UserInputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"failed to build training CSV: {exc}", file=sys.stderr)
        return 1
    return 0


def discover_event_files(inputs: list[_Path]) -> list[_Path]:
    files: list[_Path] = []
    for input_path in inputs:
        path = input_path
        if path.is_file():
            if path.name != EVENT_FILE_NAME:
                raise UserInputError(f"input file must be named {EVENT_FILE_NAME}: {path}")
            files.append(path)
            continue
        if not path.exists():
            raise UserInputError(f"input path does not exist: {path}")
        scenario_event_file = path / EVENT_FILE_NAME
        if scenario_event_file.exists():
            files.append(scenario_event_file)
            continue
        files.extend(sorted(path.glob(f"*/{EVENT_FILE_NAME}")))
    deduped: list[_Path] = []
    seen: set[str] = set()
    for file_path in sorted(files, key=lambda p: p.as_posix()):
        key = file_path.resolve().as_posix()
        if key not in seen:
            seen.add(key)
            deduped.append(file_path)
    return deduped


def load_events(event_files: list[_Path]) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    events: list[dict[str, Any]] = []
    source_by_run: dict[str, set[str]] = defaultdict(set)
    for event_file in event_files:
        batch_id = source_batch_id(event_file)
        for row in read_jsonl(event_file):
            run_id = str(row.get("scenario_run_id", ""))
            if run_id:
                source_by_run[run_id].add(batch_id)
            events.append(row)
    return events, source_by_run


def source_batch_id(event_file: _Path) -> str:
    # Known shape: raw_exports/<batch_id>/<scenario_run_id>/public_safe_events.jsonl
    return event_file.parent.parent.name if event_file.parent.parent.name else "unknown_batch"


def reject_duplicate_runs_across_batches(source_by_run: dict[str, set[str]]) -> None:
    duplicates = {run_id: sorted(batches) for run_id, batches in source_by_run.items() if len(batches) > 1}
    if duplicates:
        detail = ", ".join(f"{run_id}={batches}" for run_id, batches in sorted(duplicates.items()))
        raise UserInputError(f"duplicate scenario_run_id across batches; rerun with --namespace-repeated-runs after that mode is implemented: {detail}")


def _is_under_training(path: _Path) -> bool:
    output_path = path.expanduser().resolve()
    training_root = (_Path.cwd() / "data" / "training").resolve()
    return output_path == training_root or output_path.is_relative_to(training_root)


# Backward-compatible alias for older imports.
_is_under_private_training = _is_under_training


def _ordered_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        events,
        key=lambda event: (
            str(event.get("scenario_run_id", "")),
            str(event.get("actor_id", "")),
            int(event.get("relative_time_sec", 0)),
            str(event.get("event_id", "")),
        ),
    )


def load_labels(
    events: list[dict[str, Any]],
    *,
    answer_key_path: _Path | None,
    run_manifest_path: _Path | None,
    allow_unlabeled: bool,
) -> list[dict[str, Any]]:
    if answer_key_path is not None:
        rows = read_jsonl(answer_key_path)
        if not rows:
            raise UserInputError(f"answer key is empty: {answer_key_path}")
        return normalize_label_rows(rows, default_source="scenario_answer_key")
    if run_manifest_path is not None:
        run_rows = read_jsonl(run_manifest_path)
        if not run_rows:
            raise UserInputError(f"run manifest is empty: {run_manifest_path}")
        reject_duplicate_label_rows(run_rows, context="run manifest")
        require_run_manifest_ground_truth(run_rows, allow_unlabeled=allow_unlabeled)
        return [
            {
                "scenario_run_id": row["scenario_run_id"],
                "label_family": row.get("ground_truth_family", "background_unlabeled"),
                "label_source": row.get("label_source", "post_run_verification"),
                "label_confidence": row.get("label_confidence", 1.0),
                "outcome": row.get("outcome", "background_unlabeled"),
                "reset_id": row.get("reset_id", "reset_000"),
            }
            for row in run_rows
            if row.get("scenario_run_id")
        ]
    if allow_unlabeled:
        print("WARNING: emitting unlabeled debug training CSV", file=sys.stderr)
        return [
            {
                "scenario_run_id": run_id,
                "label_family": "background_unlabeled",
                "label_source": "background_unlabeled",
            }
            for run_id in sorted({str(event.get("scenario_run_id")) for event in events if event.get("scenario_run_id")})
        ]
    raise UserInputError("labels are required; provide --answer-key, --run-manifest, or --allow-unlabeled")


def normalize_label_rows(rows: list[dict[str, Any]], *, default_source: str) -> list[dict[str, Any]]:
    reject_duplicate_label_rows(rows, context="answer key")
    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        run_id = row.get("scenario_run_id")
        family = row.get("label_family")
        if not run_id or not family:
            raise UserInputError(f"label row {idx} must include scenario_run_id and label_family")
        normalized.append({**row, "label_source": row.get("label_source", default_source)})
    return normalized


def reject_duplicate_label_rows(rows: list[dict[str, Any]], *, context: str) -> None:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        run_id = row.get("scenario_run_id")
        if run_id:
            counts[str(run_id)] += 1
    duplicates = sorted(run_id for run_id, count in counts.items() if count > 1)
    if duplicates:
        raise UserInputError(f"duplicate label rows in {context}: {', '.join(duplicates)}")


def require_run_manifest_ground_truth(rows: list[dict[str, Any]], *, allow_unlabeled: bool) -> None:
    if allow_unlabeled:
        return
    missing = sorted(str(row.get("scenario_run_id")) for row in rows if row.get("scenario_run_id") and not row.get("ground_truth_family"))
    if missing:
        raise UserInputError("ground_truth_family is required for run manifest rows: " + ", ".join(missing))


def require_labels_for_events(events: list[dict[str, Any]], answer_key: list[dict[str, Any]], *, allow_unlabeled: bool) -> None:
    if allow_unlabeled:
        return
    event_run_ids = {str(event.get("scenario_run_id")) for event in events if event.get("scenario_run_id")}
    label_run_ids = {str(row.get("scenario_run_id")) for row in answer_key if row.get("scenario_run_id")}
    missing = sorted(event_run_ids - label_run_ids)
    if missing:
        raise UserInputError("labels missing for scenario_run_id: " + ", ".join(missing))


def add_source_audit_columns(rows: list[dict[str, Any]], source_by_run: dict[str, set[str]], file_count: int) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        run_id = str(row.get("scenario_run_id", ""))
        batches = sorted(source_by_run.get(run_id, {"unknown_batch"}))
        source_batch = batches[0] if len(batches) == 1 else "mixed"
        audited.append({**row, "source_batch_id": source_batch, "source_input_path_count": file_count})
    return audited


def output_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    schema_props = load_schema("behavior_window_v1.schema.json").get("properties", {})
    feature_columns = [key for key in schema_props if key.startswith("feature_")]
    known = ID_COLUMNS + feature_columns + LABEL_COLUMNS + AUDIT_COLUMNS
    extras: list[str] = []
    for row in rows:
        for key in row:
            if key not in known and key not in extras:
                extras.append(key)
    return [key for key in known if any(key in row for row in rows)] + extras


def published_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the public training boundary: IDs/labels plus feature_* only.

    Run-manifest provenance such as scenario_id/path_type/prompt IDs, bulky source
    audit columns, and actor prompt paths stays in private manifests, not published
    CSVs. source_batch_id is retained as reviewed non-feature lineage metadata.
    """
    allowed = set(ID_COLUMNS + LABEL_COLUMNS + AUDIT_COLUMNS)
    return [
        {key: value for key, value in row.items() if key in allowed or key.startswith("feature_")}
        for row in rows
    ]


if __name__ == "__main__":
    raise SystemExit(main())
