# AI TamperGuard V1 full-live k3 fixed nondeterminism summary

## Run identity

- Batch ID: `full_live_v1_k3_fixed_20260525T204429Z`
- Scope: required V1 scenarios plus compatible nondeterministic prompt-pack variants at `attempts=3` after nondeterminism seed fix.
- Explicit boundary: **no Openclaw grading was performed**. This is evidence plumbing, data generation, feature derivation, and nondeterminism analysis only.

## Counts

- Required scenarios represented: 11
- Scenario runs: 80
- Nondeterministic variant groups: 23
- Splunk-verified public-safe events: 315
- Normalized events: 315
- 15m behavior windows: 80
- Episodes: 80
- Edges: 315
- Private training CSV: `data/private/training/full_live_v1_k3_fixed_20260525T204429Z/windows_actor_15m.csv`

## Scenario counts

|scenario|runs|verified events|
|---|---:|---:|
|scenario_004|7|21|
|scenario_006|16|71|
|scenario_007|7|14|
|scenario_010|13|52|
|scenario_011|1|5|
|scenario_012|10|40|
|scenario_013|10|40|
|scenario_014|4|16|
|scenario_015|4|20|
|scenario_017|4|20|
|scenario_018|4|16|

## Nondeterminism result

|classification|trajectory groups|feature groups|
|---|---:|---:|
|stable|22|22|
|partially_variable|1|1|
|variable|0|0|

- Fix effect observed: `True`.
- Semantics stable despite trajectory variability where observed.

## Gates executed

- Preflight tests, public fixture validation, public safety scan, and diff whitespace gates passed before live writes.
- Nondeterminism-fix dry-run precheck passed: `scenario_006 + limited_budget_choose_path_v1_a` produced at least two signatures across attempts.
- Splunk readiness passed for required lab surfaces.
- HEC probe read back 3 rows for `scenario_004_run_900`.
- Full k3 seeding/read-back: 80 scenario runs, 315 events read back from `openclaw_tamper_lab` by fresh batch ID; probe excluded from verified export.
- Capture: live verified rows only; no scaffold fallback.
- Normalization/derivation: 315 normalized events, 80 windows, 80 episodes, 315 edges.

## Caveats

- This is small-k synthetic seeded evidence, not formal reliability estimation.
- This reports observed trajectory/feature variability in this run path, not global model nondeterminism.
- The full-live sample remains private and is not promoted to public sample or release-candidate status.
- No production detector, model-quality, or Openclaw grading claims are made.
