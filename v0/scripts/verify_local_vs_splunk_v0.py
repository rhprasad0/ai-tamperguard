#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_tamperguard.verify import (  # noqa: E402
    DEFAULT_EQUIVALENCE_TOLERANCE,
    PRIVATE_VERIFY_REPORT_DEFAULT,
    VerificationError,
    safe_default_report_path,
    verify_csv_files,
    write_verification_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify AI TamperGuard v0 local expected holdout scores against Splunk scoring results."
    )
    parser.add_argument(
        "--expected",
        required=True,
        type=Path,
        help="Local expected holdout CSV, e.g. data/private/holdout/tamperguard_windows_holdout_proxy_expected.csv.",
    )
    parser.add_argument(
        "--splunk-results",
        required=True,
        type=Path,
        help="Splunk-scored holdout CSV, e.g. data/private/holdout/tamperguard_windows_holdout_proxy_splunk_scored.csv.",
    )
    parser.add_argument(
        "--artifact",
        required=True,
        type=Path,
        help="Model artifact JSON, e.g. models/private/tamperguard_v0_model.json.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(PRIVATE_VERIFY_REPORT_DEFAULT),
        help=f"Private verification report path. Default: {PRIVATE_VERIFY_REPORT_DEFAULT}",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_EQUIVALENCE_TOLERANCE,
        help="Absolute tolerance for score and probability residuals. Default: 1e-6.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    report_path = args.report
    if str(report_path) == PRIVATE_VERIFY_REPORT_DEFAULT:
        try:
            report_path = safe_default_report_path(artifact["model_version"])
        except VerificationError as exc:
            raise SystemExit(str(exc)) from exc
    try:
        result = verify_csv_files(
            expected_path=args.expected,
            splunk_results_path=args.splunk_results,
            artifact=artifact,
            tolerance=args.tolerance,
        )
    except VerificationError as exc:
        raise SystemExit(f"local-vs-Splunk equivalence failed: {exc}") from exc
    write_verification_report(result, report_path)
    print(
        "verified local-vs-Splunk equivalence "
        f"for {result.row_count} rows; max_score_residual={result.max_score_residual:.12g}; "
        f"max_probability_residual={result.max_probability_residual:.12g}; report={report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
