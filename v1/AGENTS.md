# AI TamperGuard v1 Agent Guide

This directory contains the v1 testing harness for generating, validating, and optionally live-capturing public-safe Splunk/SOC behavior-window data.

The harness flow is:

```text
scenario catalog + path templates + prompt pack
→ generated scenario run manifest
→ optional live Splunk seed/read-back capture
→ public-safe raw events
→ behavior-window training CSV
→ validation, leakage checks, and public-safety scan
```

## Boundaries

- Use only authorized local Splunk lab data and synthetic/sacrificial fixtures.
- Do not commit `.env`, `splunk/private/`, raw private exports, real tokens, credentials, PII, private hostnames, or unredacted SPL.
- Live Splunk runs are gated: do **not** run live seed/capture commands unless the user explicitly asks for live collection.
- Public outputs should be reviewable and public-safe; generated raw exports stay under ignored `data/raw_exports/`.
- Treat labels as weak proxy labels for harness/model plumbing, not as production malicious-ground-truth claims.

## Standard commands

Run commands from the repository root unless noted.

### 1. Run the Python test suite

```bash
uv run --directory v1 pytest -q
```

### 2. Generate a dry-run 5k all-scenario manifest

Dry-run generation does not touch Splunk. Keep generated manifests under `v1/data/run_manifests/`.

```bash
BATCH_ID="all_scenarios_dry_$(date -u +%Y%m%dT%H%M%SZ)"
uv run --directory v1 python scripts/generate_training_batch_v1.py \
  --scenario-catalog scenarios/scenario_catalog_v1.jsonl \
  --path-templates scenarios/path_templates_v1.jsonl \
  --prompt-pack scenarios/nondeterministic_prompt_pack_v1.jsonl \
  --allocation-config config/v1_5k_all_scenarios.yaml \
  --batch-id "$BATCH_ID" \
  --seed 260526 \
  --output-dir "data/run_manifests/$BATCH_ID" \
  --no-reset-required
```

Expected dry-run evidence includes `scenario_runs.jsonl`, actor prompts, and `coverage_summary.json` under the batch directory.

### 3. Validate public-safe artifacts

```bash
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all \
  --allow-fixture-only

uv run --directory v1 python scripts/public_safety_scan_v1.py \
  data/public_sample docs schemas scenarios reports/goal_runs
```

### 4. Convert captured harness JSONL into training CSV

Use this after a live or scaffolded capture has written `public_safe_events.jsonl` files under a batch in `data/raw_exports/`.

```bash
uv run --directory v1 python scripts/raw_harness_jsonl_to_training_csv_v1.py \
  --input "data/raw_exports/<batch_id>" \
  --run-manifest "data/run_manifests/<batch_id>/scenario_runs.jsonl" \
  --output "data/training/<batch_id>/windows_actor_15m.csv" \
  --window-size-sec 900 \
  --fail-on-empty
```

Published training windows should not expose answer-key-shaped metadata such as `scenario_id`, `path_type`, prompt IDs, or template IDs; keep only allowed IDs, label fields, and numeric/boolean `feature_*` columns.

## Live harness pattern

Only use this section after explicit user approval for a live run.

1. Confirm private readiness:

```bash
uv run --directory v1 python scripts/check_splunk_readiness_v1.py \
  --config splunk/private/lab.toml \
  --output reports/runs/splunk-readiness-local.md
```

2. For each selected row in `data/run_manifests/<batch_id>/scenario_runs.jsonl`, reset, seed, and capture using its `scenario_id`, `scenario_run_id`, `reset_id`, prompt metadata, `path_type`, and `outcome`:

```bash
uv run --directory v1 python scripts/reset_lab_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial_inventory.toml \
  --scenario <scenario_id> \
  --reset-id <reset_id>

uv run --directory v1 python scripts/seed_splunk_scenario_evidence_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial_inventory.toml \
  --scenario <scenario_id> \
  --scenario-run-id <scenario_run_id> \
  --reset-id <reset_id> \
  --batch-id <batch_id> \
  --anchor-epoch <unix_epoch> \
  --output-manifest "data/raw_exports/<batch_id>/<scenario_run_id>/seed-manifest.json" \
  --prompt-variant-id <prompt_variant_id> \
  --prompt-family <prompt_family> \
  --prompt-pack-version <prompt_pack_version> \
  --prompt-seed <prompt_seed> \
  --attempt-index <attempt_index> \
  --path-type <path_type> \
  --outcome <outcome>

uv run --directory v1 python scripts/capture_splunk_run_v1.py \
  --config splunk/private/lab.toml \
  --scenario-run-id <scenario_run_id> \
  --reset-id <reset_id> \
  --batch-id <batch_id> \
  --earliest-epoch <unix_epoch> \
  --require-live-splunk-rows \
  --output-dir "data/raw_exports/<batch_id>/<scenario_run_id>"
```

3. Convert captured raw JSONL to training CSV, then rerun tests, validation, leakage checks, and the public-safety scan before treating the corpus as usable.

## Before handing off

- Run `git diff --check`.
- Run focused tests for changed code and `uv run --directory v1 pytest -q` when practical.
- Report exact commands and pass/fail status.
- Leave live/private artifacts ignored unless the user explicitly asks for a public-safe tracked artifact.
