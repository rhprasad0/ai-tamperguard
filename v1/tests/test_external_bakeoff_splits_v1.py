from __future__ import annotations

import pandas as pd
import pytest

from ai_tamperguard_v1.research.splits import SplitError, assign_or_validate_splits


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"window_id": f"w{i}", "scenario_run_id": f"run_{i // 2}", "label_binary": i % 2, "split_id": "unassigned"}
            for i in range(12)
        ]
    )


def test_deterministic_grouped_split_is_reproducible():
    first = assign_or_validate_splits(_frame(), strategy="deterministic_hash", seed=260527, allow_small_fixture=True)
    second = assign_or_validate_splits(_frame(), strategy="deterministic_hash", seed=260527, allow_small_fixture=True)

    assert first.frame["split_id"].tolist() == second.frame["split_id"].tolist()
    group_counts = first.frame.groupby("scenario_run_id")["split_id"].nunique()
    assert group_counts.max() == 1
    assert set(first.frame["split_id"]) == {"train", "validation", "test"}


def test_uses_explicit_split_id_when_available():
    frame = _frame()
    frame.loc[:5, "split_id"] = "train"
    frame.loc[6:7, "split_id"] = "validation"
    frame.loc[8:, "split_id"] = "test"

    result = assign_or_validate_splits(frame, strategy="deterministic_hash", seed=1, allow_small_fixture=True)

    assert result.strategy == "provided_split_id"
    assert result.frame["split_id"].tolist() == frame["split_id"].tolist()


def test_mixed_unassigned_and_explicit_splits_fail():
    frame = _frame()
    frame.loc[0, "split_id"] = "train"

    with pytest.raises(SplitError, match="mixed explicit and unassigned"):
        assign_or_validate_splits(frame, strategy="deterministic_hash", seed=1, allow_small_fixture=True)
