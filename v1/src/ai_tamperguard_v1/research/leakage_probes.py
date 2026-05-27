from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score


def single_feature_auc_probe(
    frame: pd.DataFrame,
    *,
    feature_order: list[str],
    train_mask: pd.Series,
    max_auc: float,
    overrides: dict[str, str],
) -> dict[str, Any]:
    y = frame.loc[train_mask, "label_binary"].astype(int)
    per: dict[str, float | None] = {}
    failures: list[str] = []
    for feature in feature_order:
        x = frame.loc[train_mask, [feature]].astype(float)
        if x[feature].nunique() <= 1 or y.nunique() <= 1:
            auc = None
        else:
            model = LogisticRegression(solver="liblinear", class_weight="balanced", max_iter=1000)
            model.fit(x, y)
            probs = model.predict_proba(x)[:, 1]
            auc = float(roc_auc_score(y, probs))
        per[feature] = auc
        if auc is not None and auc > max_auc and feature not in overrides:
            failures.append(feature)
    max_seen = max((value for value in per.values() if value is not None), default=0.0)
    return {
        "single_feature_auc_max": float(max_seen),
        "single_feature_auc_per_feature": per,
        "top_single_feature_auc": sorted(
            [(feature, value) for feature, value in per.items() if value is not None], key=lambda item: item[1], reverse=True
        )[:5],
        "single_feature_auc_failures": failures,
    }


def negative_control_ap_drop(
    estimator_factory,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_validation: pd.DataFrame,
    y_validation: pd.Series,
    *,
    real_validation_ap: float | None,
    seed: int,
) -> dict[str, Any]:
    if real_validation_ap is None:
        return {"negative_control_validation_ap": None, "negative_control_validation_ap_drop": None}
    rng = np.random.default_rng(seed)
    shuffled = np.asarray(y_train.astype(int).to_numpy()).copy()
    rng.shuffle(shuffled)
    if len(set(shuffled.tolist())) < 2:
        return {"negative_control_validation_ap": None, "negative_control_validation_ap_drop": None}
    estimator = estimator_factory()
    estimator.fit(x_train, shuffled)
    if hasattr(estimator, "predict_proba"):
        scores = estimator.predict_proba(x_validation)[:, 1]
    elif hasattr(estimator, "decision_function"):
        scores = estimator.decision_function(x_validation)
    else:
        scores = estimator.predict(x_validation)
    control_ap = float(average_precision_score(y_validation.astype(int), scores))
    return {
        "negative_control_validation_ap": control_ap,
        "negative_control_validation_ap_drop": float(real_validation_ap - control_ap),
    }
