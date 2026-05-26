from __future__ import annotations

import math
from collections import Counter
from typing import Hashable, Iterable


def entropy(values: Iterable[Hashable]) -> float:
    items = list(values)
    if not items:
        return 0.0
    total = len(items)
    counts = Counter(items)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def mutual_information(left: Iterable[Hashable], right: Iterable[Hashable]) -> float:
    left_items = list(left)
    right_items = list(right)
    if len(left_items) != len(right_items):
        raise ValueError("mutual_information inputs must have equal length")
    if not left_items:
        return 0.0
    total = len(left_items)
    left_counts = Counter(left_items)
    right_counts = Counter(right_items)
    joint_counts = Counter(zip(left_items, right_items))
    score = 0.0
    for (left_value, right_value), joint_count in joint_counts.items():
        p_xy = joint_count / total
        p_x = left_counts[left_value] / total
        p_y = right_counts[right_value] / total
        score += p_xy * math.log2(p_xy / (p_x * p_y))
    return score


def normalized_mi(left: Iterable[Hashable], right: Iterable[Hashable]) -> float:
    left_items = list(left)
    h_left = entropy(left_items)
    if h_left == 0.0:
        return 0.0
    return mutual_information(left_items, list(right)) / h_left
