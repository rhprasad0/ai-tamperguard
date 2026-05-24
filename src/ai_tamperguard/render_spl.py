from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from ai_tamperguard.schema import validate_model_artifact

PRIVATE_SPL_DEFAULT = "splunk/private/score_tamperguard_v0_model.spl"
DEFAULT_SCORE_TOLERANCE = 1e-6
_FEATURE_NAME_RE = re.compile(r"^feature_[A-Za-z0-9_]+$")
_LOOKUP_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.csv$")


class RenderSplError(ValueError):
    """Raised when a scoring artifact cannot be safely rendered as SPL."""


def render_scoring_spl(artifact: Mapping[str, Any], *, lookup_name: str) -> str:
    """Render deterministic no-ML-app SPL scoring from a v0 model artifact.

    The generated SPL intentionally uses only documented SPL primitives needed for
    v0: inputlookup, eval, tonumber, exp, if, now, and table. The model artifact remains
    the single source of truth for feature order, coefficients, threshold, and
    model_version.
    """
    feature_order = [str(feature) for feature in cast(Sequence[Any], artifact.get("feature_order", []))]
    for feature in feature_order:
        _validate_feature_name(feature)
    validate_model_artifact(artifact)
    _validate_lookup_name(lookup_name)
    coefficients = [float(value) for value in cast(Sequence[Any], artifact["coefficients"])]

    feature_eval_parts = [f"{feature}_num = tonumber({feature})" for feature in feature_order]
    score_terms = [
        f"({_format_number(coefficient)} * {feature}_num)"
        for feature, coefficient in zip(feature_order, coefficients, strict=True)
    ]
    score_expression = f"{_format_number(float(artifact['intercept']))} + " + " + ".join(score_terms)
    model_version = _spl_string(str(artifact["model_version"]))
    threshold = _format_number(float(artifact["threshold"]))

    lines = [
        f"| inputlookup {lookup_name}",
        "| eval " + ", ".join(feature_eval_parts),
        f"| eval score = {score_expression}",
        "| eval probability = 1 / (1 + exp(-score))",
        f"| eval prediction = if(probability >= {threshold}, 1, 0)",
        f"| eval model_version = {model_version}, scored_at = now()",
        "| table window_id score probability prediction model_version scored_at",
    ]
    return "\n".join(lines) + "\n"


def local_score_rows(rows: Iterable[Mapping[str, Any]], artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Score synthetic/public fixture rows with the same logistic math rendered to SPL."""
    validate_model_artifact(artifact)
    feature_order = [str(feature) for feature in cast(Sequence[Any], artifact["feature_order"])]
    coefficients = [float(value) for value in cast(Sequence[Any], artifact["coefficients"])]
    intercept = float(artifact["intercept"])
    threshold = float(artifact["threshold"])
    scored_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        row_dict = dict(row)
        score = intercept
        for feature, coefficient in zip(feature_order, coefficients, strict=True):
            if feature not in row_dict:
                raise RenderSplError(f"row {index} missing feature: {feature}")
            score += coefficient * float(row_dict[feature])
        probability = 1 / (1 + math.exp(-score))
        row_dict["score_local"] = float(score)
        row_dict["probability_local"] = float(probability)
        row_dict["prediction_local"] = int(probability >= threshold)
        row_dict["model_version"] = str(artifact["model_version"])
        scored_rows.append(row_dict)
    return scored_rows


def write_scoring_spl(*, artifact_path: Path, lookup_name: str, output_path: Path) -> str:
    """Read a model artifact JSON file and write the rendered private SPL artifact."""
    artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    spl = render_scoring_spl(artifact, lookup_name=lookup_name)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(spl, encoding="utf-8")
    return spl


def _validate_lookup_name(lookup_name: str) -> None:
    if "/" in lookup_name or "\\" in lookup_name or not _LOOKUP_NAME_RE.fullmatch(lookup_name):
        raise RenderSplError("lookup_name must be a simple app-scoped CSV lookup filename")


def _validate_feature_name(feature: str) -> None:
    if not _FEATURE_NAME_RE.fullmatch(feature):
        raise RenderSplError(f"feature names must be safe feature_* identifiers; got {feature!r}")


def _format_number(value: float) -> str:
    return format(value, ".15g")


def _spl_string(value: str) -> str:
    return json.dumps(value)
