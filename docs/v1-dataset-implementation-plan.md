# AI TamperGuard V1 Dataset Implementation Plan

This plan turns `docs/v1-dataset-spec.md` into a Hermes Kanban-executable V1 dataset workflow. It assumes the first V1 deliverable is a trainable public sample dataset under `v1/data/public_sample/`, backed by live Splunk lab runs and reset records. It does not require committing private data or training a final model.

Do not modify `.worktrees/`. Do not commit during implementation unless a separate request asks for it.

## Implementation Principles

- Use live authorized Splunk lab runs; do not replace V1 with purely synthetic-only generation.
- Implement the first scenario subset, not all 24 scenarios.
- Keep public/private boundaries explicit in every script, schema, and artifact.
- Treat labels as weak working-model labels: tamper-congruent, observability-degrading, evidence-laundering, synthetic positive, and needs review.
- Make every generated public file reproducible from normalized public-safe events plus scenario metadata.
- Preserve the v0 lesson: a dataset is not complete until downstream scoring or model training has a clear handoff path.


## Hermes Kanban Execution Model

This plan is intended to be executable through Hermes Kanban, not as one giant monolithic agent prompt. Use the board as the audit trail for the live-lab build: each card should produce a small, reviewable slice with explicit validation output, and downstream cards should start only after their parent card has completed or been unblocked.

### Board setup

Create one board for the V1 dataset implementation, for example:

```bash
hermes kanban boards create ai-tamperguard-v1-dataset
```

Before creating cards, discover the profiles that actually exist on the machine:

```bash
hermes profile list
```

Do not invent assignee names. If no existing profile clearly fits a card, pause and ask which profile should own it. The dispatcher will not reliably recover from made-up profile names; it will simply leave the lobster traps empty.

### Worktree / branch convention

Use one shared implementation branch and one shared implementation workspace for the board unless the controller explicitly chooses otherwise:

```text
branch: feature/v1-dataset
workspace: .worktrees/v1-dataset-kanban/   # or the board-managed equivalent
```

Rules for workers:

- work only inside the assigned implementation workspace;
- do not commit unless the controller card explicitly asks for it;
- do not modify `.worktrees/` except for the designated implementation workspace;
- keep public-safe generated outputs under tracked `v1/data/` and `v1/reports/` paths; only real secrets, credentials, tokens, PII, local lab config, and model bundles with private material belong under ignored `v1/models/private/` or `v1/splunk/private/` paths;
- include exact validation commands and results in the card completion summary;
- block with `review-required:` when a live Splunk credential, lab endpoint, reset decision, or public/private boundary decision is needed.

### Suggested Kanban task graph

Use these as the first-pass card IDs/titles. Parent links should be real Kanban dependencies, not prose-only instructions.

| Card | Title | Depends on | Primary output |
|---|---|---|---|
| K0 | Scaffold V1 repo layout and ignore rules | none | `v1/` skeleton, private-path guards |
| K1 | Add schemas and contract tests | K0 | JSON schemas and schema tests |
| K2 | Add Splunk readiness checker | K0 | readiness script and private report template |
| K3 | Add reset and reset verification workflow | K1, K2 | allowlisted reset scripts and reset manifest schema |
| K4 | Encode V1 scenario subset catalog | K1 | required scenario subset JSONL |
| K5 | Add live run capture workflow | K3, K4 | private capture/run manifest workflow |
| K6 | Add normalization and redaction workflow | K5 | public-safe normalized events |
| K7 | Add answer-key and verification artifacts | K4, K6 | public/private answer-key artifacts |
| K8 | Derive windows, episodes, and graph edges | K6, K7 | derived analytical views |
| K9 | Generate leakage-aware splits | K8 | split files and split manifest |
| K10 | Build public sample package | K7, K8, K9 | `v1/data/public_sample/` package |
| K11 | Add privacy, claim, and dataset validation | K10 | validator and safety scanner |
| K12 | Add model-training handoff template | K10, K11 | baseline-training handoff docs |
| K13 | Final controller read-back and merge decision | K11, K12 | board summary, repo status, final validation report |

K1, K2, and K4 can run in parallel after K0. K3 waits for K1 and K2 because reset manifests need schemas and live-lab readiness needs to be known. K5 and later should be mostly serialized because they operate on the same dataset artifact chain.

### Review and recovery gates

After each card, the controller should verify the card-specific output before unblocking downstream work. At minimum:

```bash
git status --short --untracked-files=all
git diff --check
```

For documentation-only cards, also check Markdown fence balance and required terminology. For implementation cards, run the phase-specific tests named below. If a worker blocks or produces a partial candidate, preserve the card as the audit trail, patch or reassign through a follow-up card, and record the candidate workspace path in the downstream card comments.

### Controller completion checklist

Before reporting the Kanban run as complete:

1. list the board and confirm every K-card is `done` or intentionally deferred;
2. inspect the implementation workspace branch and root repo status;
3. rerun the final validation commands from this plan;
4. verify that only intended files are staged/committed;
5. summarize deferred open questions separately from completed work.

## Phase 0 / K0: Repository Scaffolding

Create these public paths:

```text
v1/
  README.md
  .gitignore
  docs/
    data_dictionary.md
    redaction_methodology.md
    known_limitations.md
  schemas/
    normalized_event_v1.schema.json
    scenario_catalog_v1.schema.json
    scenario_run_v1.schema.json
    reset_manifest_v1.schema.json
    answer_key_v1.schema.json
    behavior_window_v1.schema.json
    episode_v1.schema.json
    actor_object_edge_v1.schema.json
    split_manifest_v1.schema.json
  scenarios/
    scenario_subset_v1.jsonl
  scripts/
    check_splunk_readiness_v1.py
    reset_lab_v1.py
    verify_reset_v1.py
    capture_splunk_run_v1.py
    normalize_events_v1.py
    derive_windows_v1.py
    derive_episodes_v1.py
    derive_edges_v1.py
    generate_splits_v1.py
    build_public_sample_v1.py
    public_safety_scan_v1.py
    validate_dataset_v1.py
  tests/
    test_schema_contracts_v1.py
    test_relationship_integrity_v1.py
    test_split_integrity_v1.py
    test_public_safety_v1.py
    test_derivation_v1.py
  data/
    public_sample/
      README.md
      normalized/
      scenarios/
      derived/
      splits/
  splunk/
    searches/
      templates/
  reports/
    templates/
```

Keep ignore rules limited to genuinely private locations:

```text
v1/models/private/
v1/splunk/private/
```

Suggested files to modify in this phase:

- `v1/.gitignore`: ignore all private/generated V1 artifacts.
- root `.gitignore`: add V1 private paths if the repo-level ignore should protect them too.
- `v1/README.md`: explain V1 status, run commands, public/private boundary, and non-claims.

Validation:

```bash
git status --short
git diff --check
```

Commit checkpoint, if commits are later requested:

```text
checkpoint 1: scaffold v1 dataset directories, ignore rules, and docs placeholders
```

## Phase 0.5 / K1: Schemas and Contract Tests

Goal: establish machine-checkable contracts before live lab work or generated artifacts appear.

Create or stub all V1 schema files listed in the scaffolding section, plus schema contract tests that validate at least one minimal positive fixture and one intentionally invalid fixture per schema.

K1 should not depend on live Splunk. It should be safe to run entirely offline so later live-lab cards can fail for real lab reasons rather than schema ambiguity.

Validation command shape:

```bash
uv run --directory v1 pytest tests/test_schema_contracts_v1.py
uv run --directory v1 python scripts/validate_dataset_v1.py --schemas schemas --check schemas-only
```

Tests/checks:

- every schema file exists;
- controlled vocabularies are encoded where expected;
- required fields reject missing IDs, label fields, and reset/run linkage fields;
- public-safe field constraints reject obvious private strings in public artifact examples.

Commit checkpoint, if commits are later requested:

```text
checkpoint 1.5: add v1 schemas and schema contract tests
```

## Phase 1 / K2: Splunk Readiness

Goal: prove the live lab can support repeatable V1 runs before collecting data.

Implement `v1/scripts/check_splunk_readiness_v1.py` to verify:

- Splunk connection config exists only under `v1/splunk/private/`.
- The configured Splunk endpoint is explicitly verified as an authorized lab endpoint, not a production deployment. This should use an allowlisted lab marker such as an expected app namespace, fixture index, banner marker, or private readiness value; a reachable endpoint alone is not enough.
- Target app namespace exists or can be prepared safely.
- Protected evidence surfaces are queryable: audit/config evidence, scenario fixture evidence, and optional agent/tool telemetry.
- Sacrificial artifacts exist or can be created from fixtures: dashboards, saved searches, alerts, lookups, reports, and optional synthetic inputs.
- The run operator has only the intended lab capability surface.
- The lab clock, time zone handling, and relative-time conversion are documented.
- Capture and export destinations for public-safe generated artifacts are tracked `v1/data/**` and `v1/reports/**` paths; only credential-bearing lab config, true secrets, tokens, PII, and private model material stay in ignored private paths.

Recommended public-safe generated outputs:

```text
v1/reports/runs/splunk-readiness-<batch_id>.md
v1/data/readiness/readiness-<batch_id>.json
```

Validation command shape:

```bash
uv run --directory v1 python scripts/check_splunk_readiness_v1.py \
  --config splunk/private/lab.toml \
  --output reports/runs/splunk-readiness-<batch_id>.md
```

Open decision to record in the readiness report:

- whether first execution uses MCP, scripted REST, scheduled searches, or a manual runbook;
- which optional surfaces are available for Scenario 016, Scenario 021, and Scenario 023;
- whether AI Assistant or MCP telemetry is captured directly or represented through redacted operator notes;
- the redaction contract for operator notes: prompt text is private by default, public rows may include only controlled action summaries, public IDs, relative time, and bounded outcome fields.

Commit checkpoint:

```text
checkpoint 2: add Splunk readiness checker and private readiness report template
```

## Phase 2 / K3: Reset Mechanism

Goal: make every scenario run start from a known lab state.

Implement:

- `v1/scripts/reset_lab_v1.py`
- `v1/scripts/verify_reset_v1.py`
- `v1/schemas/reset_manifest_v1.schema.json`

Reset should:

1. restore sacrificial dashboards, saved searches, alerts, lookups, reports, and optional input fixtures from an explicit allowlist;
2. refuse to operate if a requested target is outside the sacrificial artifact allowlist;
3. clear or rotate synthetic evidence for the next run;
4. remove previous run output from sacrificial public-facing views;
5. preserve protected audit/config evidence;
6. write a private reset manifest;
7. produce a public redacted reset manifest row;
8. mark the next scenario run as excluded if reset fails partway through, until a later reset verification succeeds.

Public-safe reset output:

```text
v1/data/resets/reset-<reset_id>.json
v1/reports/runs/reset-<reset_id>.md
```

Public reset output in the sample:

```text
v1/data/public_sample/scenarios/reset_manifest_public_redacted.jsonl
```

Validation command shape:

```bash
uv run --directory v1 python scripts/reset_lab_v1.py \
  --config splunk/private/lab.toml \
  --scenario scenario_004 \
  --reset-id reset_<id>

uv run --directory v1 python scripts/verify_reset_v1.py \
  --config splunk/private/lab.toml \
  --reset-id reset_<id> \
  --output reports/runs/reset-<reset_id>.md
```

Tests/checks:

- reset manifest validates against schema;
- reset verification fails if expected sacrificial artifacts are missing;
- reset verification fails if prior run residue is visible in downstream sacrificial views;
- reset refuses to target any artifact outside the sacrificial allowlist;
- failed or partial resets produce exclusion records rather than release-candidate runs;
- public reset manifest contains only public-safe IDs and summaries.

Commit checkpoint:

```text
checkpoint 3: add reset and reset-verification workflow
```

## Phase 3 / K4: Scenario Subset Catalog

Goal: encode the first V1 subset as data before collecting runs.

Create:

```text
v1/scenarios/scenario_subset_v1.jsonl
v1/data/public_sample/scenarios/scenario_catalog.jsonl
```

Required first subset:

- `scenario_004`: accurate investigation report;
- `scenario_006`: MCP knowledge-object discovery sweep;
- `scenario_007`: permission probe that stops;
- `scenario_010`: dashboard alibi factory;
- `scenario_011`: saved-search narrowing after evidence discovery;
- `scenario_012`: alert suppression after matching evidence appears;
- `scenario_013`: benign alert tuning during maintenance.

Optional scenario rows may be present but marked `optional_v1` or `future`:

- `scenario_016`: episode narrative laundering;
- `scenario_021`: synthetic input or HEC token degradation;
- `scenario_023`: model-result dashboard hiding.

Each row should include:

```text
scenario_id
name
family
subset_status
paired_control_scenario_id
allowed_surfaces
allowed_object_types
reset_requirements
positive_condition
blocked_condition
post_run_verification
public_claim_boundary
known_limitations
```

Free-text fields such as `verification_basis` and `limitations` must be public-safe controlled summaries, not copied private notes. They must not contain hostnames, IP addresses, usernames, URLs, raw SPL, prompts, local paths, absolute timestamps, or descriptive private object names.

Validation:

```bash
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --scenario-catalog scenarios/scenario_subset_v1.jsonl \
  --check scenario_catalog
```

Commit checkpoint:

```text
checkpoint 4: encode first v1 scenario subset and optional future scenarios
```

## Phase 4 / K5: Live Run Execution and Capture

Goal: capture private evidence from resettable live Splunk lab runs.

Implement `v1/scripts/capture_splunk_run_v1.py` to:

- create or read a `scenario_run_id`;
- require a successful `reset_id`;
- capture protected audit/config evidence for the run window;
- capture synthetic fixture evidence and downstream sacrificial view results;
- capture optional redacted agent/tool telemetry;
- write public-safe run manifests and raw exports under tracked paths.

Public-safe generated paths:

```text
v1/data/raw_exports/<batch_id>/<scenario_run_id>/
v1/data/run_manifests/<batch_id>/scenario_runs.jsonl
v1/reports/runs/runs/<scenario_run_id>.md
```

Public redacted paths:

```text
v1/data/public_sample/scenarios/scenario_runs.jsonl
```

Minimum first collection target:

```text
2-5 runs each for scenario_004, scenario_010, scenario_011, scenario_012, and scenario_013
1-3 runs each for scenario_006 and scenario_007
optional stretch runs only after reset and capture gates are stable
```

This is deliberately smaller than the finished-corpus target. It is enough to exercise the full artifact shape and model-training handoff only if it contains at least one collected tamper-congruent positive run, its paired benign control, and one hard-negative run. A batch that is all benign, all positive, or missing hard negatives is a harness smoke test, not a V1 public-sample candidate.

Validation command shape:

```bash
uv run --directory v1 python scripts/capture_splunk_run_v1.py \
  --config splunk/private/lab.toml \
  --scenario-run-id scenario_004_run_<id> \
  --reset-id reset_<id> \
  --output-dir data/raw_exports/<batch_id>/scenario_004_run_<id>
```

Tests/checks:

- run manifest references a known scenario and reset;
- capture fails closed if reset verification did not pass;
- capture writes no files outside ignored private paths;
- public redacted run rows omit private values;
- the collected batch has at least one positive-label run and one negative or hard-negative run before normalization proceeds to public-sample generation.

Commit checkpoint:

```text
checkpoint 5: add live run capture workflow and private/public run manifest shapes
```

## Phase 5 / K6: Normalization and Redaction

Goal: convert private captures into public-safe actor/action/object events.

Implement:

- `v1/scripts/normalize_events_v1.py`
- `v1/schemas/normalized_event_v1.schema.json`
- `v1/docs/redaction_methodology.md`

Normalization must:

- assign stable public IDs for actors, objects, events, scenario runs, and resets;
- convert timestamps to `relative_time_sec` for public sample rows;
- map raw source details into controlled fields such as `source_surface`, `action`, `action_family`, `object_type`, `object_role`, and `status`;
- preserve `raw_event_ref` only as an opaque private pointer;
- strip raw SPL, private prompts, usernames, hostnames, IP addresses, email addresses, absolute timestamps, URLs, tokens, secrets, local paths, and concrete object names;
- reject descriptive opaque IDs that embed private context such as hostnames, usernames, environment names, or object names.

Output paths:

```text
v1/data/normalized/normalization_manifest.jsonl
v1/data/public_sample/normalized/events.jsonl
```

Validation command shape:

```bash
uv run --directory v1 python scripts/normalize_events_v1.py \
  --input data/raw_exports/<batch_id> \
  --run-manifest data/run_manifests/<batch_id>/scenario_runs.jsonl \
  --output-private data/normalized/normalization_manifest.jsonl \
  --output-public data/public_sample/normalized/events.jsonl
```

Tests/checks:

- schema validation passes;
- every public event has `redaction_level=public_safe`;
- public IDs are stable within the build;
- private-only fields are absent from public outputs.

Commit checkpoint:

```text
checkpoint 6: add normalization, redaction, and normalized event schema
```

## Phase 6 / K7: Answer Keys and Verification

Goal: connect labels to run outcomes and protected verification.

Create:

```text
v1/schemas/answer_key_v1.schema.json
v1/data/answer_keys/answer_key_private.jsonl
v1/data/public_sample/scenarios/answer_key_public_redacted.jsonl
```

Each public answer-key row should include:

```text
scenario_run_id
positive_intervals
actor_id
object_ids_or_types
label_family
outcome
label_source
verification_basis
limitations
```

Free-text fields such as `verification_basis` and `limitations` must be public-safe controlled summaries, not copied private notes. They must not contain hostnames, IP addresses, usernames, URLs, raw SPL, prompts, local paths, absolute timestamps, or descriptive private object names.

Verification should decide whether the run is benign, needs review, attempted, blocked, failed, or successful_synthetic. It should not infer intent. It should verify observable conditions such as evidence access followed by a visibility artifact change, or a report path conflicting with protected evidence.

Validation:

```bash
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --events data/public_sample/normalized/events.jsonl \
  --answer-key data/public_sample/scenarios/answer_key_public_redacted.jsonl \
  --check answer_key
```

Tests/checks:

- every positive interval references an existing `scenario_run_id`;
- every positive interval maps to at least one public event or object type;
- blocked and failed outcomes are distinguishable from successful synthetic outcomes;
- public answer keys contain no private values;
- free-text verification and limitation fields pass the same public-safety scan as event and window artifacts.

Commit checkpoint:

```text
checkpoint 7: add answer-key and verification artifacts
```

## Phase 7 / K8: Derived Windows, Episodes, and Edges

Goal: generate the analytical views used for model training and later sequence or graph work.

Implement:

- `v1/scripts/derive_windows_v1.py`
- `v1/scripts/derive_episodes_v1.py`
- `v1/scripts/derive_edges_v1.py`
- `v1/schemas/behavior_window_v1.schema.json`
- `v1/schemas/episode_v1.schema.json`
- `v1/schemas/actor_object_edge_v1.schema.json`

Public outputs:

```text
v1/data/public_sample/derived/windows_actor_5m.csv
v1/data/public_sample/derived/windows_actor_15m.csv
v1/data/public_sample/derived/episodes.jsonl
v1/data/public_sample/derived/action_sequences.jsonl
v1/data/public_sample/derived/actor_object_edges.jsonl
```

Derivation requirements:

- all model features use `feature_*` names;
- feature columns are numeric or boolean;
- no raw text or private identifiers appear in model features;
- labels are derived from the public redacted answer key or documented rules;
- episodes preserve action order and relative time;
- graph edges use public actor/object IDs and controlled edge types;
- derivation scripts must be deterministic: stable sort inputs, avoid random sampling unless a documented `--seed` is supplied, and regenerate byte-stable outputs for the same inputs and seed.

Validation command shape:

```bash
uv run --directory v1 python scripts/derive_windows_v1.py \
  --events data/public_sample/normalized/events.jsonl \
  --answer-key data/public_sample/scenarios/answer_key_public_redacted.jsonl \
  --output-dir data/public_sample/derived

uv run --directory v1 python scripts/derive_episodes_v1.py \
  --events data/public_sample/normalized/events.jsonl \
  --answer-key data/public_sample/scenarios/answer_key_public_redacted.jsonl \
  --output data/public_sample/derived/episodes.jsonl

uv run --directory v1 python scripts/derive_edges_v1.py \
  --events data/public_sample/normalized/events.jsonl \
  --output data/public_sample/derived/actor_object_edges.jsonl
```

Tests/checks:

- derived artifacts regenerate byte-for-byte or with documented stable ordering;
- every `scenario_run_id`, `actor_id`, and `object_id` resolves;
- no `feature_*` column is null;
- label counts include both `0` and `1` before model-training handoff.

Commit checkpoint:

```text
checkpoint 8: derive windows, episodes, action sequences, and graph edges
```

## Phase 8 / K9: Split Generation

Goal: persist train, validation, test, and optional holdout decisions before model training.

Implement:

- `v1/scripts/generate_splits_v1.py`
- `v1/schemas/split_manifest_v1.schema.json`
- `v1/tests/test_split_integrity_v1.py`

Public outputs:

```text
v1/data/public_sample/splits/train_windows.csv
v1/data/public_sample/splits/validate_windows.csv
v1/data/public_sample/splits/test_windows.csv
v1/data/public_sample/splits/heldout_scenarios.csv
v1/data/public_sample/splits/split_manifest.json
```

Split rules:

- group by `scenario_run_id` by default;
- keep paired controls with paired positive runs unless an experimental split declares otherwise;
- avoid actor and object leakage when sample size allows;
- record any actor or object that crosses splits in `split_manifest.json`, even when leakage is accepted for a small sample;
- reserve a scenario-family holdout once the subset has enough families;
- record all relaxations, seed values, per-split positive/negative counts, and small-sample fallback choices in `split_manifest.json`.

Validation command shape:

```bash
uv run --directory v1 python scripts/generate_splits_v1.py \
  --windows data/public_sample/derived/windows_actor_15m.csv \
  --scenario-runs data/public_sample/scenarios/scenario_runs.jsonl \
  --output-dir data/public_sample/splits \
  --seed 20260525
```

Tests/checks:

- every split row references an existing `window_id`;
- no default split leaks the same `scenario_run_id` across train, validation, and test;
- paired controls do not cross splits unless declared;
- label distribution is non-empty in train and test, or the manifest records why the sample is too small and marks the split as best-effort;
- actor/object cross-split leakage is absent or explicitly recorded with rationale;
- per-split positive and negative counts are present in the manifest.

Commit checkpoint:

```text
checkpoint 10: add split generation and leakage checks
```

## Phase 9 / K10: Public Sample Build

Goal: package a public-safe, trainable sample under `v1/data/public_sample/`.

Implement `v1/scripts/build_public_sample_v1.py` to:

- select eligible public-safe scenario runs;
- copy normalized events, scenario metadata, redacted answer keys, reset manifest rows, derived views, and split files into the sample layout;
- write `v1/data/public_sample/README.md` with source, boundary, labels, and limitations;
- record `dataset_build_id`, `schema_version`, `scenario_catalog_version`, and `source_batch_ids`.

Rules:

- the public sample must include live-run-derived rows;
- clearly marked synthetic supplement rows are allowed only as a supplement and only if needed for schema examples or hard-negative balance;
- the public sample manifest must state whether each row is live-run-derived or a synthetic supplement;
- the public sample must not contain secrets, private URLs, hostnames, IP addresses, email addresses, absolute timestamps, usernames, raw SPL from private searches, tokens, local paths, or unredacted prompts;
- every public row must be reproducible from private source artifacts through documented scripts.

Validation command shape:

```bash
uv run --directory v1 python scripts/build_public_sample_v1.py \
  --events data/public_sample/normalized/events.jsonl \
  --scenarios data/public_sample/scenarios \
  --derived data/public_sample/derived \
  --output data/public_sample
```

Commit checkpoint:

```text
checkpoint 9: build public-safe trainable v1 sample dataset
```

## Phase 10 / K11: Privacy, Claim, and Dataset Validation

Goal: block public release candidates that leak private data or overstate the dataset.

Implement:

- `v1/scripts/public_safety_scan_v1.py`
- `v1/scripts/validate_dataset_v1.py`
- `v1/tests/test_public_safety_v1.py`
- `v1/tests/test_relationship_integrity_v1.py`

Validation command set:

```bash
test -f docs/v1-dataset-spec.md
test -f docs/v1-dataset-implementation-plan.md

rg -n "live Splunk lab runs|reset mechanism|scenario subset|v1/data/public_sample|tamper-congruent|observability-degrading|evidence-laundering|synthetic positive|needs review" \
  docs/v1-dataset-spec.md docs/v1-dataset-implementation-plan.md

rg -n --pcre2 "(?i)(password|passwd|api[_-]?key|secret|token|bearer)\\s*[:=]" \
  docs/v1-dataset-spec.md docs/v1-dataset-implementation-plan.md

rg -n --pcre2 "AKIA[0-9A-Z]{16}|BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY|eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+" \
  docs/v1-dataset-spec.md docs/v1-dataset-implementation-plan.md

uv run --directory v1 python scripts/public_safety_scan_v1.py data/raw_exports data/run_manifests data/public_sample docs schemas scenarios reports/goal_runs reports/artifact-cleanup-20260525

uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all

uv run --directory v1 pytest

git diff --check
```

The secret-assignment grep and token-shape grep are expected to return no matches for tracked public-safe docs, generated artifacts, reports, scenarios, schemas, and sample files. `public_safety_scan_v1.py` should fail closed for matches in public paths. If it finds a match in a private ignored path, that path must remain unpublished and the report should say the scan found private-only material that was excluded.

Quality gates enforced here:

- schema conformance;
- relationship integrity;
- answer-key traceability;
- reset/run linkage;
- split integrity;
- privacy scan, including common key/token shapes, private URLs, hostnames, IP addresses, email addresses, absolute timestamps, local paths, raw SPL, unredacted prompts, and descriptive opaque IDs;
- label-distribution and per-split count checks;
- claim-boundary review;
- regeneration checks for derived artifacts.

Commit checkpoint:

```text
checkpoint 11: add v1 validation, privacy scan, and quality gates
```

## Phase 11 / K12: Model-Training Handoff

Goal: make it easy to train a later baseline model from the public sample without pulling in private fields.

Create a handoff template:

```text
v1/reports/templates/model-training-handoff.md
```

The handoff should state:

- dataset build ID;
- behavior-window file selected for first training;
- split manifest path;
- label meaning and weak-label boundary;
- feature column pattern;
- excluded private fields;
- expected first model path, likely logistic regression or a small tree;
- required post-training checks: non-constant predictor, split respected, no private columns, per-split counts reported beside any metrics, and public wording remains conservative.

Optional later script:

```text
v1/scripts/train_public_sample_baseline_v1.py
```

Recommended future command shape:

```bash
uv run --directory v1 python scripts/train_public_sample_baseline_v1.py \
  --windows data/public_sample/derived/windows_actor_15m.csv \
  --splits data/public_sample/splits/split_manifest.json \
  --output models/private/public-sample-baseline.json
```

The model output is private by default until reviewed. Public sample data can be used to train a model later, but model metrics remain weak-label diagnostics unless a later spec upgrades the label standard.

Commit checkpoint:

```text
checkpoint 12: add model-training handoff template
```

## Final Implementation Validation / K13 Controller Gate

Run this lightweight validation before considering the two docs complete:

```bash
test -f docs/v1-dataset-spec.md
test -f docs/v1-dataset-implementation-plan.md

rg -n "live Splunk lab runs|reset mechanism|subset|v1/data/public_sample|tamper-congruent|observability-degrading|evidence-laundering|synthetic positive|needs review" \
  docs/v1-dataset-spec.md docs/v1-dataset-implementation-plan.md

rg -n --pcre2 "(?i)(password|passwd|api[_-]?key|secret|token|bearer)\\s*[:=]" \
  docs/v1-dataset-spec.md docs/v1-dataset-implementation-plan.md

rg -n --pcre2 "AKIA[0-9A-Z]{16}|BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY|eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+" \
  docs/v1-dataset-spec.md docs/v1-dataset-implementation-plan.md

git diff --check
```

For full V1 implementation after the scaffold exists, add:

```bash
uv run --directory v1 pytest
uv run --directory v1 python scripts/validate_dataset_v1.py --schemas schemas --sample data/public_sample --check all
uv run --directory v1 python scripts/public_safety_scan_v1.py data/raw_exports data/run_manifests data/public_sample docs schemas scenarios reports/goal_runs reports/artifact-cleanup-20260525
```

## Open Questions / Decisions

These open questions remain, but they do not block writing the spec or starting scaffolding:

1. First operator path: MCP, scripted REST, saved-search based runbooks, or manual execution with protected capture.
2. First public sample size: minimum trainable sample versus larger scenario coverage.
3. Optional scenario inclusion: whether Scenario 016, Scenario 021, or Scenario 023 are available in the current Splunk lab.
4. Public sample derivation policy: live-run-derived only, or live-run-derived plus clearly marked synthetic supplement rows.
5. Default window family for model handoff: `actor_5m`, `actor_15m`, `actor_60m`, or more than one.
6. Private evidence storage location: ignored repo-local paths, external private storage, or both.
7. Manual review threshold for promoting a `synthetic_positive` label to high confidence.
