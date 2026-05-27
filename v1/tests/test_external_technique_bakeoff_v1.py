from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ai_tamperguard_v1.research.artifacts import export_linear_artifact, score_linear_artifact
from ai_tamperguard_v1.research.bakeoff import BakeoffError, run_external_bakeoff
from ai_tamperguard_v1.research.report import render_markdown_report


def _write_fixture_csv(path):
    rows = []
    for i in range(18):
        label = 1 if i % 3 == 0 else 0
        rows.append(
            {
                "window_id": f"w{i:03d}",
                "scenario_run_id": f"run_{i:03d}",
                "actor_id": f"actor_{i % 3}",
                "window_start_relative_sec": 0,
                "window_end_relative_sec": 900,
                "feature_event_count": 3 + (2 * label) + (i % 2),
                "feature_search_count": 1 + (i % 4),
                "feature_permission_denied_count": label,
                "label_binary": label,
                "label_family": "fixture_positive" if label else "benign_investigation",
                "label_source": "unit_fixture",
                "split_id": "unassigned",
                "reset_id": "reset_000",
                "window_type": "actor_15m",
                "label_confidence": 1.0,
                "outcome": "unit_fixture",
                "source_batch_id": "unit_fixture_batch",
                "source_input_path_count": 1,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_policy(path):
    path.write_text(
        "schema_version: feature_policy_v1\n"
        "allowlist:\n"
        "  - feature_event_count\n"
        "  - feature_search_count\n"
        "  - feature_permission_denied_count\n"
        "denylist_generator_signature: []\n"
        "denylist_cross_split_population: []\n",
        encoding="utf-8",
    )


def test_logistic_artifact_scores_match_linear_formula():
    feature_order = ["feature_event_count", "feature_search_count"]
    artifact = export_linear_artifact(
        technique="logistic_regression",
        profile="default_balanced",
        feature_order=feature_order,
        intercept=-1.25,
        coefficients=[0.5, -0.125],
        threshold=0.5,
        metadata={"random_seed": 260527},
        feature_policy={"selection_mode": "explicit_allowlist_only"},
        leakage_probes={"verdict": "honest"},
        metrics={},
    )
    frame = pd.DataFrame({"feature_event_count": [1, 4], "feature_search_count": [2, 3]})

    scored = score_linear_artifact(artifact, frame)

    expected_scores = np.array([-1.0, 0.375])
    np.testing.assert_allclose(scored["score"], expected_scores)
    np.testing.assert_allclose(scored["probability"], 1.0 / (1.0 + np.exp(-expected_scores)))
    assert scored["prediction"].tolist() == [0, 1]


def test_bakeoff_runs_on_small_fixture_with_allow_small_fixture(tmp_path):
    csv_path = tmp_path / "windows.csv"
    policy_path = tmp_path / "feature_policy_v1.yaml"
    output_dir = tmp_path / "out"
    _write_fixture_csv(csv_path)
    _write_policy(policy_path)

    result = run_external_bakeoff(
        features_path=csv_path,
        feature_policy_path=policy_path,
        output_dir=output_dir,
        split_strategy="deterministic_hash",
        seed=260527,
        allow_small_fixture=True,
        leakage_probe_max_auc=1.0,
        require_negative_control_drop=0.0,
    )

    assert result.selected_candidate is not None
    assert (output_dir / "bakeoff-report.md").exists()
    assert (output_dir / "bakeoff-results.json").exists()
    assert (output_dir / "candidate-summary.csv").exists()
    assert (output_dir / "selected-model-artifact.json").exists()
    payload = json.loads((output_dir / "bakeoff-results.json").read_text(encoding="utf-8"))
    assert payload["feature_policy"]["selection_mode"] == "explicit_allowlist_only"
    assert payload["dataset"]["smoke_test_sized_fixture"] is True


def test_fails_for_missing_required_columns(tmp_path):
    csv_path = tmp_path / "windows.csv"
    policy_path = tmp_path / "feature_policy_v1.yaml"
    _write_fixture_csv(csv_path)
    _write_policy(policy_path)
    frame = pd.read_csv(csv_path).drop(columns=["label_binary"])
    frame.to_csv(csv_path, index=False)

    with pytest.raises(BakeoffError, match="missing required columns"):
        run_external_bakeoff(
            features_path=csv_path,
            feature_policy_path=policy_path,
            output_dir=tmp_path / "out",
            allow_small_fixture=True,
            leakage_probe_max_auc=1.0,
            require_negative_control_drop=0.0,
        )


def test_report_contains_non_claims():
    markdown = render_markdown_report(
        {
            "dataset": {"source_csv": "windows.csv", "rows": 42, "smoke_test_sized_fixture": True},
            "feature_policy": {"selection_mode": "explicit_allowlist_only", "allowlist_resolved": ["feature_event_count"]},
            "gate_summary": [{"gate": "feature_policy", "status": "passed", "notes": "ok"}],
            "leakage_probes": {"verdict": "honest", "single_feature_auc_max": 0.5},
            "candidates": [],
            "selected_candidate": None,
            "decision": "No candidate promoted.",
        }
    )

    assert "weak proxy labels, not malicious ground truth" in markdown
    assert "not production detection quality" in markdown
    assert "local bakeoff metrics do not prove Splunk-side success" in markdown
    assert "smoke-test-sized fixture" in markdown
