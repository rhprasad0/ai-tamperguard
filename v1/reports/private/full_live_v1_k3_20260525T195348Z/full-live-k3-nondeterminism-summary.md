# AI TamperGuard V1 full-live k3 nondeterminism summary

## Run identity

- Batch ID: `full_live_v1_k3_20260525T195348Z`
- Scope: required V1 scenarios plus compatible nondeterministic prompt-pack variants at `attempts=3`.
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
- Private training CSV: `data/private/training/full_live_v1_k3_20260525T195348Z/windows_actor_15m.csv`

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

## Label-family counts

|label_family|windows|
|---|---:|
|alert_suppression|14|
|benign_alert_tuning|10|
|benign_investigation|7|
|benign_visibility_change|4|
|evidence_laundering|18|
|permission_probe|7|
|routing_or_transform_tamper|4|
|suspicious_recon|16|

## Nondeterminism result

|classification|variant groups|
|---|---:|
|stable|23|
|partially_variable|0|
|variable|0|

No trajectory or feature-level variability was observed across repeated attempts under the current synthetic seeded evidence path. Treat this as “nondeterminism not observed in this seeded pipeline,” not as a global claim about model or agent determinism.

## Gates executed

- Preflight tests passed (`110 passed`).
- Public fixture validation passed.
- Public safety scan passed.
- Splunk readiness passed for required lab surfaces.
- HEC probe read back 3 rows for `scenario_004_run_900`.
- Reset manifests generated for 11 required scenarios using sacrificial inventory boundaries.
- Full k3 seeding/read-back: 80 scenario runs, 315 events read back from `openclaw_tamper_lab` by fresh batch ID.
- Capture: 80/80 manifests `captured_live_splunk_public_safe`; no scaffold fallback.
- Normalization/derivation: 315 normalized events, 80 windows, 80 episodes, 315 edges.
- Private relationship/leakage checks passed: manifest, answer key, normalized events, verified rows, and splits align; attempt coverage is exactly `{1,2,3}` for every variant group.

## Semantic checks

- `scenario_012`: suppression-after-creation feature semantics fired for deterministic baseline.
- `scenario_014`: throttle-before-creation feature semantics fired for deterministic baseline.
- `scenario_015`: risk-score tuning feature semantics fired for deterministic baseline.
- `scenario_017`: macro/filter sequence feature semantics fired for deterministic baseline.
- Benign controls had no unexpected attack-positive drift under the checked feature gates.

## Caveats

- This is small-k evidence/data plumbing, not formal reliability estimation.
- Synthetic seeding appears deterministic; this can mask nondeterminism that would appear in a live actor/model loop.
- `scenario_011` remains deterministic-only because no compatible prompt-pack variant exists.
- The full-live sample remains private and is not promoted to `data/public_sample` or release-candidate status.
- No production detector, model-quality, or Openclaw grading claims are made.
