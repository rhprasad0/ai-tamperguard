from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence, cast

from jsonschema import Draft202012Validator, ValidationError

_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
_PRIVATE_COLUMN_SUFFIXES = ("_private",)
_PRIVATE_COLUMN_PREFIXES = ("evidence_",)
_PUBLIC_FORBIDDEN_COLUMNS = {
    "actor_surrogate_private",
    "score_local",
    "probability_local",
    "prediction_local",
}
_PRIVATE_HOLDOUT_EXPECTED_COLUMNS = {
    "score_local",
    "probability_local",
    "prediction_local",
}


def load_schema(name: str) -> dict:
    """Load a public JSON schema by filename or schema stem."""
    filename = name if name.endswith(".json") else f"{name}.schema.json"
    path = _SCHEMA_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_behavior_window(row: Mapping[str, object], *, public: bool = False) -> None:
    """Validate one v0 actor_60m behavior-window row."""
    Draft202012Validator(load_schema("behavior_window_v0")).validate(dict(row))
    _require_min_feature_count(row, minimum=8)
    if public:
        _reject_public_forbidden_columns(row)


def validate_model_artifact(artifact: Mapping[str, object]) -> None:
    """Validate the v0 single-source-of-truth model artifact."""
    Draft202012Validator(load_schema("model_artifact_v0")).validate(dict(artifact))
    feature_order = cast(Sequence[object], artifact["feature_order"])
    coefficients = cast(Sequence[object], artifact["coefficients"])
    if len(feature_order) != len(coefficients):
        raise ValidationError("coefficients length must equal feature_order length")


def validate_holdout_fixture(
    rows: Iterable[Mapping[str, object]],
    model_artifact: Mapping[str, object],
    *,
    public: bool = False,
) -> None:
    """Validate held-out fixture rows against the artifact feature order."""
    validate_model_artifact(model_artifact)
    feature_order = list(cast(Sequence[str], model_artifact["feature_order"]))
    row_schema = load_schema("holdout_fixture_v0")
    validator = Draft202012Validator(row_schema)
    for index, row in enumerate(rows):
        row_dict = dict(row)
        validator.validate(row_dict)
        _require_features(row_dict, feature_order, row_index=index)
        if public:
            _reject_public_forbidden_columns(row_dict)
        else:
            _reject_partial_private_expected_columns(row_dict)


def _feature_names(row: Mapping[str, object]) -> list[str]:
    return [key for key in row if key.startswith("feature_")]


def _require_min_feature_count(row: Mapping[str, object], *, minimum: int) -> None:
    count = len(_feature_names(row))
    if count < minimum:
        raise ValidationError(f"behavior window requires at least {minimum} feature_* fields; got {count}")


def _require_features(row: Mapping[str, object], feature_order: Sequence[str], *, row_index: int) -> None:
    missing = [feature for feature in feature_order if feature not in row]
    if missing:
        raise ValidationError(f"holdout row {row_index} missing model features: {', '.join(missing)}")


def _reject_public_forbidden_columns(row: Mapping[str, object]) -> None:
    forbidden = sorted(
        key
        for key in row
        if key in _PUBLIC_FORBIDDEN_COLUMNS
        or key.startswith(_PRIVATE_COLUMN_PREFIXES)
        or key.endswith(_PRIVATE_COLUMN_SUFFIXES)
    )
    if forbidden:
        raise ValidationError(f"public artifact contains private/export-forbidden columns: {', '.join(forbidden)}")


def _reject_partial_private_expected_columns(row: Mapping[str, object]) -> None:
    present = _PRIVATE_HOLDOUT_EXPECTED_COLUMNS.intersection(row)
    if present and present != _PRIVATE_HOLDOUT_EXPECTED_COLUMNS:
        missing = sorted(_PRIVATE_HOLDOUT_EXPECTED_COLUMNS - present)
        raise ValidationError(f"private holdout expected columns are partial; missing: {', '.join(missing)}")
