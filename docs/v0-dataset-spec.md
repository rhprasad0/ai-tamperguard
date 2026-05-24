# AI TamperGuard v0 Dataset Spec

## Purpose

v0 is a smoke test, not the final adversarial dataset.

The immediate goal is to prove an end-to-end loop:

```text
existing authorized Splunk logs
→ local feature extraction
→ local model training
→ model export/package
→ deployment into Splunk
→ Splunk-side inference on held-out windows
```

This version does **not** require an uncensored agent, synthetic malicious activity, or an elaborate attack harness. If we can train locally on legitimate Splunk activity and get a model running inside Splunk, the project has proven the downstream path that later datasets must satisfy.

## v0 success criteria

v0 is successful when we can demonstrate all of the following:

1. Export a small, redacted sample of legitimate Splunk events from an authorized local Splunk environment.
2. Convert those events into fixed-schema behavior-window rows.
3. Train at least one baseline model locally.
4. Export or package the model in a format Splunk can use.
5. Deploy the model into Splunk.
6. Run Splunk-side inference against a held-out lookup or search result.
7. Produce a tiny report with model metrics, deployment notes, and known limitations.

This is a plumbing test. It is allowed to be boring. The security camera may blink later; first we prove the camera is plugged in.

## Non-goals for v0

v0 explicitly does **not** attempt to:

- create a public benchmark-quality dataset
- model real tampering behavior comprehensively
- use an uncensored agent
- publish raw logs from the local Splunk install
- train a large language model
- claim real-world detection performance
- compare vendors or make claims about Splunk security
- create exploit instructions or abuse recipes

## Data source

v0 should use legitimate logs already present in an authorized Splunk installation.

Candidate source categories:

- Splunk audit events
- search activity
- saved search or knowledge-object activity
- app/config/admin activity, if visible and safe
- internal operational events suitable for local-only experimentation

Public artifacts must contain only redacted, normalized, or synthetic examples. Raw local logs stay private.

## Unit of modeling

The model trains on behavior windows, not individual raw events.

Recommended v0 window types:

| Window type | Purpose |
|---|---|
| `actor_15m` | Group activity by actor over 15 minutes. |
| `actor_60m` | Simple longer context window for low-volume environments. |
| `session_window` | Group by session/request identity if available. |
| `object_burst` | Group actions around a touched object such as a saved search or config path. |

For v0, start with `actor_60m` unless the available logs are dense enough for `actor_15m`.

## Minimal v0 labels

Because v0 may only use legitimate logs, labels should be modest and honest.

Recommended first label set:

```text
benign_normal_activity
benign_admin_or_config_activity
benign_detection_or_search_tuning
needs_review_unusual_activity
```

For the first smoke test, this can be simplified to a binary target:

```text
label_binary = 0  # normal / low-risk
label_binary = 1  # needs review / higher-risk administrative or detection-control activity
```

Important: in v0, `label_binary = 1` does **not** mean malicious. It means “interesting enough to test the model and deployment path.”

## Minimal v0 schema

Each behavior-window row should include stable identity, label, feature, and evidence-summary fields.

### Identity fields

```text
window_id
window_start
window_end
window_type
source_dataset
```

### Label fields

```text
label
label_binary
label_triage
```

### Controlled categorical fields

```text
actor_type
role_class
time_bucket
primary_interface
primary_object_type
```

Use controlled vocabularies and `unknown` where necessary. Avoid raw usernames, raw object names, raw paths, raw URLs, and raw SPL as model features.

### Numeric and boolean feature fields

Minimal v0 feature set:

```text
feature_event_count
feature_search_count
feature_audit_event_count
feature_admin_action_count
feature_saved_search_action_count
feature_config_action_count
feature_lookup_action_count
feature_app_action_count
feature_rest_action_count
feature_error_count
feature_failed_permission_count
feature_unique_actions
feature_unique_object_types
feature_unique_indexes_referenced
feature_off_hours
feature_after_hours_admin_activity
feature_detection_object_touched
feature_monitoring_object_touched
feature_risky_keyword_count
```

All numeric fields default to `0`. Boolean fields are `0` or `1`. No nulls.

### Evidence fields

Evidence fields are for human inspection and should not be used as model features in v0:

```text
evidence_event_examples_redacted
evidence_action_summary
evidence_object_types
evidence_splunk_search_url_private
```

Do not publish private Splunk URLs. If `evidence_splunk_search_url_private` is useful locally, keep it out of public sample files or replace it with a placeholder.

## Suggested local training path

Train locally first with a small sklearn pipeline.

Recommended baseline order:

1. Logistic regression
2. Random forest
3. Gradient boosting or XGBoost-compatible alternative if already available

Minimum metrics:

```text
accuracy
precision
recall
f1
confusion_matrix
classification_report
```

Because labels are weak in v0, treat these metrics as plumbing diagnostics, not evidence of real detection quality.

## Suggested Splunk deployment path

Preferred v0 deployment path:

1. Train locally.
2. Export to ONNX if Splunk AI Toolkit ONNX import is available.
3. Upload model to Splunk AI Toolkit.
4. Run inference with `apply onnx:<model_name>` against held-out feature rows.

Fallback path:

1. Export the feature rows as lookup CSV.
2. Train a Splunk-native baseline using AI Toolkit / MLTK `fit`.
3. Run inference using `apply`.
4. Compare local and Splunk-side behavior.

Example intended Splunk shape:

```spl
| inputlookup tamperguard_windows_v0_test.csv
| apply onnx:tamperguard_v0_model
```

Fallback Splunk-native shape:

```spl
| inputlookup tamperguard_windows_v0_train.csv
| fit RandomForestClassifier label_binary from feature_* into app:tamperguard_v0_rf
```

```spl
| inputlookup tamperguard_windows_v0_test.csv
| apply app:tamperguard_v0_rf as predicted_label
| score classification_report label_binary predicted_label
```

## v0 artifacts

Private/local artifacts:

```text
data/private/raw_exports/
data/private/windows/
models/private/
reports/private/
```

Public-safe repo artifacts:

```text
docs/v0-dataset-spec.md
schemas/behavior_window_v0.schema.json
splunk/searches/train_v0_random_forest.spl
splunk/searches/apply_v0_onnx.spl
splunk/searches/apply_v0_random_forest.spl
examples/windows_v0_sample_redacted.csv
reports/v0-smoke-test-template.md
```

The first public example file should be tiny and redacted. It exists to document shape, not to publish the real local dataset.

## Open questions

### Splunk environment

1. Which Splunk version and AI Toolkit / MLTK version are installed?
2. Is Splunk AI Toolkit ONNX upload available and enabled?
3. Are the required ONNX upload capabilities available to the local user/app context?
4. If ONNX is not available, is classic MLTK `fit` / `apply` available?
5. Which app namespace should hold the model: a new `ai_tamperguard` app, the Search app, or another local app?

### Data access and export

6. Which indexes and sourcetypes are safe to use for v0?
7. Which fields are present for actor/user, action, object, interface, status, and request/session IDs?
8. Can we export enough legitimate audit/control-plane activity to create at least a few hundred behavior windows?
9. What time range should v0 use?
10. Which raw fields must never leave the private machine, even in redacted examples?

### Labeling

11. Should v0 use weak heuristic labels, manual labels, or both?
12. What is the first `label_binary = 1` definition: admin/config activity, detection-control activity, unusual activity, or manually reviewed activity?
13. Do we need a separate `needs_review` class so nobody mistakes weak labels for malicious labels?

### Feature engineering

14. Which feature columns can be computed reliably from the available logs?
15. Which high-cardinality fields need normalization or exclusion?
16. Should the first model use only numeric/boolean features, or include low-cardinality categorical fields with one-hot encoding?
17. What is the default window size: 15 minutes, 60 minutes, session-based, or multiple windows?

### Local training

18. Which local Python environment should own training dependencies?
19. Are `scikit-learn`, `pandas`, `onnx`, `skl2onnx`, and `onnxruntime` sufficient for v0?
20. What minimum metric/report should count as a passed smoke test?
21. Should the model artifact be committed only if it is trained on redacted sample data, or never committed at all?

### Splunk deployment

22. What model format should be the first deployment target: ONNX or Splunk `.mlmodel`?
23. How will the model be uploaded into Splunk: UI, filesystem/app packaging, REST API, or Splunk search command?
24. What exact SPL will run inference against held-out windows?
25. Where should inference results be written: lookup, summary index, dashboard, or local report only?

### Public safety and repo hygiene

26. What is the public/private split for artifacts?
27. Should public examples be fully synthetic instead of redacted local examples?
28. What scanner/check prevents raw Splunk URLs, hostnames, IPs, usernames, tokens, and internal paths from entering the public repo?
29. What language should the README use to avoid implying that v0 detects malicious tampering when it only proves training/deployment plumbing?

## Recommended next decisions

For fastest progress, answer these first:

1. ONNX path or MLTK-only path?
2. Which private Splunk indexes/sourcetypes are safe for v0 extraction?
3. What weak label definition should represent `label_binary = 1`?
4. What window size should we start with?
5. Should public sample data be synthetic-only, even if training uses private legitimate logs?

My default recommendation:

```text
Deployment path: ONNX first, MLTK fallback
Data source: private legitimate Splunk audit/control-plane logs
Window size: actor_60m for first pass
Positive label: needs_review_unusual_or_admin_control_activity, not malicious
Public examples: synthetic-only rows matching the private schema
Model artifacts: do not commit private-trained models until reviewed
```
