import pytest

from ai_tamperguard.labels import LABEL_RULE_DESCRIPTION, LABEL_RULE_ID, apply_weak_label, apply_weak_labels


def window(**feature_overrides):
    row = {
        "window_id": "actor_60m:2026-05-24T12:00:00Z:actor",
        "window_type": "actor_60m",
        "window_start": "2026-05-24T12:00:00Z",
        "window_end": "2026-05-24T13:00:00Z",
        "feature_event_count": 1,
        "feature_search_count": 1,
        "feature_admin_action_count": 0,
        "feature_config_action_count": 0,
        "feature_token_or_rbac_action_count": 0,
        "feature_index_or_input_action_count": 0,
        "feature_failed_action_count": 0,
        "feature_success_action_count": 1,
        "feature_after_hours_admin_activity": 0,
        "feature_distinct_action_category_count": 1,
    }
    row.update(feature_overrides)
    return row


def test_search_only_window_gets_needs_review_label_zero():
    labeled = apply_weak_label(window())

    assert labeled["label"] == 0
    assert labeled["label_binary"] == 0
    assert labeled["label_value_description"] == "needs_review"
    assert labeled["label_source"] == "weak_proxy_v0"
    assert labeled["label_rule_id"] == LABEL_RULE_ID
    assert labeled["label_rule_description"] == LABEL_RULE_DESCRIPTION


@pytest.mark.parametrize(
    "feature_name",
    [
        "feature_admin_action_count",
        "feature_config_action_count",
        "feature_token_or_rbac_action_count",
        "feature_index_or_input_action_count",
        "feature_after_hours_admin_activity",
    ],
)
def test_admin_config_token_rbac_index_or_after_hours_features_get_positive_proxy(feature_name):
    labeled = apply_weak_label(window(**{feature_name: 1}))

    assert labeled["label"] == 1
    assert labeled["label_binary"] == 1
    assert labeled["label_value_description"] == "working_model_positive_proxy"
    assert labeled["label_source"] == "weak_proxy_v0"


def test_apply_weak_labels_preserves_input_rows_and_adds_stable_metadata():
    original = [window(feature_search_count=3), window(feature_admin_action_count=1)]

    labeled = apply_weak_labels(original)

    assert [row["label_binary"] for row in labeled] == [0, 1]
    assert "label" not in original[0]
    assert {row["label_rule_id"] for row in labeled} == {"weak_proxy_v0_admin_control_plane_activity"}
    assert all(isinstance(row["label_rule_description"], str) and row["label_rule_description"] for row in labeled)
