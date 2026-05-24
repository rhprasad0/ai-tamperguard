import json
import subprocess
import sys

import pytest

from ai_tamperguard.verify import VerificationError, compare_local_and_splunk_scores


def tiny_artifact() -> dict[str, object]:
    return {
        "schema_version": "model_artifact_v0",
        "model_type": "logistic_regression_sklearn",
        "model_version": "tamperguard-v0-synthetic",
        "feature_order": ["feature_alpha", "feature_beta"],
        "intercept": -0.25,
        "coefficients": [0.5, -1.25],
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


def expected_rows() -> list[dict[str, object]]:
    return [
        {
            "window_id": "w1",
            "score_local": 0.125,
            "probability_local": 0.5312093733737563,
            "prediction_local": 0,
            "model_version": "tamperguard-v0-synthetic",
            "scored_at": "local timestamp must be ignored",
        },
        {
            "window_id": "w2",
            "score_local": 2.5,
            "probability_local": 0.9241418199787566,
            "prediction_local": 1,
            "model_version": "tamperguard-v0-synthetic",
        },
    ]


def splunk_rows() -> list[dict[str, object]]:
    return [
        {
            "window_id": "w1",
            "score": 0.1250000004,
            "probability": 0.5312093733737563,
            "prediction": 0,
            "model_version": "tamperguard-v0-synthetic",
            "scored_at": "fresh Splunk timestamp must be ignored",
        },
        {
            "window_id": "w2",
            "score": 2.5,
            "probability": 0.9241418199787566,
            "prediction": 1,
            "model_version": "tamperguard-v0-synthetic",
            "scored_at": "another Splunk timestamp",
        },
    ]


def test_exact_matching_predictions_and_tolerated_residuals_pass():
    result = compare_local_and_splunk_scores(expected_rows(), splunk_rows(), tiny_artifact(), tolerance=1e-6)

    assert result.passed is True
    assert result.row_count == 2
    assert result.max_score_residual <= 1e-6
    assert result.max_probability_residual == 0
    assert result.prediction_mismatches == []
    assert result.model_version == "tamperguard-v0-synthetic"


def test_probability_residual_above_tolerance_fails():
    splunk = splunk_rows()
    splunk[0]["probability"] = 0.6

    with pytest.raises(VerificationError, match="probability residual"):
        compare_local_and_splunk_scores(expected_rows(), splunk, tiny_artifact(), tolerance=1e-6)


def test_score_residual_above_tolerance_fails():
    splunk = splunk_rows()
    splunk[1]["score"] = 2.50001

    with pytest.raises(VerificationError, match="score residual"):
        compare_local_and_splunk_scores(expected_rows(), splunk, tiny_artifact(), tolerance=1e-6)


def test_scored_at_is_ignored_when_comparing_rows():
    splunk = splunk_rows()
    splunk[0]["scored_at"] = "9999-01-01T00:00:00Z"

    result = compare_local_and_splunk_scores(expected_rows(), splunk, tiny_artifact(), tolerance=1e-6)

    assert result.passed is True


def test_model_version_must_match_as_string_not_number():
    expected = expected_rows()
    splunk = splunk_rows()
    expected[0]["model_version"] = "001"
    expected[1]["model_version"] = "001"
    splunk[0]["model_version"] = "1"
    splunk[1]["model_version"] = "1"
    artifact = tiny_artifact()
    artifact["model_version"] = "001"

    with pytest.raises(VerificationError, match="model_version"):
        compare_local_and_splunk_scores(expected, splunk, artifact, tolerance=1e-6)


def test_missing_window_id_on_either_side_fails():
    expected = expected_rows()
    expected[0].pop("window_id")
    with pytest.raises(VerificationError, match="window_id"):
        compare_local_and_splunk_scores(expected, splunk_rows(), tiny_artifact(), tolerance=1e-6)

    splunk = splunk_rows()
    splunk[0].pop("window_id")
    with pytest.raises(VerificationError, match="window_id"):
        compare_local_and_splunk_scores(expected_rows(), splunk, tiny_artifact(), tolerance=1e-6)


def test_verify_cli_writes_private_report_for_matching_csvs(tmp_path):
    expected_path = tmp_path / "expected.csv"
    splunk_path = tmp_path / "splunk.csv"
    artifact_path = tmp_path / "model.json"
    report_path = tmp_path / "reports/private/v0-smoke-test-tamperguard-v0-synthetic.md"

    import pandas as pd

    pd.DataFrame(expected_rows()).to_csv(expected_path, index=False)
    pd.DataFrame(splunk_rows()).to_csv(splunk_path, index=False)
    artifact_path.write_text(json.dumps(tiny_artifact()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_local_vs_splunk_v0.py",
            "--expected",
            str(expected_path),
            "--splunk-results",
            str(splunk_path),
            "--artifact",
            str(artifact_path),
            "--report",
            str(report_path),
            "--tolerance",
            "1e-6",
        ],
        check=True,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "G6 local-vs-Splunk equivalence: PASS" in report
    assert "scored_at" in report
    assert "ignored" in report
    assert "verified local-vs-Splunk equivalence" in result.stdout


def test_csv_model_version_comparison_preserves_identifier_strings(tmp_path):
    expected = expected_rows()
    splunk = splunk_rows()
    for row in expected:
        row["model_version"] = "001"
    for row in splunk:
        row["model_version"] = "1"
    artifact = tiny_artifact()
    artifact["model_version"] = "001"
    expected_path = tmp_path / "expected.csv"
    splunk_path = tmp_path / "splunk.csv"
    artifact_path = tmp_path / "model.json"

    import pandas as pd

    pd.DataFrame(expected).to_csv(expected_path, index=False)
    pd.DataFrame(splunk).to_csv(splunk_path, index=False)
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_local_vs_splunk_v0.py",
            "--expected",
            str(expected_path),
            "--splunk-results",
            str(splunk_path),
            "--artifact",
            str(artifact_path),
            "--report",
            str(tmp_path / "reports/private/v0-smoke-test-001.md"),
        ],
        check=False,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "model_version" in result.stderr


def test_non_finite_numeric_values_fail():
    expected = expected_rows()
    expected[0]["score_local"] = float("nan")

    with pytest.raises(VerificationError, match="finite"):
        compare_local_and_splunk_scores(expected, splunk_rows(), tiny_artifact(), tolerance=1e-6)


@pytest.mark.parametrize("bad_tolerance", [float("nan"), float("inf")])
def test_non_finite_tolerance_fails_closed(bad_tolerance):
    splunk = splunk_rows()
    splunk[0]["score"] = 999

    with pytest.raises(VerificationError, match="tolerance must be finite"):
        compare_local_and_splunk_scores(expected_rows(), splunk, tiny_artifact(), tolerance=bad_tolerance)


def test_default_report_path_rejects_unsafe_model_version(tmp_path):
    expected_path = tmp_path / "expected.csv"
    splunk_path = tmp_path / "splunk.csv"
    artifact_path = tmp_path / "model.json"
    artifact = tiny_artifact()
    artifact["model_version"] = "../escape"

    import pandas as pd

    pd.DataFrame(expected_rows()).to_csv(expected_path, index=False)
    pd.DataFrame(splunk_rows()).to_csv(splunk_path, index=False)
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_local_vs_splunk_v0.py",
            "--expected",
            str(expected_path),
            "--splunk-results",
            str(splunk_path),
            "--artifact",
            str(artifact_path),
        ],
        check=False,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "unsafe model_version" in result.stderr


def test_verify_cli_help_shows_private_report_default():
    result = subprocess.run(
        [sys.executable, "scripts/verify_local_vs_splunk_v0.py", "--help"],
        check=True,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert "reports/private/v0-smoke-test-<model_version>.md" in result.stdout
