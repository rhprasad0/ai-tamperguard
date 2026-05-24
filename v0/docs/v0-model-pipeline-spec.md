# AI TamperGuard v0 Model Pipeline Spec

This document supersedes the earlier dataset-spec framing. v0 now specifies the full local-training-to-Splunk-scoring pipeline.

## Purpose

v0 is a smoke test, not the final adversarial dataset.

The immediate goal is to prove an end-to-end loop:

```text
existing authorized Splunk control-plane logs
→ local feature extraction
→ local model training
→ model export/package
→ deployment into Splunk
→ Splunk-side scoring/inference on held-out windows
→ local comparison report
```

This version does **not** require an uncensored agent, synthetic malicious activity, or an elaborate attack harness. If we can train locally on legitimate Splunk activity and get deterministic scoring running inside Splunk, the project has proven the downstream path that later datasets must satisfy.

This is a plumbing test. It is allowed to be boring. The security camera may blink later; first we prove the camera is plugged in.

## Resolved v0 decisions

These decisions are fixed for the first v0 working-model pass unless explicitly revised later.

| Decision | v0 answer |
|---|---|
| Hardware split | Train on the GPU rig; run Splunk on the CPU-only thin client. |
| Splunk version | Splunk Enterprise `10.2.3`, build `4d61cf8a5c0c`, Linux `x86_64`; license state verified as `OK` during planning. |
| Splunk ML apps | Neither Splunk AI Toolkit nor classic MLTK is installed on the current thin-client Splunk instance. |
| First deployment path | No-ML-app logistic-regression artifact scoring inside Splunk. |
| ONNX / MLTK status | Future compatibility path only; not the first v0 implementation target. |
| Splunk app namespace | Use an AI TamperGuard app namespace such as `ai_tamperguard`. |
| Deployment operator | Hermes should drive deployment/validation, preferably through Splunk MCP or a narrow AI TamperGuard artifact-deploy write path. |
| First data sources | Private Splunk control-plane logs: `_audit`/`audittrail` and `_configtracker`/`splunk_configuration_change`. |
| Default time range | Start with the last 30 days available in the lab, then narrow if volume or private-review burden is too high. |
| Default window | `actor_60m` for the first pass unless a quick volume check proves it produces too few rows. |
| First label meaning | `working_model_positive_proxy` / `needs_review` proxy, not malicious ground truth. |
| Feature posture | Boring numeric/boolean behavior-window features first; defer clever categorical encoding until the pipeline works. |
| Public data posture | Do not commit generated data for the first test run. If public sample rows are needed later, generate fully synthetic examples. |
| Artifact posture | Do not commit generated data, private-trained model artifacts, or private reports by default. Commit code, schemas, docs, templates, and reproducible scripts. |
| Verification | Compare Splunk-side scores/probabilities/predictions against local Python expected values on a held-out fixture. |

## v0 success criteria

v0 is successful when we can demonstrate all of the following:

1. Query authorized local Splunk control-plane logs from the current lab.
2. Convert those events into fixed-schema behavior-window rows.
3. Train at least one small baseline model locally, starting with logistic regression.
4. Export/package a CPU-safe scoring artifact that Splunk can use without AI Toolkit or MLTK.
5. Deploy the scoring artifact and held-out window fixture into the `ai_tamperguard` Splunk app namespace, or an equivalent MCP-readable location.
6. Run Splunk-side scoring against held-out lookup rows.
7. Compare Splunk-side scores/probabilities/predictions against local expected values within a small numeric tolerance.
8. Produce a tiny local report with model diagnostics, deployment notes, prediction-comparison results, and known limitations.

A pass means the pipeline works. It does **not** mean the model detects real malicious tampering.

## Non-goals for v0

v0 explicitly does **not** attempt to:

- create a public benchmark-quality dataset
- model real tampering behavior comprehensively
- use an uncensored agent
- publish raw logs from the local Splunk install
- publish generated lab data from the first test run
- train a large language model
- require GPU inference inside Splunk
- require Splunk AI Toolkit, MLTK, DSDL, or ONNX for the first implementation
- claim real-world detection performance
- compare vendors or make claims about Splunk security
- create exploit instructions or abuse recipes
- build a dashboard before the scoring path works

## Splunk environment constraints

The current target Splunk environment is intentionally modest:

```text
Splunk: Splunk Enterprise 10.2.3, build 4d61cf8a5c0c
Host class: thin client
Inference hardware: CPU only
ML apps installed: no Splunk AI Toolkit, no MLTK
Preferred app namespace: ai_tamperguard
```

Because no Splunk ML app is installed yet, the first pass must not depend on `fit`, `apply`, `score`, ONNX upload, or `.mlmodel` execution. Those remain useful later paths after the basic pipeline works.

The v0 model artifact should therefore be simple enough to score directly in SPL, such as a logistic-regression bundle containing:

```text
model_version
feature_order
intercept
coefficients
threshold
training_metadata
```

## Data source

v0 should use legitimate Splunk control-plane activity already present in the authorized local Splunk installation.

### First-pass private sources

Use these first:

```text
index=_audit sourcetype=audittrail
index=_configtracker sourcetype=splunk_configuration_change
```

The intended event families are:

- auth/session activity
- search activity
- saved-search and knowledge-object activity
- role/capability/token/index/input-related activity where visible
- app/config/admin activity from configuration-change records
- REST/control-plane activity after normalization

### Context-only or later sources

Do **not** include these in the first baseline training set unless scope is explicitly expanded:

- `index=_internal`: troubleshooting and pipeline-health context only
- `index=agentops`: synthetic/experiment validation only
- `index=openclaw_tamper_lab`: synthetic/experiment validation only
- endpoint/router/general LAN telemetry: out of scope for v0 Splunk control-plane behavior

Raw log events are private evidence, not the modeling artifact. The modeling artifact is the behavior-window table.

## Unit of modeling

The model trains on behavior windows, not individual raw events.

Recommended v0 window types:

| Window type | Purpose | v0 status |
|---|---|---|
| `actor_60m` | Group activity by actor or actor surrogate over 60 minutes. | First-pass default. |
| `actor_15m` | Denser activity windows where volume supports it. | Later/optional. |
| `session_window` | Group by session/request identity if available. | Later/optional; avoid exposing raw session IDs. |
| `object_burst` | Group actions around a touched object such as a saved search or config path. | Later/optional. |

For the first working model, generate only one window family: `actor_60m`, unless a quick volume check shows it produces too few rows.

## Minimal v0 labels

Because v0 may only use legitimate logs, labels must be modest and honest.

The first smoke test should use a binary target:

```text
label_binary = 0  # normal / low-risk proxy
label_binary = 1  # working_model_positive_proxy / needs_review proxy
```

Important: in v0, `label_binary = 1` does **not** mean malicious. It means “useful as a positive proxy to exercise training, scoring, deployment, and validation.”

A valid positive proxy can be any deterministic rule that creates separable classes from the private behavior-window table, such as:

- admin/config-heavy windows
- unusual action/status concentration
- detection-control or search-tuning windows
- synthetic or held-out positive examples, if explicitly separated

Recommended label fields:

```text
label
label_binary
label_source
label_confidence
```

For the first pass, `label_source` should make the weak-label nature explicit, for example:

```text
heuristic_admin_config_activity
heuristic_unusual_status_concentration
synthetic_positive_proxy
manual_spot_check
```

Manual review is optional and should only sanity-check obvious nonsense. Do not block v0 on a defensible detection taxonomy.

## Minimal v0 schema

Each behavior-window row should include stable identity, label, feature, and optional private evidence/debug fields.

### Identity fields

```text
window_id
window_start
window_end
window_type
source_dataset
actor_surrogate_private
```

`actor_surrogate_private` may be useful for grouping and private debugging, but must not be published or used as a high-cardinality model feature.

### Label fields

```text
label
label_binary
label_source
label_confidence
```

`label_confidence` is optional. If omitted, the deterministic weak label should still be reproducible from the training script.

### Controlled categorical fields

Controlled categorical fields are allowed in the schema, but the first model should not depend on them unless they are already low-cardinality and stable.

```text
actor_type
role_class
time_bucket
primary_interface
primary_object_type
```

Use controlled vocabularies and `unknown` where necessary. Avoid raw usernames, raw object names, raw saved-search names, raw paths, raw URLs, raw session IDs, hostnames, tokens, and raw SPL as model features.

### Numeric and boolean feature fields

The first model should use numeric and boolean `feature_*` columns only.

Recommended compact feature families:

```text
feature_event_count
feature_search_count
feature_audit_event_count
feature_configtracker_event_count
feature_admin_action_count
feature_saved_search_action_count
feature_config_action_count
feature_lookup_action_count
feature_app_action_count
feature_rest_action_count
feature_token_or_rbac_action_count
feature_index_or_input_action_count
feature_error_count
feature_failed_permission_count
feature_unique_actions
feature_unique_object_types
feature_off_hours
feature_weekend
feature_after_hours_admin_activity
feature_detection_object_touched
feature_monitoring_object_touched
feature_risky_keyword_count
```

All numeric fields default to `0`. Boolean fields are `0` or `1`. No nulls.

The exact first-pass implementation can use a smaller subset, as long as it creates a compact table with roughly 8–20 reliable numeric/boolean features.

### Private evidence/debug fields

Evidence fields are for human inspection and should not be used as model features in v0:

```text
evidence_event_examples_redacted
evidence_action_summary
evidence_object_types
evidence_private_notes
evidence_splunk_search_url_private
```

Do not publish private Splunk URLs. If `evidence_splunk_search_url_private` is useful locally, keep it out of public sample files or replace it with a placeholder.

Raw `_raw`, usernames, hostnames, IPs, Splunk URLs, REST paths containing local object names, raw SPL/search strings, saved-search names, object paths, session IDs, tokens, credential names/values, internal file paths, and private app/index/source details must not leave the private machine in generated artifacts.

## Local training path

Train locally first with a small, reproducible Python script or CLI path. Notebooks are optional scratch space; they are not the source of truth for v0.

Recommended dependency set:

```text
pandas
scikit-learn
onnx
skl2onnx
onnxruntime
```

`onnx`, `skl2onnx`, and `onnxruntime` may remain installed for later compatibility checks, but the first deployment target is not ONNX.

Recommended baseline order:

1. Logistic regression
2. Random forest, only after the linear path works
3. Gradient boosting or XGBoost-compatible alternative, only if already available and useful later

Logistic regression is first because it is easy to train, explain, export, and score in plain SPL using coefficients.

Minimum local diagnostics:

```text
accuracy
precision
recall
f1
confusion_matrix
classification_report
prediction_distribution
```

Because labels are weak in v0, treat these metrics as plumbing diagnostics, not evidence of real detection quality. A pass means the training script runs, produces non-degenerate predictions, emits a diagnostics report, and can compare local predictions against Splunk-side scoring.

Private-trained artifacts should be stored locally only by default and regenerated on demand from scripts and private data. Do not commit private-trained artifacts unless explicitly reviewed and declared public-safe.

## Splunk deployment and inference path

### First-pass path: no-ML-app logistic-regression scoring

The first Splunk-side scoring path should load held-out behavior-window rows, apply the exported feature order/coefficient artifact, calculate a linear score and probability, threshold the result, and emit score metadata.

Shape:

```spl
| inputlookup tamperguard_windows_holdout.csv
| fillnull value=0 feature_*
| eval score = <intercept> + (<coef_1> * feature_1) + ... + (<coef_n> * feature_n)
| eval probability = 1 / (1 + exp(-score))
| eval prediction = if(probability >= <threshold>, 1, 0)
| eval model_version = "<model_version>", scored_at = now()
| table window_id score probability prediction model_version scored_at
```

The concrete SPL should be generated from the training artifact or checked in as a parameterized template so feature order cannot drift. The held-out fixture should include local Python expected scores and predictions for comparison.

### Deployment operation model

Hermes should operate deployment so Ryan does not manually upload artifacts through the Splunk UI.

Preferred write path:

```text
A narrow AI TamperGuard artifact-deploy capability scoped to the ai_tamperguard app.
```

Current known blocker:

```text
The existing Splunk MCP toolset can inspect/query Splunk, but a harmless outputlookup deployment probe was blocked by command safeguards.
```

Acceptable fallback:

```text
Hermes writes the artifact through Splunk REST or app filesystem packaging, then validates through Splunk MCP.
```

The first result sink should be a local validation report plus a Splunk lookup or equivalent MCP-readable result artifact. Defer summary indexes and dashboards until the scoring path works.

### Verification requirement

The real v0 inference pass/fail check is prediction equivalence, not model quality.

Verification should:

1. Generate a small held-out fixture with local Python expected scores, probabilities, and predictions.
2. Run the same fixture through Splunk-side scoring.
3. Compare probabilities within a small numeric tolerance.
4. Require exact prediction-label agreement for the fixture.
5. Record the comparison in a local report.

## Future compatibility paths

ONNX and MLTK remain important compatibility paths, but they are not the first v0 deployment target because the current Splunk instance has no AI Toolkit/MLTK installed.

### Future ONNX path

After the no-ML-app scoring path works, a later pass may:

1. Export a trained model to ONNX.
2. Install/enable Splunk AI Toolkit or another supported ONNX-capable Splunk ML app.
3. Confirm ONNX upload capabilities such as `upload_onnx_model_file`.
4. Upload the model with the required feature and target metadata.
5. Run inference with `apply onnx:<model_name>` or, if shared to the app/global namespace, `apply app:onnx:<model_name>`.

Current Splunk-doc constraints to remember for that later path:

- uploaded ONNX model files must be ONNX and under documented upload-size limits, currently 30 MB in the referenced docs
- upload requires `model_name`, `features`, `targets`, and file data
- inference requires feature fields compatible with the uploaded model
- ONNX upload/inference requires the appropriate AI Toolkit/MLTK app and capabilities

Example future shape:

```spl
| inputlookup tamperguard_windows_v0_test.csv
| apply onnx:tamperguard_v0_model
```

or, for app-shared models:

```spl
| inputlookup tamperguard_windows_v0_test.csv
| apply app:onnx:tamperguard_v0_model
```

### Future MLTK path

If classic MLTK is installed later, a Splunk-native baseline may be trained and applied with documented MLTK commands.

Example future shape:

```spl
| inputlookup tamperguard_windows_v0_train.csv
| fillnull value=0 feature_*
| fit LogisticRegression label_binary from feature_* into app:tamperguard_v0_lr
```

```spl
| inputlookup tamperguard_windows_v0_test.csv
| fillnull value=0 feature_*
| apply app:tamperguard_v0_lr as predicted_label
| score accuracy_score label_binary against predicted_label
```

For precision/recall/F1-style evaluation, use documented Splunk `score` metrics such as `precision_recall_fscore_support`, `precision_score`, `recall_score`, or `f1_score`. Do not use undocumented `score classification_report` syntax.

## v0 artifacts

### Private/local generated artifacts

Generated data, models, and reports stay local and ignored by default:

```text
data/private/raw_exports/
data/private/windows/
models/private/
reports/private/
```

Raw private exports should live outside the public repo when possible. If local project-relative staging is needed, use ignored private paths such as `data/private/` and never commit them.

### Public-safe repo artifacts

Commit code, docs, schemas, parameterized templates, and reproducible scripts only.

Recommended public-safe artifacts:

```text
docs/v0-model-pipeline-spec.md
docs/v0-open-questions.md
schemas/behavior_window_v0.schema.json
splunk/searches/score_v0_logistic_regression_template.spl
splunk/searches/validate_v0_scoring_template.spl
scripts/extract_windows_v0.py
scripts/train_v0_logistic_regression.py
scripts/render_splunk_scoring_artifact_v0.py
reports/v0-smoke-test-template.md
```

Do **not** commit generated window CSVs, private Splunk exports, trained model artifacts, or generated reports for the first test run.

If public sample rows are needed later for demos/tests, generate intentionally synthetic rows matching the schema rather than redacting lab output.

## Public safety and repo hygiene

Public-facing language should say that v0 is:

```text
a lab smoke test proving a local-training to Splunk-scoring pipeline using non-production lab telemetry and weak working-model labels
```

Do not claim:

- production tamper detection
- malicious-activity detection
- validated SOC efficacy
- vendor comparison results

Keep a lightweight pre-commit/public-safety scan to catch accidental committed runtime artifacts, tokens, local paths, environment URLs, raw Splunk URLs, hostnames, private IPs, usernames, raw SPL containing sensitive environment details, and data files.

Generated private paths such as `data/private/`, `models/private/`, and `reports/private/` should be ignored by default.

A section in this spec and the open-questions doc is enough for now. Add a separate `PUBLIC_SAFETY.md` only if public sample datasets or model artifacts are introduced later.

## Remaining implementation questions

Most planning questions are resolved in `docs/v0-open-questions.md`. The next implementation questions are intentionally narrow:

1. Does `actor_60m` produce enough rows from the chosen 30-day `_audit` + `_configtracker` range?
2. What exact deterministic weak-label rule should the first training script implement?
3. Which narrow artifact-deploy path will Hermes use for the `ai_tamperguard` app: Splunk MCP extension, Splunk REST, or app filesystem packaging?
4. What numeric tolerance should the local-vs-Splunk probability comparison enforce?

## Recommended defaults

Unless explicitly revised, use these defaults:

```text
Deployment path: working-model smoke test using no-ML-app logistic-regression artifact scoring; ONNX later after the pipeline works
Deployment operator: Hermes via Splunk MCP where possible; Ryan should not need to manually upload model artifacts
Current MCP blocker: generic outputlookup is blocked, so add/enable a narrow AI TamperGuard artifact-deploy write path before full deployment
Hardware split: train on GPU rig; deploy/infer on CPU-only Splunk thin client
Splunk app namespace: AI TamperGuard app (ai_tamperguard)
Capabilities: local/admin context should have lookup/artifact upload/update capability; recheck ONNX-specific capability only if AI Toolkit is installed later
Data source: private _audit/audittrail plus _configtracker/splunk_configuration_change Splunk control-plane logs
Window size: actor_60m for first pass
Positive label: working_model_positive_proxy / needs_review proxy, not malicious ground truth
Feature posture: boring numeric/boolean behavior-window features first; defer clever categories until the pipeline works
Public examples: none for this test run; if needed later, use synthetic-only rows matching the schema
Data/artifact policy: do not commit generated data, trained model artifacts, or reports for this test run
First model: logistic regression, then random forest
First result sink: local comparison report plus Splunk lookup/equivalent MCP-readable output
```
