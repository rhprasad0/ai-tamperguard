# AI TamperGuard v0 Open Questions

These are the decisions we need to answer before implementing the v0 smoke test.

v0 is deliberately modest: use legitimate logs from an authorized existing Splunk install, train locally, and deploy/infer inside Splunk. No uncensored agent is required for this phase.

## Highest-priority decisions

Answer these first so implementation can start without wandering into the swamp wearing flip-flops.

1. **Deployment path:** Should v0 target ONNX first, with MLTK `fit` / `apply` as fallback?
2. **Data source:** Which private Splunk indexes and sourcetypes are safe to use for v0 extraction?
3. **Positive label meaning:** What should `label_binary = 1` mean in v0?
   - `needs_review_unusual_activity`
   - `admin_or_config_activity`
   - `detection_control_activity`
   - manually reviewed activity
4. **Window size:** Should the first pass use `actor_60m`, `actor_15m`, session windows, or multiple window types?
5. **Public sample data:** Should public examples be fully synthetic rows matching the private schema, even if private training uses legitimate local logs?

## Splunk environment

1. Which Splunk version is installed?
2. Which Splunk AI Toolkit / MLTK version is installed?
3. Is ONNX upload available and enabled?
4. Does the local user/app context have the capabilities required for ONNX upload and inference?
5. If ONNX is unavailable, is classic MLTK `fit` / `apply` available?
6. Which app namespace should own the model?
   - new `ai_tamperguard` app
   - Search app
   - another existing local app
7. Is model deployment expected to happen through the Splunk UI, app filesystem packaging, REST API, or search commands?

## Data access and export

1. Which indexes and sourcetypes are safe to query for v0?
2. Which logs contain useful control-plane activity?
   - audit events
   - search activity
   - saved search activity
   - knowledge object changes
   - app/config/admin activity
   - internal operational events
3. Which fields identify actor/user, action, object, interface, status, and request/session IDs?
4. Can we export enough legitimate activity to create at least a few hundred behavior windows?
5. What time range should v0 use?
6. Which raw fields must never leave the private machine?
7. Should raw private exports live under `data/private/`, outside the repo entirely, or both with `.gitignore` protection?
8. Do we need a repeatable SPL export query checked into the repo with sensitive values parameterized?

## Labeling

1. Should v0 use weak heuristic labels, manual labels, or both?
2. What is the first v0 definition of `label_binary = 1`?
3. Should the public label language use `needs_review` everywhere to avoid implying malicious activity?
4. Do we need separate labels for:
   - normal activity
   - admin/config activity
   - detection/search tuning
   - unusual activity
5. Who or what performs manual review for the first labeled sample?
6. How do we mark uncertain labels?
7. Should labels be stored directly in the window CSV or in a separate annotation file?

## Feature engineering

1. Which feature columns can be computed reliably from the available logs?
2. Which fields are too high-cardinality and need normalization or exclusion?
3. Should the first model use only numeric/boolean features?
4. Should controlled categorical fields be included in v0 with one-hot encoding?
5. How should missing fields be handled?
   - count fields default to `0`
   - boolean fields default to `0`
   - categorical fields default to `unknown`
6. Should raw usernames, object names, saved search names, raw SPL, URLs, and session IDs be excluded from model features and kept only in private evidence fields?
7. What minimum feature set is required for the first smoke test?
8. Should multiple window granularities be generated now, or only one?

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
Deployment path: ONNX first, MLTK fallback
Data source: private legitimate Splunk audit/control-plane logs
Window size: actor_60m for first pass
Positive label: needs_review_unusual_or_admin_control_activity, not malicious
Public examples: synthetic-only rows matching the private schema
Model artifacts: do not commit private-trained models until reviewed
First model: logistic regression, then random forest
First result sink: local report plus Splunk lookup output
```

## Next-question order

If we want to resolve this efficiently, answer in this order:

1. Confirm ONNX-first or MLTK-only.
2. Identify safe source indexes/sourcetypes.
3. Define `label_binary = 1` for v0.
4. Pick the first window size.
5. Decide public sample data policy.
6. Pick the model app namespace in Splunk.
7. Decide whether to commit only scripts/specs or also reviewed synthetic sample rows.
