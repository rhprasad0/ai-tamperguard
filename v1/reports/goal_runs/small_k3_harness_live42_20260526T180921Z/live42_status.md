# Live 42-row collection status — small k=3 harness smoke

- Live batch: `small_k3_harness_live42_20260526T180921Z`
- Source dry-run manifest: `v1/data/run_manifests/small_k3_harness_smoke_20260526T174111Z/scenario_runs.jsonl`
- Result: **PASS for 42-row HEC write, Splunk read-back, and public-safe capture**

## Scope

- Planned scenario runs: `42`
- Scenario count: `14`
- Attempts per scenario: `3`
- Nondeterminism check: all `14 / 14` scenarios varied on at least two inspected axes.

## Live-service evidence

- Seeded HEC events: `125`
- Verified Splunk read-back events: `125`
- Verified Splunk read-back runs: `42`
- Verified Splunk read-back scenarios: `14`
- Captured public-safe runs: `42`
- Captured public-safe events: `125`
- Capture status set: `captured_live_splunk_public_safe`

## What touched live services

1. Loaded the refreshed local HEC token from `.env`.
2. Seeded each run in the 42-row manifest to Splunk HEC under the live batch ID.
3. Queried Splunk for the live batch and required read-back for all 42 run IDs.
4. Captured each run with `capture_splunk_run_v1.py --require-live-splunk-rows --verified-live-rows-jsonl`.

## Validation

- Focused regression tests: `26 passed`.
- Public-safety scan passed for:
  - `v1/reports/goal_runs/small_k3_harness_live42_20260526T180921Z/`
  - `v1/data/seed_manifests/small_k3_harness_live42_20260526T180921Z/`
  - `v1/data/resets/`
- Raw verified Splunk rows and per-run captures are under ignored `v1/data/raw_exports/` and should remain untracked unless a later sanitizer/promoter copies only public-safe subsets into a tracked release area.

## Notes

- This confirms the k=3 42-row harness path works end-to-end against the authorized local Splunk lab.
- Scenarios `016`, `021`, and `023` currently produce single-event public-safe seed/capture rows in this harness path, so they are live-verified but thinner than the richer multi-event scenarios.
- The live collection still uses weak/scaffolded labels and should be treated as harness evidence, not production malicious ground truth.
