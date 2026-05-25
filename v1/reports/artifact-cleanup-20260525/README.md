# AI TamperGuard V1 artifact cleanup — 2026-05-25

## Summary

This cleanup removes legacy V1 run artifacts that were committed under private-shaped paths and updates the V1 pipeline to write public-safe generated artifacts under tracked `data/` and `reports/` locations.

## Decisions applied

- Keep a concise JSON cleanup manifest and this README; do not keep a bulky archive of old smoke/probe outputs.
- Remove the old fixed-k3 bundle (`v1/data/tracked/full_live_k3_fixed_20260525/`) and related fixed-k3 reports because it is an obsolete run.
- Preserve accepted goal-run evidence and migrate its public-safe raw/run artifacts out of `v1/data/private/**`.
- Track generated prompt metadata/configs. Full generated actor prompt bodies are not promoted into `data/public_sample/` unless a future public-safety review explicitly approves them.
- Keep true secrets, credentials, tokens, PII, and local lab config out of git; `v1/splunk/private/**` remains the protected location for local Splunk config.

## Preserved evidence roots

- `v1/reports/goal_runs/live_goal_nondet50_20260525T214956Z/`
- `v1/reports/goal_runs/live_goal_other_ready_20260525T221248Z/`
- `v1/data/raw_exports/live_goal_nondet50_20260525T214956Z/`
- `v1/data/raw_exports/live_goal_other_ready_20260525T221248Z/`
- `v1/data/run_manifests/live_goal_nondet50_20260525T214956Z/`
- `v1/data/run_manifests/live_goal_other_ready_20260525T221248Z/`

## Removed artifact classes

The cleanup deletes stale tracked artifacts under:

- `v1/data/private/**`
- `v1/reports/private/**`
- `v1/data/tracked/full_live_k3_fixed_20260525/**`
- `v1/reports/full_live_k3_fixed_20260525/**`
- obsolete fixed-k3/baseline goal-run report roots

See `cleanup-manifest.json` for class-level counts and migration examples.

## Validation expectations

Before publishing this cleanup, run:

```bash
uv run --directory v1 pytest
uv run --directory v1 python scripts/public_safety_scan_v1.py data/raw_exports data/run_manifests data/public_sample docs schemas scenarios reports/goal_runs reports/artifact-cleanup-20260525
```

The scan intentionally does not include `v1/splunk/private/**`.
