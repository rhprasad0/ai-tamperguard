import pytest
from jsonschema import ValidationError

from ai_tamperguard.schema import (
    validate_behavior_window,
    validate_holdout_fixture,
    validate_model_artifact,
)


FEATURES = {
    "feature_login_failures": 2,
    "feature_login_successes": 4,
    "feature_admin_actions": 1,
    "feature_config_changes": 0,
    "feature_search_count": 3,
    "feature_distinct_sources": 2,
    "feature_after_hours": True,
    "feature_rare_action_count": 0.5,
}


def valid_behavior_window(**overrides):
    row = {
        "window_id": "actor_60m:2026-05-24T12:00:00Z:synthetic-actor-001",
        "window_type": "actor_60m",
        "window_start": "2026-05-24T12:00:00Z",
        "window_end": "2026-05-24T13:00:00Z",
        "label": 1,
        "label_value_description": "working_model_positive_proxy",
        **FEATURES,
    }
    row.update(overrides)
    return row


def valid_model_artifact(**overrides):
    artifact = {
        "schema_version": "model_artifact_v0",
        "model_version": "v0_abc123",
        "model_type": "logistic_regression",
        "feature_order": list(FEATURES.keys()),
        "intercept": -0.25,
        "coefficients": [0.1, -0.2, 0.3, 0.0, 0.05, -0.07, 0.4, 0.9],
        "threshold": 0.5,
        "label_rule_id": "weak_proxy_v0",
        "training_metadata": {
            "python_version": "3.12.0",
            "sklearn_version": "1.4.0",
            "random_seed": 1729,
            "training_git_sha": "abcdef1234567890",
        },
        "score_envelope": {
            "score_field": "score_local",
            "probability_field": "probability_local",
            "prediction_field": "prediction_local",
        },
    }
    artifact.update(overrides)
    return artifact


def test_valid_behavior_window_passes():
    validate_behavior_window(valid_behavior_window(), public=True)


@pytest.mark.parametrize(
    "bad_feature_value",
    [None, "2"],
)
def test_behavior_window_rejects_null_or_string_features(bad_feature_value):
    row = valid_behavior_window(feature_login_failures=bad_feature_value)

    with pytest.raises(ValidationError):
        validate_behavior_window(row)


def test_behavior_window_rejects_wrong_window_type():
    row = valid_behavior_window(window_type="host_60m")

    with pytest.raises(ValidationError):
        validate_behavior_window(row)


def test_behavior_window_public_mode_rejects_private_columns():
    row = valid_behavior_window(actor_surrogate_private="private-synthetic-actor")

    with pytest.raises(ValidationError):
        validate_behavior_window(row, public=True)


def test_valid_model_artifact_passes():
    validate_model_artifact(valid_model_artifact())


def test_model_artifact_requires_core_single_source_of_truth_fields():
    required_fields = [
        "model_version",
        "feature_order",
        "intercept",
        "coefficients",
        "threshold",
        "label_rule_id",
        "training_metadata",
        "score_envelope",
    ]

    for field in required_fields:
        artifact = valid_model_artifact()
        artifact.pop(field)
        with pytest.raises(ValidationError):
            validate_model_artifact(artifact)


def test_model_artifact_rejects_coefficient_feature_order_length_mismatch():
    artifact = valid_model_artifact(coefficients=[0.1, 0.2])

    with pytest.raises(ValidationError):
        validate_model_artifact(artifact)


@pytest.mark.parametrize("threshold", [-0.01, 1.01])
def test_model_artifact_rejects_threshold_outside_unit_interval(threshold):
    artifact = valid_model_artifact(threshold=threshold)

    with pytest.raises(ValidationError):
        validate_model_artifact(artifact)


def test_holdout_fixture_requires_window_id_and_all_model_features():
    artifact = valid_model_artifact()
    row = valid_behavior_window()
    del row["window_id"]

    with pytest.raises(ValidationError):
        validate_holdout_fixture([row], artifact, public=True)

    row = valid_behavior_window()
    del row["feature_login_failures"]

    with pytest.raises(ValidationError):
        validate_holdout_fixture([row], artifact, public=True)


def test_holdout_fixture_allows_private_expected_columns_only_in_private_mode():
    artifact = valid_model_artifact()
    row = valid_behavior_window(
        score_local=0.1,
        probability_local=0.525,
        prediction_local=1,
    )

    validate_holdout_fixture([row], artifact, public=False)

    with pytest.raises(ValidationError):
        validate_holdout_fixture([row], artifact, public=True)
