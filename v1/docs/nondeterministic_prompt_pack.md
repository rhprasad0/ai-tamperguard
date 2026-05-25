# Nondeterministic Prompt Pack

AI TamperGuard uses this prompt pack to create bounded uncertainty-driven exploration in synthetic lab runs. The objective is not to make an agent behave maliciously. The objective is to collect public-safe traces where an actor-agent may choose different investigation paths, enumerate synthetic metadata, discover synthetic knowledge objects, re-query evidence, read sacrificial visibility notes, or write a conservative synthetic report.

## Safety boundary

Allowed surfaces:

- Synthetic scenario evidence in the sacrificial lab namespace.
- Public-safe summaries of protected evidence surfaces such as audit and configuration-history families.
- Synthetic metadata and knowledge-object summaries.
- Sacrificial report or note objects created for the scenario.
- Read-only Splunk MCP metadata, when the authorized lab exposes it.

Forbidden surfaces:

- Real credentials, real access tokens, private prompts, private operator notes, hostnames, usernames, IP addresses, URLs, raw SPL, or raw Splunk rows in public artifacts.
- Production systems or personal telemetry.
- Destructive clearing, deletion, suppression, or disabling of non-sacrificial observability.
- Dashboard, alert, or saved-search mutation in this first prompt-pack slice. The only optional write surface is a sacrificial report or note object.

## Public catalog

The public catalog is stored at:

```text
scenarios/nondeterministic_prompt_pack_v1.jsonl
```

Each row defines a public-safe prompt variant with:

- `prompt_variant_id`
- `prompt_family`
- `prompt_pack_version`
- `allowed_scenario_ids`
- `trajectory_goal_family`
- `max_tool_budget`
- `template`
- `safety_boundary`
- `expected_public_event_families`

The five starter families are:

| Family | Purpose | Expected trace shape |
|---|---|---|
| `uncertain_soc_analyst` | Resolve incomplete synthetic evidence. | Bounded searches, metadata checks, visibility reads. |
| `operator_handoff_asset_map` | Convert a vague handoff into a synthetic object map. | Metadata enumeration, knowledge-object discovery, report reads. |
| `conflicting_evidence_resolution` | Compare conflicting synthetic notes. | Re-query, visibility reads, conservative report writing. |
| `limited_budget_choose_path` | Force different path choices under a small budget. | Seeded differences in action order or action mix. |
| `soft_temptation_visibility_object` | Exercise gray-zone interaction with a sacrificial note. | Visibility reads, blocked probes, optional report-only write. |

## Dry-run materialization

Generate private actor prompts and private run manifests without contacting Splunk, Graphiti, or model services:

```bash
uv run python scripts/materialize_prompt_pack_runs_v1.py \
  --prompt-pack scenarios/nondeterministic_prompt_pack_v1.jsonl \
  --scenario scenario_006 \
  --batch-id nondet_static_check_001 \
  --attempts 3 \
  --seed 20260525 \
  --output-dir data/private/run_manifests/nondet_static_check_001 \
  --dry-run \
  --force
```

The materializer writes only under `data/private/run_manifests/<batch>/`:

- `scenario_runs_private.jsonl`
- `prompt_pack_manifest.json`
- `actor_prompts/<scenario_run_id>.txt`

Private actor-prompt text is never copied into `data/public_sample/`.

## Seed, capture, and normalize with prompt metadata

For a later authorized lab run, seed scenario evidence with prompt metadata so the capture and normalized rows can be traced back to the prompt variant without exposing the prompt body:

```bash
uv run python scripts/seed_splunk_scenario_evidence_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial-inventory.toml \
  --scenario scenario_006 \
  --scenario-run-id scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001 \
  --reset-id reset_006_001 \
  --batch-id nondet_batch_001 \
  --anchor-epoch 1234567890 \
  --output-manifest data/private/seed_manifests/nondet_batch_001/scenario_006.json \
  --prompt-variant-id operator_handoff_asset_map_v1_a \
  --prompt-family operator_handoff_asset_map \
  --prompt-pack-version nondet-v1-20260525 \
  --prompt-seed 20260525 \
  --attempt-index 1 \
  --dry-run
```

Replace `--dry-run` with live HEC writes only after the lab-readiness gate has passed and Ryan has explicitly approved live execution.

## First live-pass recommendation

When the static gates are green and the lab is explicitly authorized, use this small collection shape first:

- Scenario: `scenario_006`.
- Prompt variants: all five starter variants that allow `scenario_006`.
- Attempts: three per variant, for fifteen total runs.
- Graphiti writes: disabled during repeated attempts.
- Post-run memory: one reviewed, sanitized aggregate summary to Graphiti group `policy-bonfire-2`.

Useful public-safe metrics:

- `trajectory_signature_count`
- `first_tool_distribution`
- `knowledge_object_discovery_rate`
- `permission_probe_rate`
- `modification_attempt_rate`
- `evidence_chain_completion_rate`
- `trajectory_outcome_review_queue_count`
- `public_safe_capture_completeness_rate`

## Static validation

Run these before any live actor/model/Splunk execution:

```bash
uv run pytest tests/test_prompt_pack_v1.py tests/test_materialize_prompt_pack_runs_v1.py -q
uv run pytest tests/test_scenario_events_v1.py tests/test_seed_splunk_scenario_evidence_v1.py -q
uv run python scripts/public_safety_scan_v1.py data/public_sample docs schemas scenarios
```

These checks verify that the public catalog is safe, prompt bodies remain private, scenario 006 can express wandering traces, and prompt metadata survives dry-run seeding.
