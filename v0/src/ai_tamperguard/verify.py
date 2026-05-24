from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ai_tamperguard.schema import validate_model_artifact

PRIVATE_VERIFY_REPORT_DEFAULT = "reports/private/v0-smoke-test-<model_version>.md"
DEFAULT_EQUIVALENCE_TOLERANCE = 1e-6
_SAFE_MODEL_VERSION_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class VerificationError(ValueError):
    """Raised when local-vs-Splunk scoring equivalence does not pass."""


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    model_version: str
    row_count: int
    max_score_residual: float
    max_probability_residual: float
    prediction_mismatches: list[str]
    tolerance: float


def compare_local_and_splunk_scores(
    expected_rows: Iterable[Mapping[str, Any]],
    splunk_rows: Iterable[Mapping[str, Any]],
    artifact: Mapping[str, Any],
    *,
    tolerance: float = DEFAULT_EQUIVALENCE_TOLERANCE,
) -> VerificationResult:
    """Compare local expected holdout scores to Splunk-side scoring output.

    `scored_at` is intentionally ignored: local and Splunk executions happen at
    different times, so comparing timestamps would create a false failure. G6 is
    about numeric score/probability equivalence and prediction agreement.
    """
    validate_model_artifact(artifact)
    if not math.isfinite(tolerance):
        raise VerificationError("tolerance must be finite")
    if tolerance < 0:
        raise VerificationError("tolerance must be non-negative")
    model_version = _artifact_model_version(artifact)
    expected_by_window = _index_by_window_id(expected_rows, role="expected")
    splunk_by_window = _index_by_window_id(splunk_rows, role="splunk")
    if set(expected_by_window) != set(splunk_by_window):
        missing_in_splunk = sorted(set(expected_by_window) - set(splunk_by_window))
        missing_in_expected = sorted(set(splunk_by_window) - set(expected_by_window))
        raise VerificationError(
            "window_id sets differ; "
            f"missing_in_splunk={missing_in_splunk}, missing_in_expected={missing_in_expected}"
        )

    max_score_residual = 0.0
    max_probability_residual = 0.0
    prediction_mismatches: list[str] = []
    for window_id in sorted(expected_by_window):
        expected = expected_by_window[window_id]
        splunk = splunk_by_window[window_id]
        _assert_model_version(expected, model_version, role="expected", window_id=window_id, required=False)
        _assert_model_version(splunk, model_version, role="splunk", window_id=window_id, required=True)

        score_residual = abs(
            _number(expected, "score_local", window_id=window_id) - _number(splunk, "score", window_id=window_id)
        )
        probability_residual = abs(
            _number(expected, "probability_local", window_id=window_id)
            - _number(splunk, "probability", window_id=window_id)
        )
        max_score_residual = max(max_score_residual, score_residual)
        max_probability_residual = max(max_probability_residual, probability_residual)
        if score_residual > tolerance:
            raise VerificationError(
                f"score residual above tolerance for window_id={window_id}: {score_residual} > {tolerance}"
            )
        if probability_residual > tolerance:
            raise VerificationError(
                f"probability residual above tolerance for window_id={window_id}: {probability_residual} > {tolerance}"
            )
        expected_prediction = _integer(expected, "prediction_local", window_id=window_id)
        splunk_prediction = _integer(splunk, "prediction", window_id=window_id)
        if expected_prediction != splunk_prediction:
            prediction_mismatches.append(window_id)

    if prediction_mismatches:
        raise VerificationError(f"prediction mismatch for window_id(s): {prediction_mismatches}")

    return VerificationResult(
        passed=True,
        model_version=model_version,
        row_count=len(expected_by_window),
        max_score_residual=max_score_residual,
        max_probability_residual=max_probability_residual,
        prediction_mismatches=prediction_mismatches,
        tolerance=float(tolerance),
    )


def verify_csv_files(
    *,
    expected_path: Path,
    splunk_results_path: Path,
    artifact: Mapping[str, Any],
    tolerance: float = DEFAULT_EQUIVALENCE_TOLERANCE,
) -> VerificationResult:
    """Read local expected and Splunk result CSVs, then compare G6 equivalence."""
    expected_frame = pd.read_csv(expected_path, dtype={"window_id": "string", "model_version": "string"})
    splunk_frame = pd.read_csv(splunk_results_path, dtype={"window_id": "string", "model_version": "string"})
    return compare_local_and_splunk_scores(
        expected_frame.to_dict(orient="records"),
        splunk_frame.to_dict(orient="records"),
        artifact,
        tolerance=tolerance,
    )


def write_verification_report(result: VerificationResult, report_path: Path) -> str:
    """Write the private G6 verification report section."""
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    body = render_verification_report(result)
    report_path.write_text(body, encoding="utf-8")
    return body


def render_verification_report(result: VerificationResult) -> str:
    return "\n".join(
        [
            "# AI TamperGuard v0 local-vs-Splunk verification",
            "",
            "## G6 local-vs-Splunk equivalence: PASS",
            "",
            "This is not a tamper detector. v0 verifies pipeline plumbing and numerical equivalence only.",
            "",
            f"- model_version: `{result.model_version}`",
            f"- compared rows: {result.row_count}",
            f"- tolerance: {result.tolerance:.12g}",
            f"- max score residual: {result.max_score_residual:.12g}",
            f"- max probability residual: {result.max_probability_residual:.12g}",
            f"- prediction mismatches: {len(result.prediction_mismatches)}",
            "- scored_at: ignored by design; local and Splunk timestamps are not equivalence signals.",
            "",
        ]
    )


def safe_default_report_path(model_version: str) -> Path:
    """Resolve the default private report path without allowing path injection."""
    if not isinstance(model_version, str) or not _SAFE_MODEL_VERSION_RE.fullmatch(model_version):
        raise VerificationError("unsafe model_version for default report path")
    return Path(PRIVATE_VERIFY_REPORT_DEFAULT.replace("<model_version>", model_version))


def _artifact_model_version(artifact: Mapping[str, Any]) -> str:
    model_version = artifact["model_version"]
    if not isinstance(model_version, str):
        raise VerificationError("artifact model_version must be a string")
    return model_version


def _index_by_window_id(rows: Iterable[Mapping[str, Any]], *, role: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row_number, row in enumerate(rows, start=1):
        row_dict = dict(row)
        if "window_id" not in row_dict or pd.isna(row_dict["window_id"]) or str(row_dict["window_id"]) == "":
            raise VerificationError(f"{role} row {row_number} missing window_id")
        window_id = str(row_dict["window_id"])
        if window_id in indexed:
            raise VerificationError(f"{role} duplicate window_id: {window_id}")
        indexed[window_id] = row_dict
    if not indexed:
        raise VerificationError(f"{role} rows are empty")
    return indexed


def _assert_model_version(
    row: Mapping[str, Any], model_version: str, *, role: str, window_id: str, required: bool
) -> None:
    if "model_version" not in row or pd.isna(row["model_version"]):
        if required:
            raise VerificationError(f"{role} row missing model_version for window_id={window_id}")
        return
    if not isinstance(row["model_version"], str):
        raise VerificationError(f"{role} model_version must be a string for window_id={window_id}")
    if row["model_version"] != model_version:
        raise VerificationError(
            f"{role} model_version mismatch for window_id={window_id}: {row['model_version']!r} != {model_version!r}"
        )


def _number(row: Mapping[str, Any], field: str, *, window_id: str) -> float:
    if field not in row:
        raise VerificationError(f"missing {field} for window_id={window_id}")
    try:
        value = float(row[field])
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"{field} must be numeric for window_id={window_id}") from exc
    if not math.isfinite(value):
        raise VerificationError(f"{field} must be finite for window_id={window_id}")
    return value


def _integer(row: Mapping[str, Any], field: str, *, window_id: str) -> int:
    value = _number(row, field, window_id=window_id)
    if value not in (0.0, 1.0):
        raise VerificationError(f"{field} must be 0 or 1 for window_id={window_id}")
    return int(value)
