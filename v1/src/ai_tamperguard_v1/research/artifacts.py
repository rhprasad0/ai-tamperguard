from __future__ import annotations

import math
import platform
from typing import Any, Sequence

import numpy as np
import pandas as pd
import sklearn

NON_CLAIMS = [
    "weak proxy labels, not malicious ground truth",
    "offline model comparison, not production detection quality",
    "not a public benchmark result",
    "local bakeoff metrics do not prove Splunk-side success",
    "feature set restricted to explicit allowlist; prefix-based selection forbidden",
]


def export_linear_artifact(
    *,
    technique: str,
    profile: str,
    feature_order: Sequence[str],
    intercept: float,
    coefficients: Sequence[float],
    threshold: float,
    metadata: dict[str, Any],
    feature_policy: dict[str, Any],
    leakage_probes: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    if len(feature_order) != len(coefficients):
        raise ValueError("feature_order and coefficients length mismatch")
    return {
        "schema_version": "model_artifact_v1_bakeoff",
        "model_type": f"{technique}_sklearn",
        "technique": technique,
        "profile": profile,
        "feature_order": list(feature_order),
        "threshold": float(threshold),
        "deployability_class": "direct_spl" if technique == "logistic_regression" else "linear_local_only",
        "score_fields": {"score": "score_local", "probability": "probability_local", "prediction": "prediction_local"},
        "parameters": {"intercept": float(intercept), "coefficients": [float(v) for v in coefficients]},
        "training_metadata": {
            "python_version": platform.python_version(),
            "sklearn_version": sklearn.__version__,
            **metadata,
        },
        "feature_policy": feature_policy,
        "leakage_probes": leakage_probes,
        "metrics": metrics,
        "non_claims": NON_CLAIMS,
    }


def score_linear_artifact(artifact: dict[str, Any], frame: pd.DataFrame) -> pd.DataFrame:
    feature_order = artifact["feature_order"]
    params = artifact["parameters"]
    matrix = frame.loc[:, feature_order].astype(float).to_numpy()
    coefficients = np.asarray(params["coefficients"], dtype=float)
    scores = float(params["intercept"]) + matrix @ coefficients
    probabilities = 1.0 / (1.0 + np.exp(-scores))
    predictions = (probabilities >= float(artifact.get("threshold", 0.5))).astype(int)
    return pd.DataFrame({"score": scores, "probability": probabilities, "prediction": predictions})


def assert_artifact_scores_match(
    artifact: dict[str, Any],
    frame: pd.DataFrame,
    expected_probabilities: Sequence[float],
    *,
    atol: float = 1e-9,
) -> None:
    scored = score_linear_artifact(artifact, frame)
    if not np.allclose(scored["probability"].to_numpy(), np.asarray(expected_probabilities), atol=atol):
        raise ValueError("artifact local scoring does not match in-memory estimator probabilities")
