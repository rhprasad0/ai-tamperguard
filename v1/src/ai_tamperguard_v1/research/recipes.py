from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.tree import DecisionTreeClassifier


@dataclass(frozen=True)
class Recipe:
    technique: str
    profile: str
    deployability_class: str
    simplicity_score: float

    @property
    def name(self) -> str:
        return f"{self.technique}/{self.profile}"

    def make_estimator(self, seed: int):
        if self.technique == "logistic_regression":
            c_value = 0.25 if self.profile == "stronger_regularization" else 1.0
            return LogisticRegression(class_weight="balanced", C=c_value, solver="liblinear", max_iter=1000, random_state=seed)
        if self.technique == "linear_sgd" and self.profile == "log_loss_balanced":
            return SGDClassifier(loss="log_loss", class_weight="balanced", max_iter=2000, tol=1e-4, random_state=seed)
        if self.technique == "linear_sgd" and self.profile == "hinge_balanced":
            return SGDClassifier(loss="hinge", class_weight="balanced", max_iter=2000, tol=1e-4, random_state=seed)
        if self.technique == "decision_tree" and self.profile == "stump":
            return DecisionTreeClassifier(max_depth=1, min_samples_leaf=2, class_weight="balanced", random_state=seed)
        if self.technique == "decision_tree" and self.profile == "shallow":
            return DecisionTreeClassifier(max_depth=3, min_samples_leaf=2, class_weight="balanced", random_state=seed)
        raise ValueError(f"unsupported recipe: {self.name}")


def default_recipes() -> list[Recipe]:
    return [
        Recipe("logistic_regression", "default_balanced", "direct_spl", 1.0),
        Recipe("logistic_regression", "stronger_regularization", "direct_spl", 0.95),
        Recipe("linear_sgd", "log_loss_balanced", "linear_local_only", 0.85),
        Recipe("linear_sgd", "hinge_balanced", "offline_only", 0.80),
        Recipe("decision_tree", "stump", "generated_spl_planned", 0.75),
        Recipe("decision_tree", "shallow", "offline_only", 0.65),
    ]


def candidate_scores(estimator: Any, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray | None]:
    if hasattr(estimator, "predict_proba"):
        probs = estimator.predict_proba(x)[:, 1]
        return probs, probs
    if hasattr(estimator, "decision_function"):
        raw = estimator.decision_function(x)
        return np.asarray(raw, dtype=float), None
    pred = estimator.predict(x)
    return np.asarray(pred, dtype=float), None
