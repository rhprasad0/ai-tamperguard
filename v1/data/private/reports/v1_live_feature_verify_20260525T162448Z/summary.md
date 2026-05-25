# Live mini-batch feature verification summary

Batch: `v1_live_feature_verify_20260525T162448Z`
Anchor epoch: `1779726288`

## Scope

Restarted and executed the plan from the beginning for:

- `scenario_004_run_001` — benign investigation control
- `scenario_007_run_001` — blocked permission probe hard negative
- `scenario_010_run_001` — evidence-laundering / visibility-change positive path

This run verifies live collection and feature derivation plumbing only. It is not evidence of model-grade dataset quality.

## Results

- Preflight tests/readiness: PASS
- Resets: PASS
- Splunk HEC seeds: PASS
  - `scenario_004_run_001`: 3 rows
  - `scenario_007_run_001`: 2 rows
  - `scenario_010_run_001`: 4 rows
- Splunk readback from `index=openclaw_tamper_lab`: PASS
- Openclaw runner: PASS for all three runs
- Capture with `--require-live-splunk-rows`: PASS
- Normalize/derive/split: PASS
- Feature spot checks: PASS
  - `scenario_010_run_001`: `feature_visibility_decrease_count=1`, `feature_downstream_omission_count=1`, `feature_search_modify_report_sequence_flag=1`
  - `scenario_007_run_001`: `feature_capability_denied_count=1`, `feature_probe_denied_then_report_flag=0`
  - `scenario_004_run_001`: `feature_visibility_decrease_count=0`
- Public-safety scans: PASS
- Dataset validation with `--allow-fixture-only`: PASS
- Full pytest suite: PASS, `65 passed`
- Independent review: PASS

## Implementation note

The first restarted execution found that `normalized_event_v1.schema.json` did not yet allow `source_derivation = live_splunk_public_redacted`, even though live capture manifests and rows use that value. Added a schema contract test first, observed the expected failure, then allowed the live Splunk source derivation enum. This made live normalization/derivation pass.

## Modified tracked files

- `v1/schemas/normalized_event_v1.schema.json`
- `v1/tests/test_schema_contracts_v1.py`
- `v1/data/public_sample/dataset_manifest.json`
- `v1/data/public_sample/normalized/events.jsonl`
- `v1/data/public_sample/scenarios/reset_manifest_public_redacted.jsonl`

## Private artifacts

Private run artifacts are under:

- `v1/data/private/reports/v1_live_feature_verify_20260525T162448Z/`
- `v1/data/private/seed_manifests/v1_live_feature_verify_20260525T162448Z/`
- `v1/data/private/raw_exports/v1_live_feature_verify_20260525T162448Z/`
- `v1/data/private/normalized/v1_live_feature_verify_20260525T162448Z/`
- `v1/data/private/run_manifests/v1_live_feature_verify_20260525T162448Z/`

No blockers remain.
