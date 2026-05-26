# Full live 5,000-row run validation

Generated: 2026-05-26T20:48:14Z

## Batch

- Batch ID: `all_scenarios_5k_live_20260526T201126Z`
- Manifest: `v1/data/run_manifests/all_scenarios_5k_live_20260526T201126Z/scenario_runs.jsonl`
- Raw public-safe captures: `v1/data/raw_exports/all_scenarios_5k_live_20260526T201126Z/` *(gitignored/private working artifact root)*
- Training CSV: `v1/data/training/all_scenarios_5k_live_20260526T201126Z/windows_actor_15m.csv`

## Live Splunk loop

- Seeded scenario runs: 5000
- Expected/live verified events: 17218
- Expected/live verified runs: 5000
- Captured run manifests: 5000
- Captured event rows: 17218
- Capture status counts: `{'captured_live_splunk_public_safe': 5000}`

Read-back note: the configured Splunk MCP bearer path returned `401 Unauthorized` during this run, so the live read-back used the local direct Splunk REST path with existing private credentials. No credential values were printed or written to public artifacts.

## Training CSV validation

- Rows: 5000
- Columns: 71
- Feature columns: 60
- Required core-column gaps: `[]`
- Forbidden manifest/provenance columns leaked: `[]`
- Label counts: `{'0': 3623, '1': 1377}`
- Outcome counts: `{'failed': 950, 'blocked': 400, 'benign': 1650, 'attempted': 625, 'needs_review': 425, 'successful_synthetic': 950}`

### Label-family counts

| label_family | rows |
|---|---:|
| `benign_investigation` | 1171 |
| `failed_tamper_attempt` | 950 |
| `permission_probe` | 484 |
| `evidence_laundering` | 460 |
| `alert_suppression` | 459 |
| `suspicious_recon` | 425 |
| `benign_admin` | 254 |
| `routing_or_transform_tamper` | 229 |
| `benign_visibility_change` | 172 |
| `report_alibi_generation` | 115 |
| `lookup_or_report_overwrite` | 114 |
| `input_or_token_tamper` | 114 |
| `benign_alert_tuning` | 53 |


## Validation commands run

- `uv run --directory v1 python scripts/raw_harness_jsonl_to_training_csv_v1.py --input data/raw_exports/all_scenarios_5k_live_20260526T201126Z --run-manifest data/run_manifests/all_scenarios_5k_live_20260526T201126Z/scenario_runs.jsonl --output data/training/all_scenarios_5k_live_20260526T201126Z/windows_actor_15m.csv --window-size-sec 900 --fail-on-empty`
- Training CSV structural/leakage validation: PASS
- `uv run --directory v1 pytest tests/test_raw_harness_jsonl_to_training_csv_v1.py -q`: PASS, 15 tests
- `uv run --directory v1 pytest -q`: PASS, 164 tests
- `git diff --check`: PASS
- Public-safety scan across `v1/reports/5k_runs`, `v1/reports/runs`, and the 5k training CSV for private IPs, home paths, env references, and credential assignments: PASS

## Caveats

- This is still a synthetic/lab corpus with weak working-model labels, not malicious ground truth.
- The successful result validates the end-to-end live plumbing and public-safe training-window generation; it does not claim production detection quality.
- No Openclaw grading was performed.
