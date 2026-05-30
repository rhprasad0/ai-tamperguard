# AI TamperGuard V1 Dataset Workspace

This workspace contains the V1 dataset pipeline scaffold for a scenario-grounded Splunk observability-tamper corpus.

**Final v1 status:** archived as an evidence/data plumbing milestone. The project produced a live-backed 5,000-row behavior-window corpus and a bounded AutoResearch / technique bakeoff, but the selected custom model was not deployed into Splunk. See [`../docs/project-closeout.md`](../docs/project-closeout.md).

## Boundary

- Public artifacts under `data/public_sample/` are redacted and use stable pseudonyms.
- Private live-lab config belongs only under ignored paths such as `splunk/private/`.
- Raw live Splunk exports belong under ignored `data/raw_exports/`; derived public-safe samples should be copied to `data/public_sample/` instead of tracking raw export roots.
- Public-safe generated run artifacts belong in tracked `data/`, `reports/`, `models/`, `scenarios/`, and `docs/` paths.
- Generated actor prompt bodies are intended to be tracked under `data/run_manifests/` when they are public-safe, so reviewers can inspect the scenario instructions that produced a run.
- The checked-in public sample is a **synthetic fixture/smoke sample**, not a public release candidate. A release candidate must include authorized live Splunk lab runs and pass the validation gate without fixture-only relaxations.
- Do not commit real secrets, credentials, tokens, PII, private hostnames/URLs, raw private SPL, private lab config, or unredacted private exports. The lobster is public; the bait bucket is not.

## Scenario and variant inspection

Scenario configuration is meant to be reviewable without running Splunk.

Current inspectable inputs:

| Artifact | Purpose |
|---|---|
| `scenarios/scenario_catalog_v1.jsonl` | Authoritative scenario catalog replacing `scenario_subset_v1.jsonl` for all-scenario coverage. |
| `scenarios/path_templates_v1.jsonl` | Explicit benign/control, hard-negative, blocked, attempted, and synthetic-positive path templates. |
| `scenarios/scenario_subset_v1.jsonl` | Deprecated migration source for the original executable subset. New code should read the catalog. |
| `scenarios/nondeterministic_prompt_pack_v1.jsonl` | Public-safe prompt variants used to create nondeterministic actor runs. |
| `scenarios/generated/<batch_id>/candidate-config.json` | Candidate nondeterminism optimizer settings for generated prompt-pack experiments. |
| `scenarios/generated/<batch_id>/nondeterministic_prompt_pack_v1.generated.jsonl` | Generated prompt-pack copy for a candidate/batch. |
| `data/run_manifests/<batch_id>/scenario_runs.jsonl` | Run metadata for a generated or live batch. |
| `data/run_manifests/<batch_id>/**/actor_prompts/*.txt` | Public-safe generated actor prompt bodies for individual scenario runs. |
| `data/run_manifests/<batch_id>/coverage_summary.json` | Coverage proof for scenario, family, path, prompt, and label coverage. |
| `reports/goal_runs/<batch_id>/goal-summary.md` | Human-readable nondeterminism or batch summary. |
| `reports/goal_runs/<batch_id>/goal-summary.json` | Machine-readable nondeterminism or batch summary. |

## Quick inspection commands

List current scenario IDs, names, families, and status:

```bash
uv run --directory v1 python - <<'PY'
import json
from pathlib import Path
path = Path('scenarios/scenario_catalog_v1.jsonl')
for line in path.read_text().splitlines():
    row = json.loads(line)
    path_types = ','.join(row['path_types_supported'])
    print(f"{row['scenario_id']}\t{row['family']}\t{row.get('canonical_status', '')}\t{path_types}\t{row['name']}")
PY
```

List path templates and labels:

```bash
uv run --directory v1 python - <<'PY'
import json
from pathlib import Path
path = Path('scenarios/path_templates_v1.jsonl')
for line in path.read_text().splitlines():
    row = json.loads(line)
    print(f"{row['path_template_id']}\t{row['scenario_id']}\t{row['path_type']}\t{row['label_binary_policy']}\t{row['outcome']}")
PY
```

List prompt variants and the scenarios they can run against:

```bash
uv run --directory v1 python - <<'PY'
import json
from pathlib import Path
path = Path('scenarios/nondeterministic_prompt_pack_v1.jsonl')
for line in path.read_text().splitlines():
    row = json.loads(line)
    scenarios = ','.join(row['allowed_scenario_ids'])
    print(f"{row['prompt_variant_id']}\t{row['prompt_family']}\t{scenarios}")
PY
```

Inspect a generated batch manifest:

```bash
uv run --directory v1 python - <<'PY'
import json
from pathlib import Path
batch = 'all_scenarios_dry_YYYYMMDDTHHMMSSZ'
path = Path('data/run_manifests') / batch / 'scenario_runs.jsonl'
for line in path.read_text().splitlines()[:20]:
    row = json.loads(line)
    print(f"{row.get('scenario_run_id')}\t{row.get('scenario_id')}\t{row.get('path_type')}\t{row.get('prompt_variant_id')}\tseed={row.get('prompt_seed')}")
PY
```

Generate a dry-run all-scenario manifest and coverage summary:

```bash
uv run --directory v1 python scripts/generate_training_batch_v1.py \
  --scenario-catalog scenarios/scenario_catalog_v1.jsonl \
  --path-templates scenarios/path_templates_v1.jsonl \
  --prompt-pack scenarios/nondeterministic_prompt_pack_v1.jsonl \
  --batch-id all_scenarios_dry_YYYYMMDDTHHMMSSZ \
  --target-runs 14 \
  --target-windows-min 5000 \
  --target-windows-max 5500 \
  --seed 260526 \
  --mode dry-run \
  --output-dir data/run_manifests/all_scenarios_dry_YYYYMMDDTHHMMSSZ
```

Preview generated actor prompts for a batch:

```bash
uv run --directory v1 python - <<'PY'
from pathlib import Path
batch = Path('data/run_manifests/live_goal_other_ready_20260525T221248Z')
for path in sorted(batch.glob('**/actor_prompts/*.txt'))[:10]:
    print('\n---', path)
    print(path.read_text()[:600])
PY
```

After `scenario_catalog_v1.jsonl` and `path_templates_v1.jsonl` land, prefer inspecting those files instead of `scenario_subset_v1.jsonl`.

## Useful validation commands

```bash
uv run --directory v1 pytest
uv run --directory v1 python scripts/validate_dataset_v1.py --schemas schemas --sample data/public_sample --check all --allow-fixture-only
uv run --directory v1 python scripts/public_safety_scan_v1.py data/run_manifests data/public_sample docs schemas scenarios reports/goal_runs reports/artifact-cleanup-20260525
git check-ignore -v v1/data/raw_exports/example_batch/public_safe_events.jsonl
```

Run live readiness only after creating an ignored private lab config; write the public-safe readiness report to tracked reports/runs/:

```bash
uv run --directory v1 python scripts/check_splunk_readiness_v1.py --config splunk/private/lab.toml --output reports/runs/splunk-readiness-local.md
```

## First all-scenario training result

The all-scenario expansion target completed as the live batch `all_scenarios_5k_live_20260526T201126Z`:

- 5,000 live-backed behavior-window rows.
- 17,218 Splunk read-back verified events.
- 60 `feature_*` columns, with a six-feature explicit model allowlist for the final bakeoff.
- Selected bakeoff candidate: `logistic_regression/default_balanced`.

The selected model is a research artifact only. It was **not deployed into Splunk**; live normalization, feature parity, and Splunk-side scoring equivalence are intentionally left as a future project rather than claimed here.

Final closeout: [`../docs/project-closeout.md`](../docs/project-closeout.md).
