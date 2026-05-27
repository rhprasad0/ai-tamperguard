from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import pandas as pd

SPLIT_NAMES = ("train", "validation", "test")


class SplitError(ValueError):
    """Raised when split assignment or validation fails."""


@dataclass(frozen=True)
class SplitResult:
    frame: pd.DataFrame
    strategy: str
    group_key: str
    distribution: dict[str, int]
    group_distribution: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "group_key": self.group_key,
            "distribution": self.distribution,
            "group_distribution": self.group_distribution,
        }


def assign_or_validate_splits(
    frame: pd.DataFrame,
    *,
    strategy: str,
    seed: int,
    group_key: str = "scenario_run_id",
    allow_small_fixture: bool = False,
) -> SplitResult:
    if "split_id" not in frame.columns:
        raise SplitError("input frame missing required column: split_id")
    if group_key not in frame.columns:
        raise SplitError(f"input frame missing split group key: {group_key}")
    values = set(frame["split_id"].astype(str))
    if values.issubset(set(SPLIT_NAMES)) and set(SPLIT_NAMES).issubset(values):
        out = frame.copy()
        _validate_disjoint_groups(out, group_key=group_key)
        _validate_class_coverage(out, allow_small_fixture=allow_small_fixture)
        return _result(out, strategy="provided_split_id", group_key=group_key)
    if values == {"unassigned"}:
        if strategy != "deterministic_hash":
            raise SplitError("unassigned split_id values require --split-strategy deterministic_hash")
        out = frame.copy()
        out["split_id"] = out[group_key].astype(str).map(lambda value: _bucket(value, seed))
        if set(out["split_id"]) != set(SPLIT_NAMES):
            out = _rebalance_tiny_grouped_fixture(out, group_key=group_key, seed=seed)
        _validate_disjoint_groups(out, group_key=group_key)
        _validate_class_coverage(out, allow_small_fixture=allow_small_fixture)
        return _result(out, strategy="deterministic_hash", group_key=group_key)
    if "unassigned" in values:
        raise SplitError("mixed explicit and unassigned split_id values are not supported")
    raise SplitError(f"split_id must contain train/validation/test or all unassigned, got: {sorted(values)}")


def _bucket(value: str, seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()
    pct = int(digest[:8], 16) / 0xFFFFFFFF
    if pct < 0.60:
        return "train"
    if pct < 0.80:
        return "validation"
    return "test"


def _rebalance_tiny_grouped_fixture(frame: pd.DataFrame, *, group_key: str, seed: int) -> pd.DataFrame:
    out = frame.copy()
    groups = sorted(out[group_key].astype(str).unique(), key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())
    if len(groups) < 3:
        raise SplitError("at least three groups are required for train/validation/test split assignment")
    targets = ["train", "validation", "test"]
    for group, split in zip(groups[:3], targets, strict=False):
        out.loc[out[group_key].astype(str) == group, "split_id"] = split
    return out


def _validate_disjoint_groups(frame: pd.DataFrame, *, group_key: str) -> None:
    counts = frame.groupby(group_key)["split_id"].nunique()
    overlapping = counts[counts > 1]
    if not overlapping.empty:
        raise SplitError(f"{group_key} appears in multiple splits: {sorted(map(str, overlapping.index.tolist()))}")
    if frame["window_id"].astype(str).duplicated().any():
        raise SplitError("window_id values must be unique before splitting")


def _validate_class_coverage(frame: pd.DataFrame, *, allow_small_fixture: bool) -> None:
    labels = pd.to_numeric(frame["label_binary"], errors="raise").astype(int)
    if not set(labels).issubset({0, 1}):
        raise SplitError("label_binary must contain only 0/1 values")
    check_splits = ("train", "validation") if allow_small_fixture else SPLIT_NAMES
    for split in check_splits:
        split_labels = set(labels[frame["split_id"] == split])
        if split_labels != {0, 1}:
            raise SplitError(f"{split} split must include both label classes 0 and 1")


def _result(frame: pd.DataFrame, *, strategy: str, group_key: str) -> SplitResult:
    distribution = {split: int((frame["split_id"] == split).sum()) for split in SPLIT_NAMES}
    group_distribution = {
        split: int(frame.loc[frame["split_id"] == split, group_key].astype(str).nunique()) for split in SPLIT_NAMES
    }
    return SplitResult(
        frame=frame,
        strategy=strategy,
        group_key=group_key,
        distribution=distribution,
        group_distribution=group_distribution,
    )
