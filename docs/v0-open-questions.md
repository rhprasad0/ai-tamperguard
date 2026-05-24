# AI TamperGuard v0 Open Questions

These are the decisions we need to answer before implementing the v0 smoke test.

v0 is deliberately modest: use legitimate logs from an authorized existing Splunk install, train locally, and deploy/infer inside Splunk. No uncensored agent is required for this phase.

## Resolved decisions

These answers are now fixed for v0 unless we explicitly revise them later.

1. **Hardware split:** Training runs on the GPU rig. Splunk runs on a thin client without a GPU.
2. **Keep Splunk on the thin client for v0:** Do not migrate Splunk to the GPU rig unless the thin client becomes an empirical blocker. The thin client is useful because it proves the deployed model can run in a realistic CPU-only Splunk environment.
3. **Inference constraint:** Splunk-side inference must be CPU-safe and lightweight. Do not require GPU inference inside Splunk.
4. **Splunk version:** The current thin-client Splunk install is Splunk Enterprise `10.2.3`, build `4d61cf8a5c0c`, on Linux `x86_64`. License state was verified as `OK` during v0 planning.
5. **No Splunk ML app installed yet:** The current Splunk instance does not have Splunk AI Toolkit or MLTK installed. MCP app inventory confirmed no matching ML/AI/ONNX apps are present.
6. **Capabilities posture:** The local/admin Splunk context should have the capabilities needed for the chosen deployment path, including lookup upload/update for no-ML-app scoring and, if AI Toolkit is installed later, ONNX upload permissions. Recheck exact capabilities after the deployment app path is chosen.
7. **Splunk app namespace:** Model artifacts, lookups, saved searches, and v0 searches should live under the AI TamperGuard app namespace, using a Splunk-safe app id such as `ai_tamperguard`.
8. **v0 model shape:** Prefer small tabular models that can run cheaply on CPU, such as logistic regression or random forest. Avoid any model that needs GPU serving for v0.
9. **Deployment implication:** Local training may use the GPU rig, but the exported/deployed model must be practical for the Splunk thin client. Because no Splunk ML app is installed yet, true Splunk-side model execution requires either installing AI Toolkit/MLTK or using a simpler no-ML-app bridge such as lookup-based scoring or scripted packaging.
10. **Scope:** v0 remains a smoke test of training locally and deploying/inferencing in Splunk using legitimate logs. The uncensored-agent harness is out of scope for v0.
11. **Deployment operation model:** Hermes should operate model deployment through the Splunk MCP server so Ryan does not need to manually upload artifacts through the Splunk UI. Current MCP read/search is working, but an `outputlookup` deployment probe was blocked by the MCP server's command safeguards, so v0 needs either a narrow MCP deployment capability or a deliberately allowed lookup-write path before artifact deployment is fully hands-off.
12. **Modeling goal:** v0 is only trying to produce a working end-to-end model pipeline, not prove that the labels or features represent a production-quality tamper detector. Labels and features may be weak, synthetic, or heuristic as long as they exercise extraction, training, deployment, scoring, and validation.

## Highest-priority decisions

Answer these next so implementation can start without wandering into the swamp wearing flip-flops.

1. **Deployment path:** With no AI Toolkit or MLTK installed, should v0 install a Splunk ML app, or should the first pass use no-ML-app scoring such as lookup-based coefficients / scripted inference?
2. **Window size:** Should the first pass use `actor_60m`, `actor_15m`, session windows, or multiple window types?
3. **Public sample data:** Should public examples be fully synthetic rows matching the private schema, even if private training uses legitimate local logs?

## Splunk environment

1. Which Splunk version is installed?
   - Resolved for current thin-client lab: Splunk Enterprise `10.2.3`, build `4d61cf8a5c0c`, Linux `x86_64`, license state `OK`.
2. Which Splunk AI Toolkit / MLTK version is installed?
   - Resolved for current thin-client lab: neither Splunk AI Toolkit nor MLTK is installed.
3. Is ONNX upload available and enabled?
   - Resolved for current thin-client lab: no. ONNX upload is not available until an appropriate Splunk AI/ML app is installed and enabled.
4. Does the local user/app context have the capabilities required for ONNX upload and inference?
   - Resolved directionally: the local/admin context should have the required capabilities for the chosen path. For no-ML-app scoring, confirm lookup upload/update permissions. If AI Toolkit is installed later, confirm ONNX-specific upload permissions such as `upload_onnx_model_file` in addition to lookup upload capability.
5. If ONNX is unavailable, is classic MLTK `fit` / `apply` available?
   - Resolved for current thin-client lab: no. Classic MLTK commands are unavailable until MLTK is installed.
6. Which app namespace should own the model?
   - Resolved: use the AI TamperGuard app namespace, with a Splunk-safe app id such as `ai_tamperguard`.
7. Is model deployment expected to happen through the Splunk UI, app filesystem packaging, REST API, or search commands?
   - Resolved directionally: Hermes should drive deployment using the Splunk MCP server, not manual Splunk UI handling by Ryan.
   - Current implementation note: the existing MCP toolset can inspect/query Splunk, but a harmless `outputlookup` deployment probe was blocked as a forbidden command. Before full hands-off deployment, add or enable a narrow MCP-safe write path for AI TamperGuard artifacts, such as a constrained lookup/model-artifact deployment tool scoped to the `ai_tamperguard` app.
   - Fallback if needed: Hermes may use Splunk REST or app filesystem packaging for the actual write while still using Splunk MCP for validation, but the preferred v0 operator interface remains Hermes + Splunk MCP.

## Data access and export

1. Which indexes and sourcetypes are safe to query for v0?
   - Resolved first-pass private source set, discovered through Splunk MCP metadata/stats searches:
     - `index=_audit sourcetype=audittrail` for auth/session, search, saved-search, role/capability, token, index/input, and REST/control-plane activity.
     - `index=_configtracker sourcetype=splunk_configuration_change` for config/admin/knowledge-object change activity.
   - Optional private context sources, not first-pass training defaults:
     - `index=_internal` for Splunk/MCP operational health and troubleshooting only.
     - `index=agentops` and `index=openclaw_tamper_lab` for synthetic/experiment validation only, not legitimate private baseline training unless explicitly separated.
   - Do not use endpoint/router/general LAN telemetry as v0 training input unless a later question explicitly expands scope beyond Splunk control-plane behavior.
2. What do we need to grab to train a working model?
   - Resolved reframing: v0 does not need to prove that specific log-event categories are inherently useful. The goal is a working end-to-end model pipeline, so the export should grab the minimum fields needed to build behavior-window rows.
   - Minimum required ingredients:
     - stable timestamp for windowing
     - actor or actor surrogate for grouping
     - action/status/category fields that can become counts or booleans
     - object/app/interface fields only after normalization into low-cardinality categories
     - enough activity volume to create train/holdout windows
     - a weak/manual label source or heuristic label proxy
   - Treat raw log events as private evidence, not as the modeling artifact. The modeling artifact is the window table.
   - Internal operational events remain troubleshooting/context only unless needed to prove pipeline health.
3. Which fields identify actor/user, action, object, interface, status, and request/session IDs?
   - Resolved first pass: use normalized fields derived from `_audit` and `_configtracker`, not raw private values.
   - Candidate private evidence fields include user/actor, action, info/status, object, search text presence, REST/control endpoint, config action, changed property names, app context, and time.
   - Training features should be aggregated counts/booleans/categories per window, not raw usernames, raw SPL, URLs, object paths, hostnames, tokens, or session IDs.
4. Can we export enough legitimate activity to create at least a few hundred behavior windows?
   - Likely yes for a smoke test: MCP inventory found tens of thousands of `_audit` events and hundreds of `_configtracker` events in the current lab window. Final sufficiency should be verified after the exact actor/time-window aggregation is implemented.
5. What time range should v0 use?
   - Resolved default: start with the last 30 days available in the lab, then narrow if volume or private-review burden is too high.
6. Which raw fields must never leave the private machine?
   - Raw `_raw`, usernames, hostnames, IPs, Splunk URLs, REST paths containing local object names, raw SPL/search strings, saved-search names, object paths, session IDs, tokens, credential names/values, internal file paths, and private app/index/source details.
7. Should raw private exports live under `data/private/`, outside the repo entirely, or both with `.gitignore` protection?
   - Resolved default: keep raw private exports outside the public repo when possible. If local project-relative staging is needed, use ignored private paths such as `data/private/` and never commit them.
8. Do we need a repeatable SPL export query checked into the repo with sensitive values parameterized?
   - Yes. Check in parameterized SPL templates and feature-schema scripts only. Keep private concrete queries, raw exports, and reviewed evidence rows out of the public repo unless explicitly sanitized.

## Labeling

1. Should v0 use weak heuristic labels, manual labels, or both?
   - Resolved for the working-model pass: use weak heuristic labels first, with optional manual spot-checks only to sanity-check the pipeline. Do not block v0 on a defensible detection label taxonomy.
2. What is the first v0 definition of `label_binary = 1`?
   - Resolved for the working-model pass: `1` means `working_model_positive_proxy`, not confirmed malicious behavior.
   - A valid proxy can be any deterministic rule that creates separable classes from the private window table, such as admin/config-heavy windows, unusual action/status concentration, or synthetic/held-out positive examples.
   - The label exists to prove that the model can learn, score, deploy, and round-trip through Splunk. It is not a claim that the event was bad.
3. Should the public label language use `needs_review` everywhere to avoid implying malicious activity?
   - Yes. Public-facing language should use `needs_review` or `positive_proxy`, not `malicious`, `attack`, or `tamper` as ground truth.
4. Do we need separate labels for:
   - normal activity
   - admin/config activity
   - detection/search tuning
   - unusual activity
   - Not for v0. Keep one binary label plus optional private evidence fields. Additional label classes can wait until the pipeline works.
5. Who or what performs manual review for the first labeled sample?
   - Optional Hermes/Ryan spot-check only. Manual review should catch obvious nonsense, not become a required annotation workflow.
6. How do we mark uncertain labels?
   - Use a simple `label_confidence` or `label_source` field if needed, but the first model can proceed with a deterministic weak label.
7. Should labels be stored directly in the window CSV or in a separate annotation file?
   - For v0, store `label_binary`, `label_source`, and optional `label_confidence` directly in the private window table so training stays boring and reproducible. Separate annotation files can wait.

## Feature engineering

1. Which feature columns can be computed reliably from the available logs?
   - Resolved for the working-model pass: pick only fields that can be reliably computed into a stable behavior-window table. Prefer boring, always-present counts/booleans over clever features.
   - Minimum first-pass feature families:
     - event/action counts per actor window
     - distinct action/category count
     - failed/denied/status counts
     - search activity count or boolean
     - admin/config activity count or boolean
     - token/RBAC/capability/index/input related activity count or boolean when present
     - normalized low-cardinality app/interface/object category counts when present
     - off-hours/weekend or time-bucket booleans if easy
2. Which fields are too high-cardinality and need normalization or exclusion?
   - Exclude raw usernames, raw object names, saved-search names, raw SPL, URLs, session IDs, hostnames, paths, tokens, and other unique identifiers from model features.
   - Keep them only as private evidence fields when needed for debugging or manual spot-checking.
3. Should the first model use only numeric/boolean features?
   - Yes. Numeric/boolean-only is the safest v0 default because it supports logistic-regression scoring in plain SPL and avoids categorical preprocessing drama.
4. Should controlled categorical fields be included in v0 with one-hot encoding?
   - Only if they are already low-cardinality and stable. Otherwise defer. The first model should not depend on one-hot expansion to work.
5. How should missing fields be handled?
   - count fields default to `0`
   - boolean fields default to `0`
   - categorical fields default to `unknown`
6. Should raw usernames, object names, saved search names, raw SPL, URLs, and session IDs be excluded from model features and kept only in private evidence fields?
   - Yes. This is both a modeling simplification and a public-safety guardrail.
7. What minimum feature set is required for the first smoke test?
   - A compact numeric table is enough: `window_id`, private actor surrogate, window start/end, 8-20 `feature_*` count/boolean columns, `label_binary`, `label_source`, and optional evidence/debug columns kept private.
8. Should multiple window granularities be generated now, or only one?
   - Only one for the first working model. Use `actor_60m` unless a quick volume check shows it produces too few rows.

## Local training

1. Which local Python environment should own training dependencies?
2. Are these dependencies enough for v0?
   - `pandas`
   - `scikit-learn`
   - `onnx`
   - `skl2onnx`
   - `onnxruntime`
3. Which baseline model should be first?
   - logistic regression
   - random forest
   - gradient boosting
4. What metrics count as a passed smoke test?
   - accuracy
   - precision
   - recall
   - f1
   - confusion matrix
   - classification report
5. Should metrics be treated only as plumbing diagnostics because labels are weak?
6. Should private-trained model artifacts be committed, stored locally only, or regenerated on demand?
7. Do we need a reproducible training script before any manual notebook work?

## Splunk deployment and inference

1. What model format should be the first deployment target?
   - ONNX
   - Splunk `.mlmodel`
   - both
2. How will the model be uploaded into Splunk?
3. What exact SPL will run inference against held-out windows?
4. Should held-out windows be loaded with `inputlookup` for v0?
5. Where should inference results go?
   - lookup
   - summary index
   - dashboard
   - local report only
6. How do we verify Splunk-side predictions match local expectations?
7. Do we need a Splunk dashboard for v0, or is an SPL transcript/report enough?
8. What does rollback/removal of the test model look like?

## Public safety and repo hygiene

1. What is the public/private artifact split?
2. Should public sample data be fully synthetic instead of redacted local examples?
3. What scan prevents these from entering the public repo?
   - raw Splunk URLs
   - hostnames
   - private IPs
   - usernames
   - tokens
   - internal paths
   - raw SPL containing sensitive environment details
4. Should `data/private/`, `models/private/`, and `reports/private/` be ignored by default?
5. Should model artifacts be excluded from git unless explicitly reviewed?
6. What README language keeps the claim honest: v0 proves training/deployment plumbing, not malicious tamper detection?
7. Do we need a `PUBLIC_SAFETY.md` or is a section in the v0 spec enough for now?

## Recommended defaults

Unless we decide otherwise, use these defaults:

```text
Deployment path: no Splunk ML app is installed yet; decide between installing AI Toolkit/MLTK vs no-ML-app lookup/scripted scoring
Deployment operator: Hermes via Splunk MCP; Ryan should not need to manually upload model artifacts
Current MCP blocker: generic `outputlookup` is blocked, so add/enable a narrow AI TamperGuard artifact-deploy write path before full deployment
Hardware split: train on GPU rig; deploy/infer on CPU-only Splunk thin client
Splunk app namespace: AI TamperGuard app (`ai_tamperguard`)
Capabilities: local/admin context should have lookup upload/update capability; recheck ONNX-specific capability only if AI Toolkit is installed later
Data source: private `_audit`/`audittrail` plus `_configtracker`/`splunk_configuration_change` Splunk control-plane logs
Window size: actor_60m for first pass
Positive label: working_model_positive_proxy / needs_review proxy, not malicious ground truth
Feature posture: boring numeric/boolean behavior-window features first; defer clever categories until the pipeline works
Public examples: synthetic-only rows matching the private schema
Model artifacts: do not commit private-trained models until reviewed
First model: logistic regression, then random forest
First result sink: local report plus Splunk lookup output
```

## Next-question order

If we want to resolve this efficiently, answer in this order:

1. Decide Splunk deployment prerequisite: install AI Toolkit/MLTK, or start with no-ML-app lookup/scripted scoring.
2. Pick the first window size.
3. Decide public sample data policy.
4. Decide whether to commit only scripts/specs or also reviewed synthetic sample rows.
