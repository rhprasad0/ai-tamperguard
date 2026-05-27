from __future__ import annotations

import argparse
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from ai_tamperguard_v1.research.bakeoff import BakeoffError, run_external_bakeoff  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an offline AI TamperGuard v1 external technique bakeoff.")
    parser.add_argument("--features", required=True, help="Behavior-window CSV to evaluate.")
    parser.add_argument("--feature-policy", required=True, help="Explicit feature allowlist/denylist YAML policy.")
    parser.add_argument("--output-dir", required=True, help="Directory for report, JSON results, and artifacts.")
    parser.add_argument("--split-strategy", default="deterministic_hash", choices=["deterministic_hash"])
    parser.add_argument("--seed", type=int, default=260527)
    parser.add_argument("--min-delta-average-precision", type=float, default=0.02)
    parser.add_argument("--max-direct-spl-features", type=int, default=80)
    parser.add_argument("--leakage-probe-max-auc", type=float, default=0.85)
    parser.add_argument("--require-negative-control-drop", type=float, default=0.15)
    parser.add_argument("--allow-small-fixture", action="store_true")
    args = parser.parse_args()

    try:
        result = run_external_bakeoff(
            features_path=args.features,
            feature_policy_path=args.feature_policy,
            output_dir=args.output_dir,
            split_strategy=args.split_strategy,
            seed=args.seed,
            allow_small_fixture=args.allow_small_fixture,
            leakage_probe_max_auc=args.leakage_probe_max_auc,
            require_negative_control_drop=args.require_negative_control_drop,
            min_delta_average_precision=args.min_delta_average_precision,
            max_direct_spl_features=args.max_direct_spl_features,
        )
    except BakeoffError as exc:
        print(f"bakeoff failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote bakeoff report: {result.output_dir / 'bakeoff-report.md'}")
    print(f"selected candidate: {result.selected_candidate or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
