from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

LABEL_RULE_ID = "weak_proxy_v0_admin_control_plane_activity"
LABEL_RULE_DESCRIPTION = (
    "working_model_positive_proxy when a window contains admin, config, token/RBAC, "
    "index/input, or after-hours admin/control-plane activity; not malicious ground truth"
)
_POSITIVE_PROXY_FEATURES = (
    "feature_admin_action_count",
    "feature_config_action_count",
    "feature_token_or_rbac_action_count",
    "feature_index_or_input_action_count",
    "feature_after_hours_admin_activity",
)


def apply_weak_label(window: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the deterministic v0 weak proxy label to one behavior window."""
    row = dict(window)
    label_binary = int(any(float(row.get(feature, 0) or 0) > 0 for feature in _POSITIVE_PROXY_FEATURES))
    row.update(
        {
            "label": label_binary,
            "label_binary": label_binary,
            "label_value_description": "working_model_positive_proxy" if label_binary else "needs_review",
            "label_source": "weak_proxy_v0",
            "label_rule_id": LABEL_RULE_ID,
            "label_rule_description": LABEL_RULE_DESCRIPTION,
        }
    )
    return row


def apply_weak_labels(windows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Apply the deterministic v0 weak proxy label to behavior windows."""
    return [apply_weak_label(window) for window in windows]
