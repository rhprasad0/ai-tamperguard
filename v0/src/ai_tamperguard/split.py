from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


class SplitError(ValueError):
    """Raised when behavior windows cannot be split safely."""


@dataclass(frozen=True)
class SplitResult:
    train: list[dict[str, Any]]
    holdout: list[dict[str, Any]]
    manifest: dict[str, Any]


def split_windows(
    rows: Iterable[Mapping[str, Any]],
    *,
    seed: int,
    holdout_fraction: float = 0.2,
) -> SplitResult:
    """Create a deterministic stratified train/holdout split for v0 behavior windows."""
    normalized = [_normalize_row(row) for row in rows]
    if not normalized:
        raise SplitError("split requires at least one behavior-window row")
    if not 0 < holdout_fraction < 1:
        raise SplitError("holdout_fraction must be greater than 0 and less than 1")

    by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen_window_ids: set[str] = set()
    for row in sorted(normalized, key=lambda item: str(item["window_id"])):
        window_id = str(row["window_id"])
        if window_id in seen_window_ids:
            raise SplitError(f"duplicate window_id in split input: {window_id}")
        seen_window_ids.add(window_id)
        by_label[int(row["label_binary"])].append(row)

    if set(by_label) != {0, 1}:
        raise SplitError("deterministic split requires both label classes 0 and 1")

    train: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for label in (0, 1):
        label_rows = list(by_label[label])
        if len(label_rows) < 2:
            raise SplitError(f"label class {label} needs at least two rows for disjoint train/holdout split")
        shuffled = list(label_rows)
        random.Random(f"{seed}:{label}").shuffle(shuffled)
        holdout_count = min(len(shuffled) - 1, max(1, math.ceil(len(shuffled) * holdout_fraction)))
        holdout.extend(shuffled[:holdout_count])
        train.extend(shuffled[holdout_count:])

    train = sorted(train, key=lambda item: str(item["window_id"]))
    holdout = sorted(holdout, key=lambda item: str(item["window_id"]))
    _assert_disjoint(train, holdout)

    manifest = _manifest_for_split(normalized, train, holdout, seed=seed, holdout_fraction=holdout_fraction)
    return SplitResult(train=train, holdout=holdout, manifest=manifest)


def write_split(
    *,
    input_path: Path,
    train_output_path: Path,
    holdout_output_path: Path,
    manifest_output_path: Path,
    seed: int,
    holdout_fraction: float = 0.2,
) -> dict[str, Any]:
    """Read behavior-window CSV, write train/holdout CSVs, and persist a split manifest."""
    input_path = Path(input_path)
    train_output_path = Path(train_output_path)
    holdout_output_path = Path(holdout_output_path)
    manifest_output_path = Path(manifest_output_path)

    input_frame = pd.read_csv(input_path)
    result = split_windows(input_frame.to_dict(orient="records"), seed=seed, holdout_fraction=holdout_fraction)

    train_output_path.parent.mkdir(parents=True, exist_ok=True)
    holdout_output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = list(input_frame.columns)
    pd.DataFrame(result.train, columns=columns).to_csv(train_output_path, index=False)
    pd.DataFrame(result.holdout, columns=columns).to_csv(holdout_output_path, index=False)

    manifest = dict(result.manifest)
    manifest.update(
        {
            "paths": {
                "input": str(input_path),
                "train": str(train_output_path),
                "holdout": str(holdout_output_path),
            },
            "file_hashes_sha256": {
                "input": sha256_file(input_path),
                "train": sha256_file(train_output_path),
                "holdout": sha256_file(holdout_output_path),
            },
        }
    )
    manifest_output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    row_dict = dict(row)
    window_id = row_dict.get("window_id")
    if window_id in (None, ""):
        raise SplitError("every row must include a non-empty window_id")
    label_value = row_dict.get("label_binary", row_dict.get("label"))
    if label_value in (None, ""):
        raise SplitError(f"row {window_id} is missing label_binary")
    try:
        label_binary = int(label_value)
    except (TypeError, ValueError) as exc:
        raise SplitError(f"row {window_id} has non-integer label_binary: {label_value!r}") from exc
    if label_binary not in {0, 1}:
        raise SplitError(f"row {window_id} has unsupported label_binary {label_binary}; expected 0 or 1")
    row_dict["window_id"] = str(window_id)
    row_dict["label_binary"] = label_binary
    if "label" in row_dict:
        row_dict["label"] = label_binary
    return row_dict


def _assert_disjoint(train: Sequence[Mapping[str, Any]], holdout: Sequence[Mapping[str, Any]]) -> None:
    train_ids = {str(row["window_id"]) for row in train}
    holdout_ids = {str(row["window_id"]) for row in holdout}
    overlap = train_ids.intersection(holdout_ids)
    if overlap:
        raise SplitError(f"train and holdout window_id sets overlap: {', '.join(sorted(overlap))}")


def _manifest_for_split(
    input_rows: Sequence[Mapping[str, Any]],
    train: Sequence[Mapping[str, Any]],
    holdout: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    holdout_fraction: float,
) -> dict[str, Any]:
    return {
        "split_version": "v0",
        "random_seed": seed,
        "holdout_fraction": holdout_fraction,
        "id_column": "window_id",
        "label_column": "label_binary",
        "counts": {
            "input_total": len(input_rows),
            "train_total": len(train),
            "holdout_total": len(holdout),
            "input_by_label": _counts_by_label(input_rows),
            "train_by_label": _counts_by_label(train),
            "holdout_by_label": _counts_by_label(holdout),
        },
    }


def _counts_by_label(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(int(row["label_binary"])) for row in rows)
    return {label: int(counts.get(label, 0)) for label in ("0", "1")}
