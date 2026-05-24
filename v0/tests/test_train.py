import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from ai_tamperguard.features import FEATURE_COLUMNS
from ai_tamperguard.schema import validate_holdout_fixture, validate_model_artifact
from ai_tamperguard.train import (
    PRIVATE_ARTIFACT_DEFAULT,
    PRIVATE_EXPECTED_HOLDOUT_DEFAULT,
    PRIVATE_REPORT_DEFAULT,
    generate_diagnostics_report,
    train_logistic_regression,
    write_training_outputs,
)


def synthetic_training_rows(*, perturb: bool = False) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    for index in range(40):
        label = index % 2
        row: dict[str, object] = {
            "window_id": f"actor_60m:2026-05-24T{index:02d}:00:00Z:actor_{index:02d}",
            "window_type": "actor_60m",
            "window_start": f"2026-05-24T{index:02d}:00:00Z",
            "window_end": f"2026-05-24T{index + 1:02d}:00:00Z",
            "source_dataset": "synthetic-unit",
            "actor_surrogate_private": f"actor_private_{index:02d}",
            "label": label,
            "label_binary": label,
            "label_value_description": "working_model_positive_proxy" if label else "needs_review",
            "label_source": "weak_proxy_v0",
            "label_rule_id": "weak_proxy_v0_admin_control_plane_activity",
            "label_rule_description": "synthetic weak proxy label",
        }
        for feature_index, feature_name in enumerate(FEATURE_COLUMNS):
            base = 3 + feature_index if label else feature_index % 3
            row[feature_name] = base + (1 if perturb and index == 3 and feature_index == 0 else 0)
        rows.append(row)
    return rows[:30], rows[30:]


def test_training_on_synthetic_rows_emits_valid_artifact_and_expected_holdout():
    train_rows, holdout_rows = synthetic_training_rows()

    result = train_logistic_regression(
        train_rows,
        holdout_rows,
        feature_order=list(FEATURE_COLUMNS),
        seed=20260524,
        training_git_sha="unit-test-sha",
    )

    validate_model_artifact(result.artifact)
    validate_holdout_fixture(result.expected_holdout_rows, result.artifact, public=False)
    assert result.artifact["feature_order"] == list(FEATURE_COLUMNS)
    assert len(result.artifact["coefficients"]) == len(FEATURE_COLUMNS)
    assert result.artifact["label_rule_id"] == "weak_proxy_v0_admin_control_plane_activity"
    assert result.artifact["label_rule_description"]
    assert result.artifact["training_metadata"]["random_seed"] == 20260524
    assert result.artifact["score_envelope"] == {
        "score_field": "score_local",
        "probability_field": "probability_local",
        "prediction_field": "prediction_local",
    }
    assert all("score_local" in row for row in result.expected_holdout_rows)


def test_model_version_changes_when_feature_data_fingerprint_changes():
    train_rows, holdout_rows = synthetic_training_rows()
    perturbed_train_rows, perturbed_holdout_rows = synthetic_training_rows(perturb=True)

    original = train_logistic_regression(
        train_rows,
        holdout_rows,
        feature_order=list(FEATURE_COLUMNS),
        seed=20260524,
        training_git_sha="unit-test-sha",
    )
    changed = train_logistic_regression(
        perturbed_train_rows,
        perturbed_holdout_rows,
        feature_order=list(FEATURE_COLUMNS),
        seed=20260524,
        training_git_sha="unit-test-sha",
    )

    assert original.artifact["training_metadata"]["data_fingerprint_sha256"] != changed.artifact["training_metadata"]["data_fingerprint_sha256"]
    assert original.artifact["model_version"] != changed.artifact["model_version"]


def test_g2_anti_degeneracy_metrics_are_computed():
    train_rows, holdout_rows = synthetic_training_rows()

    result = train_logistic_regression(
        train_rows,
        holdout_rows,
        feature_order=list(FEATURE_COLUMNS),
        seed=20260524,
        training_git_sha="unit-test-sha",
    )

    diagnostics = result.diagnostics
    assert diagnostics["nonzero_coefficient_count"] >= 3
    assert diagnostics["holdout_probability_std"] > 0.05
    assert set(diagnostics["predicted_class_distribution"]) == {"0", "1"}
    assert set(diagnostics["true_class_distribution"]) == {"0", "1"}


def test_training_rejects_fractional_labels_without_truncating():
    train_rows, holdout_rows = synthetic_training_rows()
    train_rows[0]["label_binary"] = 0.5

    with pytest.raises(ValueError, match="label_binary"):
        train_logistic_regression(
            train_rows,
            holdout_rows,
            feature_order=list(FEATURE_COLUMNS),
            seed=20260524,
            training_git_sha="unit-test-sha",
        )


def test_training_outputs_require_canonical_feature_manifest(tmp_path):
    train_rows, holdout_rows = synthetic_training_rows()
    train_path = tmp_path / "train.csv"
    holdout_path = tmp_path / "holdout.csv"
    train_frame = pd.DataFrame(train_rows).drop(columns=[FEATURE_COLUMNS[-1]])
    holdout_frame = pd.DataFrame(holdout_rows)
    train_frame.to_csv(train_path, index=False)
    holdout_frame.to_csv(holdout_path, index=False)

    with pytest.raises(ValueError, match="missing canonical feature"):
        write_training_outputs(
            train_path=train_path,
            holdout_path=holdout_path,
            artifact_path=tmp_path / "models/private/model.json",
            expected_holdout_path=tmp_path / "data/private/expected.csv",
            report_path=tmp_path / "reports/private/report.md",
            seed=20260524,
            training_git_sha="unit-test-sha",
        )


def test_training_outputs_reject_extra_feature_columns(tmp_path):
    train_rows, holdout_rows = synthetic_training_rows()
    train_path = tmp_path / "train.csv"
    holdout_path = tmp_path / "holdout.csv"
    train_frame = pd.DataFrame(train_rows)
    holdout_frame = pd.DataFrame(holdout_rows)
    train_frame["feature_surprise_private_signal"] = 1
    holdout_frame["feature_surprise_private_signal"] = 1
    train_frame.to_csv(train_path, index=False)
    holdout_frame.to_csv(holdout_path, index=False)

    with pytest.raises(ValueError, match="extra feature"):
        write_training_outputs(
            train_path=train_path,
            holdout_path=holdout_path,
            artifact_path=tmp_path / "models/private/model.json",
            expected_holdout_path=tmp_path / "data/private/expected.csv",
            report_path=tmp_path / "reports/private/report.md",
            seed=20260524,
            training_git_sha="unit-test-sha",
        )


def test_training_outputs_reject_reordered_feature_columns(tmp_path):
    train_rows, holdout_rows = synthetic_training_rows()
    train_path = tmp_path / "train.csv"
    holdout_path = tmp_path / "holdout.csv"
    train_frame = pd.DataFrame(train_rows)
    holdout_frame = pd.DataFrame(holdout_rows)
    metadata_columns = [column for column in train_frame.columns if not column.startswith("feature_")]
    reversed_features = list(reversed(FEATURE_COLUMNS))
    train_frame = train_frame[metadata_columns + reversed_features]
    train_frame.to_csv(train_path, index=False)
    holdout_frame.to_csv(holdout_path, index=False)

    with pytest.raises(ValueError, match="feature_order"):
        write_training_outputs(
            train_path=train_path,
            holdout_path=holdout_path,
            artifact_path=tmp_path / "models/private/model.json",
            expected_holdout_path=tmp_path / "data/private/expected.csv",
            report_path=tmp_path / "reports/private/report.md",
            seed=20260524,
            training_git_sha="unit-test-sha",
        )


def test_report_contains_plumbing_diagnostics_without_overclaiming_or_private_strings():
    train_rows, holdout_rows = synthetic_training_rows()
    result = train_logistic_regression(
        train_rows,
        holdout_rows,
        feature_order=list(FEATURE_COLUMNS),
        seed=20260524,
        training_git_sha="unit-test-sha",
    )

    report = generate_diagnostics_report(result)

    assert "# AI TamperGuard v0 smoke-test report" in report
    assert "## Plumbing diagnostics (not detection quality)" in report
    assert "this is not a tamper detector" in report.lower()
    assert "G1" in report and "G2" in report
    assert "actor_private_" not in report
    assert "hostname" not in report.lower()
    assert "index=_" not in report


def test_write_training_outputs_writes_private_paths(tmp_path):
    train_rows, holdout_rows = synthetic_training_rows()
    train_path = tmp_path / "data/private/windows/tamperguard_windows_v0_train.csv"
    holdout_path = tmp_path / "data/private/holdout/tamperguard_windows_holdout_proxy.csv"
    artifact_path = tmp_path / PRIVATE_ARTIFACT_DEFAULT
    expected_path = tmp_path / PRIVATE_EXPECTED_HOLDOUT_DEFAULT
    report_path = tmp_path / PRIVATE_REPORT_DEFAULT
    train_path.parent.mkdir(parents=True)
    holdout_path.parent.mkdir(parents=True)
    pd.DataFrame(train_rows).to_csv(train_path, index=False)
    pd.DataFrame(holdout_rows).to_csv(holdout_path, index=False)

    result = write_training_outputs(
        train_path=train_path,
        holdout_path=holdout_path,
        artifact_path=artifact_path,
        expected_holdout_path=expected_path,
        report_path=report_path,
        seed=20260524,
        training_git_sha="unit-test-sha",
    )

    assert artifact_path.exists()
    assert expected_path.exists()
    assert report_path.exists()
    assert "models/private/" in str(artifact_path)
    assert "data/private/" in str(expected_path)
    assert "reports/private/" in str(report_path)
    assert json.loads(artifact_path.read_text())["model_version"] == result.artifact["model_version"]
    assert pd.read_csv(expected_path).shape[0] == len(holdout_rows)


def test_train_cli_defaults_write_private_paths_from_repo_root_when_called_from_subdir(tmp_path):
    train_rows, holdout_rows = synthetic_training_rows()
    train_path = tmp_path / "train.csv"
    holdout_path = tmp_path / "holdout.csv"
    pd.DataFrame(train_rows).to_csv(train_path, index=False)
    pd.DataFrame(holdout_rows).to_csv(holdout_path, index=False)
    root = Path.cwd()
    default_outputs = [
        root / PRIVATE_ARTIFACT_DEFAULT,
        root / PRIVATE_EXPECTED_HOLDOUT_DEFAULT,
        root / PRIVATE_REPORT_DEFAULT,
    ]
    wrong_subdir_output = root / "scripts" / PRIVATE_ARTIFACT_DEFAULT
    for path in default_outputs:
        path.unlink(missing_ok=True)
    wrong_subdir_output.unlink(missing_ok=True)

    try:
        subprocess.run(
            [
                sys.executable,
                "train_v0_logistic_regression.py",
                "--train",
                str(train_path),
                "--holdout",
                str(holdout_path),
                "--seed",
                "20260524",
                "--training-git-sha",
                "unit-test-sha",
            ],
            check=True,
            cwd="scripts",
            text=True,
            capture_output=True,
        )

        assert all(path.exists() for path in default_outputs)
        assert not wrong_subdir_output.exists()
    finally:
        for path in default_outputs:
            path.unlink(missing_ok=True)


def test_train_cli_help_shows_private_output_defaults():
    result = subprocess.run(
        [sys.executable, "scripts/train_v0_logistic_regression.py", "--help"],
        check=True,
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert "models/private/tamperguard_v0_model.json" in result.stdout
    assert "data/private/holdout/tamperguard_windows_holdout_proxy_expected.csv" in result.stdout
    assert "reports/private/v0-smoke-test-report.md" in result.stdout
