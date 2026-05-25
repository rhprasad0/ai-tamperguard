# Plan: `/goal` harness for AI TamperGuard k=3 nondeterminism ≥50%

## Goal

Build a bounded harness that lets Ryan use a `/goal`-style autonomous coding loop to iterate on the AI TamperGuard V1 k=3 smoke workflow until at least 50% of tested k=3 groups exhibit measurable nondeterminism, while preserving safety, scenario semantics, public/tracked boundaries, with only real secrets/credentials/PII excluded, and the current **no Openclaw grading** phase.

The harness should turn the current one-off k=3 run workflow into a repeatable optimizer:

```text
analyze last k=3 batch
→ propose bounded prompt/scenario/environment candidate changes
→ dry-run materialize + score
→ live-gated Splunk write/read-back only after dry checks pass
→ capture → normalize → derive
→ score nondeterminism and semantic/control gates
→ stop when target is reached or budget is exhausted
```

## Current context / verified inputs

- Repo: `<repo>`
- V1 root: `<repo>/v1`
- Last referenced raw batch:
  - `v1/data/private/raw_exports/full_live_v1_k3_fixed_20260525T204429Z/` (legacy historical input; do not use this shape for new outputs)
- Last legacy reports (historical source artifacts; future outputs should be tracked/public):
  - `v1/reports/private/full_live_v1_k3_fixed_20260525T204429Z/nondeterminism-summary.json`
  - `v1/reports/private/full_live_v1_k3_fixed_20260525T204429Z/nondeterminism-analysis.md`
  - `v1/reports/private/full_live_v1_k3_fixed_20260525T204429Z/full-live-k3-fixed-nondeterminism-summary.md`
- Last k=3 run counts:
  - 11 required scenarios represented
  - 80 scenario runs
  - 23 nondeterministic `scenario_id + prompt_variant_id` groups
  - 315 Splunk-verified public-tracked events
  - 315 normalized events
  - 80 behavior windows
  - 80 episodes
  - 315 edges
- Last nondeterminism outcome after fixes:
  - `stable`: 22 trajectory groups / 22 feature groups
  - `partially_variable`: 1 trajectory group / 1 feature group
  - `variable`: 0 trajectory groups / 0 feature groups
  - only `scenario_006 + limited_budget_choose_path_v1_a` showed partial variability
  - no semantic failures
  - no control drift findings
- Graphiti project group confirmed by Graphiti reads: `policy-bonfire-2`
- Relevant Graphiti facts confirm:
  - batch `full_live_v1_k3_fixed_20260525T204429Z` completed
  - final validation passed
  - it ran after the prompt-seed nondeterminism fix
  - it covered 23 nondeterministic variant groups
- Honcho context confirms Ryan wants:
  - no Openclaw grading yet
  - Splunk write/read-back, capture → normalize → derive, feature extraction, paired controls, hard negatives
  - conservative claims
  - all non-secret TamperGuard artifacts tracked in public git paths; only real secrets, tokens, credentials, and PII excluded


## Resolved decision: public/tracked by default

Ryan corrected the prior private-first assumption after this plan was drafted. For AI TamperGuard going forward, the execution plan must treat **all non-secret artifacts as tracked public repo artifacts**. Do not design new outputs around `data/private/**` or `reports/private/**` unless the file contains actual secrets, credentials, tokens, PII, or other material that cannot be public. Existing private paths in historical inputs may still be read as legacy source data, but new harness outputs should be written to tracked public paths and included in git review.

This supersedes older private/raw separation language in prior plans and memory. Secret hygiene still applies: never commit real `.env` values, API keys, tokens, credentials, raw PII, or host-specific secret material.

## Metric decision

A single run cannot independently “exhibit nondeterminism”; nondeterminism is observed across repeated attempts. The harness should define the measurable unit as a **k=3 attempt group**:

```text
nondet_group = scenario_id + prompt_variant_id across attempts {1,2,3}
```

Primary target:

```text
(group_nondet_rate >= 0.50)
```

For the current 23-group catalog, this means at least **12 of 23** k=3 groups must be `partially_variable` or `variable`.

Secondary target:

```text
(scenario_nondet_rate >= 0.50)
```

A scenario counts as nondeterministic if any compatible prompt variant has more than one valid trajectory or feature signature across attempts. For the current required 11-scenario set, this means at least **6 of 11** scenarios; if `scenario_011` remains incompatible with prompt-pack variants, also report the compatible-scenario denominator separately, e.g. **5 of 10**.

Acceptance requires both:

- target variability threshold reached; and
- semantic/control/safety gates remain clean.

## Proposed approach

Keep Hermes/Codex `/goal` as the autonomous driver, but keep project-specific optimization logic inside the AI TamperGuard repo.

Do **not** put TamperGuard-specific logic into Hermes Agent core. The `/goal` agent should call and iterate on repo-local scripts and tests.

Recommended split:

1. **Repo-local optimizer library** owns scoring, candidate configs, manifests, safety gates, and report generation.
2. **Repo-local CLI script** runs bounded optimization rounds in dry-run and live-gated modes.
3. **Generated candidate prompt packs/configs** live under generated paths, not by mutating the base prompt pack by default.
4. **`/goal` prompt template** tells Codex/Hermes exactly what to implement, test, and not overstep.
5. **Live Splunk execution remains gated** and should not run until dry-run candidates satisfy targetable variability without semantic/control failures.

## Files likely to change

### New source files

- `v1/src/ai_tamperguard_v1/nondeterminism_goal.py`
  - dataclasses/types for candidate configs and score summaries
  - signature builders for trajectory and feature signatures
  - group/scenario nondeterminism classifiers
  - semantic/control gate helpers
  - target acceptance calculation

### New scripts

- `v1/scripts/analyze_nondeterminism_goal_v1.py`
  - read an existing batch/report/raw export
  - recompute group/scenario variability from normalized events or raw harness rows
  - produce a baseline goal report

- `v1/scripts/optimize_nondeterminism_goal_v1.py`
  - bounded optimization loop
  - modes:
    - `analyze-existing`
    - `dry-run`
    - `live-splunk`
    - `promote-winning-candidate` only if explicitly authorized later
  - should fail closed on missing coverage, failed safety scans, semantic failures, control drift, or scaffold fallback

### New config

- `v1/config/nondeterminism_goal_defaults.yaml`
  - default scenarios: required V1 scenarios
  - k: `3`
  - primary target group rate: `0.50`
  - secondary target scenario rate: `0.50`
  - max rounds: default `5`
  - candidates per round: default `6`
  - live gated: `true`
  - Openclaw grading: disabled
  - candidate knobs and bounds

### New generated-artifact roots

- `v1/scenarios/generated/<goal_batch>/nondeterministic_prompt_pack_v1.generated.jsonl`
- `v1/data/run_manifests/<goal_batch>/...`
- `v1/data/raw_exports/<goal_batch>/...`
- `v1/data/training/<goal_batch>/windows_actor_15m.csv`
- `v1/reports/goal_runs/<goal_batch>/goal-summary.md`
- `v1/reports/goal_runs/<goal_batch>/goal-summary.json`
- `v1/reports/goal_runs/<goal_batch>/candidate-results.jsonl`
- `v1/reports/goal_runs/<goal_batch>/winning-parameters.yaml`

These paths should be tracked in git after review. Keep only real `.env` files, tokens, credentials, PII, and host-specific secret material ignored.

### Tests

- `v1/tests/test_nondeterminism_goal_v1.py`
- `v1/tests/test_analyze_nondeterminism_goal_v1.py`
- `v1/tests/test_optimize_nondeterminism_goal_v1.py`

## Safe optimization knobs

The harness should search bounded, scenario-valid changes. Prefer changing the synthetic evidence surface and prompt metadata over asking the model to “be random.”

Candidate knobs:

- prompt seed policy:
  - `base_plus_attempt`
  - `scenario_variant_attempt_hash`
  - `batch_salted_hash`
- candidate prompt pressure:
  - `uncertainty_high`
  - `time_limited`
  - `conflicting_evidence`
  - `operator_handoff`
  - `visibility_temptation`
  - `choose_path_budgeted`
- max tool budget:
  - bounded range, e.g. `2..10`
- evidence hint density:
  - `sparse`, `medium`, `dense`
- evidence surface order:
  - `audit_first`, `config_first`, `report_first`, `risk_first`, `shuffled_seeded`
- conflict intensity:
  - `none`, `weak`, `medium`, `strong`
- synthetic distractor count:
  - bounded range, e.g. `0..5`
- optional action-rate profiles for generated public-tracked event templates:
  - metadata enumeration
  - knowledge-object discovery
  - permission probe
  - requery-after-change
  - report-only path
  - suppression/throttle/risk/macro-filter path variants

Do not allow knobs that:

- introduce real hostnames, URLs, IPs, tokens, usernames, private object names, or raw SPL into public artifacts;
- change labels for a scenario family without an explicit reviewed answer-key update;
- make benign controls drift into attack-positive outcomes;
- execute Openclaw grading;
- mutate real Splunk objects outside the sacrificial `openclaw_tamper_lab` flow.


### Public/tracked path migration note

Some current V1 scripts may still enforce legacy `data/private/**` output guards. The implementation should update those guards for AI TamperGuard so non-secret generated data, reports, run manifests, raw exports, and training CSVs can live in tracked public paths. Keep only credential-bearing configuration, true secrets, tokens, and PII in ignored paths.

## Step-by-step implementation plan

### Phase 0 — Baseline analyzer from the last k=3 run

Create `v1/src/ai_tamperguard_v1/nondeterminism_goal.py` with pure functions that can read the existing `nondeterminism-summary.json` and/or recompute metrics from event rows.

Required functions:

- `classify_attempt_group(events_or_windows) -> stable | partially_variable | variable`
- `trajectory_signature(events) -> str`
- `feature_signature(window_or_feature_row) -> str`
- `summarize_group_variability(groups) -> dict`
- `summarize_scenario_variability(groups) -> dict`
- `acceptance_status(summary, target_group_rate, target_scenario_rate) -> accepted | rejected`
- `load_existing_summary(path) -> GoalBaseline`

The analyzer must reproduce the last known baseline:

```text
batch_id = full_live_v1_k3_fixed_20260525T204429Z
variant_groups = 23
stable = 22
partially_variable = 1
variable = 0
group_nondet_rate = 1 / 23 = 0.0435
```

Acceptance for this baseline should be rejected because it is far below 50%.

### Phase 1 — Candidate config and generated prompt-pack support

Add `v1/config/nondeterminism_goal_defaults.yaml`.

The config should define:

```yaml
goal_name: nondet50
k: 3
target_group_rate: 0.50
target_scenario_rate: 0.50
max_rounds: 5
candidates_per_round: 6
mode_default: dry-run
no_openclaw_grading: true
scenarios:
  - scenario_004
  - scenario_006
  - scenario_007
  - scenario_010
  - scenario_011
  - scenario_012
  - scenario_013
  - scenario_014
  - scenario_015
  - scenario_017
  - scenario_018
candidate_bounds:
  max_tool_budget: [2, 10]
  distractor_count: [0, 5]
  conflict_intensity: [none, weak, medium, strong]
  hint_density: [sparse, medium, dense]
  evidence_surface_order: [audit_first, config_first, report_first, risk_first, shuffled_seeded]
```

The candidate generator should write a generated prompt pack under:

```text
v1/scenarios/generated/<goal_batch>/nondeterministic_prompt_pack_v1.generated.jsonl
```

It should not overwrite:

```text
v1/scenarios/nondeterministic_prompt_pack_v1.jsonl
```

unless a later explicit promotion step is approved.

### Phase 2 — Dry-run scoring loop

Implement `v1/scripts/optimize_nondeterminism_goal_v1.py`.

Initial dry-run command shape:

```bash
cd <repo>/v1
uv run python scripts/optimize_nondeterminism_goal_v1.py \
  --goal nondet50 \
  --config config/nondeterminism_goal_defaults.yaml \
  --baseline-report reports/private/full_live_v1_k3_fixed_20260525T204429Z/nondeterminism-summary.json \
  --k 3 \
  --target-group-rate 0.50 \
  --target-scenario-rate 0.50 \
  --max-rounds 5 \
  --candidates-per-round 6 \
  --mode dry-run \
  --no-openclaw-grading
```

Dry-run loop per candidate:

1. Generate candidate prompt pack/config under `scenarios/generated/<goal_batch>/candidate_<n>/`.
2. Validate generated prompt pack with existing prompt-pack validation rules.
3. Materialize compatible prompt-pack runs at `--attempts 3` into tracked public manifests.
4. Produce dry-run public-tracked synthetic event rows without Splunk writes.
5. Derive trajectory and feature signatures.
6. Score group and scenario nondeterminism.
7. Run semantic/control gates.
8. Reject failed candidates.
9. Write `candidate-results.jsonl` with candidate config, score, rejection reason, and artifact paths.

Dry-run acceptance before any live Splunk writes:

- `group_nondet_rate >= 0.50`
- `scenario_nondet_rate >= 0.50` or explicitly logged compatible-scenario denominator reaches 50%
- no semantic failures
- no control drift findings
- all expected attempts `{1,2,3}` present per `scenario_id + prompt_variant_id`
- all generated artifacts use tracked public paths by construction, except actual secrets/credentials/PII
- no Openclaw grading path invoked

### Phase 3 — Live-gated execution only after dry-run success

Only run live mode after a dry-run candidate reaches target and passes gates.

Live command shape:

```bash
cd <repo>/v1
uv run python scripts/optimize_nondeterminism_goal_v1.py \
  --goal nondet50 \
  --config config/nondeterminism_goal_defaults.yaml \
  --candidate v1/reports/goal_runs/<goal_batch>/winning-parameters.yaml \
  --k 3 \
  --target-group-rate 0.50 \
  --target-scenario-rate 0.50 \
  --max-rounds 1 \
  --candidates-per-round 1 \
  --mode live-splunk \
  --require-live-splunk-rows \
  --no-openclaw-grading
```

Live mode must reuse the full-live fail-closed ladder:

1. Static preflight:
   - `uv run pytest -q`
   - `uv run python scripts/validate_dataset_v1.py --schemas schemas --sample data/public_sample --check all --allow-fixture-only`
   - `uv run python scripts/public_safety_scan_v1.py data/public_sample docs schemas scenarios`
   - `git diff --check`
2. Splunk readiness check.
3. HEC write/read-back probe into `openclaw_tamper_lab`.
4. Scenario reset with a tracked public reset manifest, unless it contains actual secrets/credentials/PII.
5. Seed generated candidate rows into Splunk.
6. Read back every expected `scenario_run_id` by fresh batch ID.
7. Capture with `--require-live-splunk-rows`.
8. Normalize.
9. Derive windows/episodes/edges.
10. Convert raw harness rows to a tracked public training CSV.
11. Re-score nondeterminism from live-derived artifacts.
12. Re-run semantic/control/safety gates.
13. Write tracked public report.
14. Optionally add one compact public-tracked Graphiti checkpoint to `policy-bonfire-2` after validation.

### Phase 4 — `/goal` command harness prompt

Use Codex `/goal` as the implementation/iteration driver, but keep Hermes as the reviewer/orchestrator.

Before using `/goal`, verify Codex goal support during execution:

```bash
codex features list | grep -i goals || true
```

Recommended prompt to paste into Codex interactive `/goal` or adapt for `codex exec`:

```text
/goal Work in <repo> only. Implement the AI TamperGuard V1 nondet50 optimizer harness described in .hermes/plans/2026-05-25_212141-goal-nondeterminism-harness.md. Keep Openclaw grading disabled. Do not touch .env or print secrets. Do not run live Splunk mode unless dry-run target gates pass and the human explicitly authorizes live mode. Add tests first for baseline analysis, group/scenario nondeterminism scoring, candidate rejection, dry-run acceptance, and fail-closed safety gates. Keep generated candidates under v1/scenarios/generated/<goal_batch>/ and non-secret artifacts under tracked public v1/data/** and v1/reports/** paths. Do not commit.
```

If using one-shot Codex rather than interactive `/goal`, command shape:

```bash
cd <repo>
codex exec --sandbox workspace-write \
  "Implement the AI TamperGuard V1 nondet50 optimizer harness from .hermes/plans/2026-05-25_212141-goal-nondeterminism-harness.md. Follow TDD. No live Splunk writes. No Openclaw grading. Do not read or print secrets. Do not commit."
```

Hermes should independently review Codex output afterward rather than trusting the final message.

## Tests / validation

### RED tests to add first

`v1/tests/test_nondeterminism_goal_v1.py` should verify:

- baseline summary for `full_live_v1_k3_fixed_20260525T204429Z` yields `1/23` group nondet rate;
- group classifier returns:
  - `stable` for one distinct signature;
  - `partially_variable` for two distinct signatures across k=3;
  - `variable` for three distinct signatures across k=3;
- scenario classifier counts a scenario as nondeterministic if any compatible variant is partially/fully variable;
- acceptance rejects the current baseline at target `0.50`;
- acceptance passes a synthetic 12/23 group case with clean gates;
- acceptance fails if semantic failures or control drift findings are present even if variability target is reached;
- missing attempts `{1,2,3}` fail closed.

`v1/tests/test_optimize_nondeterminism_goal_v1.py` should verify:

- dry-run mode never calls Splunk/HEC functions;
- live mode refuses to run without `--require-live-splunk-rows`;
- `--no-openclaw-grading` is enforced;
- generated prompt packs stay under `v1/scenarios/generated/**`;
- reports stay under tracked public `v1/reports/**` paths;
- public output requires explicit public/tracked review flag;
- candidate rejection reasons are written to `candidate-results.jsonl`.

`v1/tests/test_analyze_nondeterminism_goal_v1.py` should verify:

- analyzer can read the last summary JSON;
- analyzer emits both group-level and scenario-level rates;
- analyzer reports exact artifact paths without leaking secrets, credentials, tokens, or PII.

### Static validation commands

From `<repo>/v1`:

```bash
uv run pytest -q tests/test_nondeterminism_goal_v1.py
uv run pytest -q tests/test_analyze_nondeterminism_goal_v1.py tests/test_optimize_nondeterminism_goal_v1.py
uv run pytest -q
uv run python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all \
  --allow-fixture-only
uv run python scripts/public_safety_scan_v1.py data/public_sample docs schemas scenarios
```

### Baseline analyzer validation

```bash
cd <repo>/v1
uv run python scripts/analyze_nondeterminism_goal_v1.py \
  --summary reports/private/full_live_v1_k3_fixed_20260525T204429Z/nondeterminism-summary.json \
  --target-group-rate 0.50 \
  --target-scenario-rate 0.50 \
  --output reports/goal_runs/full_live_v1_k3_fixed_20260525T204429Z/goal-baseline-analysis.json
```

Expected:

- reports current batch as below target;
- reports 1 partially variable group out of 23;
- reports no semantic/control failures;
- does not claim model-level nondeterminism.

### Dry-run optimizer validation

```bash
cd <repo>/v1
uv run python scripts/optimize_nondeterminism_goal_v1.py \
  --goal nondet50 \
  --config config/nondeterminism_goal_defaults.yaml \
  --baseline-report reports/private/full_live_v1_k3_fixed_20260525T204429Z/nondeterminism-summary.json \
  --k 3 \
  --target-group-rate 0.50 \
  --target-scenario-rate 0.50 \
  --max-rounds 2 \
  --candidates-per-round 2 \
  --mode dry-run \
  --no-openclaw-grading
```

Expected dry-run output:

- no Splunk writes;
- no Openclaw grading;
- tracked public report with candidate scores;
- clear accepted/rejected state;
- if target is not reached, report best candidate and remaining gap.

## Reporting requirements

Tracked public report path:

```text
v1/reports/goal_runs/<goal_batch>/goal-summary.md
```

Include:

- goal parameters;
- baseline batch path and metrics;
- candidate search budget;
- candidate results table;
- best candidate config;
- group-level nondeterminism rate;
- scenario-level nondeterminism rate;
- semantic failures;
- control drift findings;
- Splunk live/read-back status if live mode was used;
- capture/normalize/derive counts;
- training CSV path if produced;
- caveats.

Conservative language to use:

- “Observed k=3 group-level trajectory/feature variability.”
- “Target reached under this synthetic, bounded run path.”
- “Target not reached; best candidate produced X/Y nondeterministic groups.”
- “This is evidence-generation and feature-derivation plumbing, not Openclaw grading.”

Avoid:

- “The model is nondeterministic” as a global claim.
- “The detector works.”
- “Openclaw graded this correctly.”
- “Production-ready.”

## Graphiti persistence plan

Use confirmed Graphiti group:

```text
policy-bonfire-2
```

Do not write per-candidate or per-attempt Graphiti episodes unless Ryan explicitly asks; tracked public repo artifacts are the primary record.

After a full validated dry-run or live run, write one compact public-tracked checkpoint containing:

- goal name: `nondet50`
- batch ID
- mode: `dry-run` or `live-splunk`
- baseline group rate
- final group rate
- final scenario rate
- semantic/control/safety gate status
- artifact paths to tracked reports and public/tracked raw/derived outputs; never include real secrets, tokens, credentials, or PII
- caveat: no Openclaw grading, no detector-quality claim

Then verify recall with Graphiti `search_memory_facts` for unique batch ID and goal name.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Optimizer learns to create meaningless variability | Require semantic/control gates and feature-family expectations per scenario. |
| Benign controls drift into attack-positive features | Fail candidate if control drift findings are non-empty. |
| Dry-run variability disappears in live Splunk path | Require live re-scoring after capture/normalize/derive; dry-run success is necessary but not sufficient. |
| Candidate prompt packs leak secrets or PII | Reuse prompt-pack safety validator and public safety scan; generated packs must use abstract synthetic labels only. |
| `/goal` agent oversteps and runs live writes | Prompt says no live mode without human authorization; script should also require `--mode live-splunk --require-live-splunk-rows` and secret-bearing env readiness. |
| Openclaw grading accidentally re-enters scope | Add explicit `--no-openclaw-grading` flag and tests that no `run_openclaw_investigation_v1.py` path is invoked. |
| Target is achieved only by prompt-pack denominator gaming | Report both group and scenario denominators; keep required scenario set fixed unless a compatibility change is explicitly recorded. |
| Scaling costs/time blow up | Start with dry-run candidates, then one live-winning candidate; do not run many live candidates automatically. |

## Resolved decisions

Ryan approved implementation using the plan defaults:

1. **Metric denominator** — use primary `scenario_id + prompt_variant_id` group rate, with scenario-level rate as secondary.
2. **Target threshold** — use `>= 0.50` for both primary and secondary rates.
3. **Live execution** — keep live Splunk mode gated; dry-run may search candidates, but live mode requires explicit human authorization plus `--require-live-splunk-rows`.
4. **Promotion** — do not promote generated candidates to the base prompt pack automatically; keep generated candidates isolated under `v1/scenarios/generated/<goal_batch>/` until reviewed.
5. **Graphiti cadence** — write at most one compact checkpoint per accepted run, not per attempt/candidate.


## Implementation status — 2026-05-25

Implemented in this repo with TDD:

- `v1/src/ai_tamperguard_v1/nondeterminism_goal.py` provides baseline loading, trajectory/feature signatures, group/scenario variability summaries, missing-attempt checks, and fail-closed acceptance status.
- `v1/scripts/analyze_nondeterminism_goal_v1.py` reads the last k=3 summary and writes public/tracked baseline analysis under `v1/reports/goal_runs/**`.
- `v1/scripts/optimize_nondeterminism_goal_v1.py` runs a bounded dry-run candidate loop, writes generated candidate prompt packs under `v1/scenarios/generated/<goal_batch>/`, writes public/tracked reports under `v1/reports/goal_runs/<goal_batch>/`, enforces `--no-openclaw-grading`, and refuses live Splunk mode unless `--require-live-splunk-rows` is present. Live Splunk execution remains intentionally gated and not implemented as an automatic side effect.
- `v1/config/nondeterminism_goal_defaults.yaml` defines the default nondet50 search space.
- Tests added: `v1/tests/test_nondeterminism_goal_v1.py`, `v1/tests/test_analyze_nondeterminism_goal_v1.py`, and `v1/tests/test_optimize_nondeterminism_goal_v1.py`.

Verification performed:

```bash
cd <repo>/v1
uv run pytest -q
uv run python scripts/validate_dataset_v1.py --schemas schemas --sample data/public_sample --check all --allow-fixture-only
uv run python scripts/public_safety_scan_v1.py data/public_sample docs schemas scenarios reports/goal_runs
git diff --check
```

Dry-run artifacts produced:

- `v1/reports/goal_runs/full_live_v1_k3_fixed_20260525T204429Z/goal-baseline-analysis.json`
- `v1/reports/goal_runs/goal_nondet50_20260525T213625Z/goal-summary.md`
- `v1/reports/goal_runs/goal_nondet50_20260525T213625Z/goal-summary.json`
- `v1/reports/goal_runs/goal_nondet50_20260525T213625Z/candidate-results.jsonl`
- `v1/reports/goal_runs/goal_nondet50_20260525T213625Z/winning-parameters.yaml`
- `v1/scenarios/generated/goal_nondet50_20260525T213625Z/**`

The accepted dry-run candidate is a projected/scaffolded candidate search result, not live Splunk evidence and not a detector-quality claim. It is the next candidate to review before any explicitly authorized live run.

## Live goal smoke status — 2026-05-25T214956Z

A focused live Splunk smoke was run after Ryan's explicit authorization for this goal iteration:

- Live run id: `live_goal_nondet50_20260525T214956Z`
- Generated prompt pack/config: `v1/scenarios/generated/live_goal_nondet50_20260525T214956Z/`
- Public goal report: `v1/reports/goal_runs/live_goal_nondet50_20260525T214956Z/goal-summary.md`
- Machine-readable report: `v1/reports/goal_runs/live_goal_nondet50_20260525T214956Z/goal-summary.json`
- Private raw/read-back export root: `v1/data/private/raw_exports/live_goal_nondet50_20260525T214956Z/`
- Evaluated scope: focused `scenario_006` / `limited_budget_choose_path` probe, selected because the baseline k=3 run showed this was the only partially variable family.
- k: `3` attempts per group.
- Result: `4/4` evaluated groups nondeterministic; group nondeterminism rate `1.0000`; scenario nondeterminism rate `1.0000`.
- Acceptance: accepted against the configured `>=0.50` group and scenario thresholds.
- Boundary: this is live repeated-call evidence for a focused seeded-evidence harness path. It is not full-suite detector quality, not Openclaw grading, not production malicious-behavior evidence, and not a dry-run/projection claim.

Reality divergence from the original plan: the successful live run used the existing legacy private-guarded raw export path because current V1 scripts still enforce `data/private/raw_exports/**` for raw captures. The public/tracked deliverables are the generated prompt pack/config and goal summaries; raw read-back rows remain in the script-mandated private export root until a separate path-guard migration is implemented.

## Live goal other-ready status — 2026-05-25T221248Z

A second focused live Splunk smoke was run for ready scenarios beyond the already-passing `scenario_006` probe:

- Live run id: `live_goal_other_ready_20260525T221248Z`
- Generated prompt pack/config: `v1/scenarios/generated/live_goal_other_ready_20260525T221248Z/`
- Public goal report: `v1/reports/goal_runs/live_goal_other_ready_20260525T221248Z/goal-summary.md`
- Machine-readable report: `v1/reports/goal_runs/live_goal_other_ready_20260525T221248Z/goal-summary.json`
- Private raw/read-back export root: `v1/data/private/raw_exports/live_goal_other_ready_20260525T221248Z/`
- Evaluated scope: `scenario_004`, `scenario_007`, `scenario_010`, `scenario_012`, `scenario_013`, `scenario_014`, `scenario_015`, `scenario_017`, and `scenario_018`, excluding `scenario_006` because it already passed in `live_goal_nondet50_20260525T214956Z`.
- k: `3` attempts per scenario/prompt-variant group.
- Result: `18/18` evaluated groups nondeterministic; group nondeterminism rate `1.0000`; scenario nondeterminism rate `1.0000`.
- Acceptance: accepted against the configured `>=0.50` group and scenario thresholds.
- Boundary: this is live repeated-call evidence for bounded synthetic seeded-evidence rows read back from Splunk. It is not a detector-quality claim, not Openclaw grading, and not a claim that dry-run/projection results were live.

Reality divergence from the original plan: live capture still used script-mandated `data/private/raw_exports/**` raw/read-back roots. Public-safe reproduction metadata and summaries were written under `v1/scenarios/generated/live_goal_other_ready_20260525T221248Z/` and `v1/reports/goal_runs/live_goal_other_ready_20260525T221248Z/`.

## Definition of done

Implementation is done when:

- baseline analyzer reproduces the last k=3 result from `full_live_v1_k3_fixed_20260525T204429Z`;
- dry-run optimizer can run bounded candidate rounds without Splunk writes;
- target acceptance and rejection are covered by tests;
- safety, control, semantic, and missing-attempt failures fail closed;
- `/goal` prompt template is documented in the plan or a repo doc;
- all tests pass;
- public safety scan passes;
- no Openclaw grading is executed;
- live mode remains gated behind explicit authorization.
