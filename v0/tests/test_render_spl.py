import json
import math
import subprocess
import sys

import pytest

from ai_tamperguard.render_spl import DEFAULT_SCORE_TOLERANCE, local_score_rows, render_scoring_spl


def tiny_artifact() -> dict[str, object]:
    return {
        "schema_version": "model_artifact_v0",
        "model_type": "logistic_regression_sklearn",
        "model_version": "tamperguard-v0-synthetic",
        "feature_order": ["feature_alpha", "feature_beta", "feature_gamma"],
        "intercept": -0.25,
        "coefficients": [0.5, -1.25, 2.0],
        "threshold": 0.6,
        "label_rule_id": "weak_proxy_v0_admin_control_plane_activity",
        "label_rule_description": "synthetic weak proxy label",
        "training_metadata": {
            "python_version": "3.14.0",
            "sklearn_version": "1.8.0",
            "random_seed": 20260524,
            "training_git_sha": "unit-test-sha",
            "data_fingerprint_sha256": "a" * 64,
            "label_rule_fingerprint_sha256": "b" * 64,
            "train_row_count": 30,
            "holdout_row_count": 2,
        },
        "score_envelope": {
            "score_field": "score_local",
            "probability_field": "probability_local",
            "prediction_field": "prediction_local",
        },
        "diagnostics": {},
    }


def test_rendered_spl_uses_explicit_feature_order_tonumber_and_documented_eval_shape():
    artifact = tiny_artifact()

    spl = render_scoring_spl(artifact, lookup_name="tamperguard_windows_holdout_proxy.csv")

    assert spl.startswith("| inputlookup tamperguard_windows_holdout_proxy.csv")
    assert "1 / (1 + exp(-score))" in spl
    assert 'model_version = "tamperguard-v0-synthetic", scored_at = now()' in spl
    assert "score = -0.25 + (0.5 * feature_alpha_num) + (-1.25 * feature_beta_num) + (2 * feature_gamma_num)" in spl
    assert spl.index("tonumber(feature_alpha)") < spl.index("tonumber(feature_beta)") < spl.index("tonumber(feature_gamma)")
    for feature in artifact["feature_order"]:
        assert spl.count(f"tonumber({feature})") == 1


@pytest.mark.parametrize("forbidden", [" fit ", " apply ", " onnx", ".mlmodel", "python"])
def test_rendered_spl_does_not_use_ml_toolkit_or_custom_commands(forbidden):
    spl = render_scoring_spl(tiny_artifact(), lookup_name="tamperguard_windows_holdout_proxy.csv")

    assert forbidden not in spl.lower()


def test_rendered_spl_rejects_private_lookup_names_and_feature_injection():
    artifact = tiny_artifact()
    with pytest.raises(ValueError, match="lookup_name"):
        render_scoring_spl(artifact, lookup_name="splunk/private/holdout.csv")

    bad_artifact = dict(artifact)
    bad_artifact["feature_order"] = ["feature_alpha", "feature_beta | delete"]
    bad_artifact["coefficients"] = [0.5, 1.0]
    with pytest.raises(ValueError, match="feature"):
        render_scoring_spl(bad_artifact, lookup_name="tamperguard_windows_holdout_proxy.csv")


def test_synthetic_local_scoring_matches_expected_logistic_math():
    rows = [
        {"window_id": "w1", "feature_alpha": "2", "feature_beta": 1, "feature_gamma": 0},
        {"window_id": "w2", "feature_alpha": 0, "feature_beta": 0, "feature_gamma": 1.5},
    ]

    scored = local_score_rows(rows, tiny_artifact())

    expected_score_1 = -0.25 + (0.5 * 2) + (-1.25 * 1) + (2.0 * 0)
    expected_probability_1 = 1 / (1 + math.exp(-expected_score_1))
    expected_score_2 = -0.25 + (0.5 * 0) + (-1.25 * 0) + (2.0 * 1.5)
    expected_probability_2 = 1 / (1 + math.exp(-expected_score_2))
    assert DEFAULT_SCORE_TOLERANCE == 1e-6
    assert scored[0]["score_local"] == expected_score_1
    assert abs(scored[0]["probability_local"] - expected_probability_1) <= DEFAULT_SCORE_TOLERANCE
    assert scored[0]["prediction_local"] == int(expected_probability_1 >= 0.6)
    assert scored[1]["score_local"] == expected_score_2
    assert abs(scored[1]["probability_local"] - expected_probability_2) <= DEFAULT_SCORE_TOLERANCE
    assert scored[1]["prediction_local"] == int(expected_probability_2 >= 0.6)


def test_render_cli_writes_private_spl_from_artifact(tmp_path):
    artifact_path = tmp_path / "model.json"
    output_path = tmp_path / "splunk/private/score_tamperguard_v0_model.spl"
    artifact_path.write_text(json.dumps(tiny_artifact()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_splunk_scoring_artifact_v0.py",
            "--artifact",
            str(artifact_path),
            "--lookup",
            "tamperguard_windows_holdout_proxy.csv",
            "--output",
            str(output_path),
        ],
        check=True,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert output_path.exists()
    assert "wrote SPL scoring artifact" in result.stdout
    assert "| inputlookup tamperguard_windows_holdout_proxy.csv" in output_path.read_text(encoding="utf-8")


def test_render_cli_help_shows_private_output_default():
    result = subprocess.run(
        [sys.executable, "scripts/render_splunk_scoring_artifact_v0.py", "--help"],
        check=True,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert "splunk/private/score_tamperguard_v0_model.spl" in result.stdout
