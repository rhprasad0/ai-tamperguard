# AI TamperGuard v0 Model Pipeline Spec — Adversarial Edition

This document supersedes the earlier dataset-spec framing. v0 now specifies the full local-training-to-Splunk-scoring pipeline.

This is a stricter, implementation-ready restatement of `v0-model-pipeline-spec.md`. It preserves the resolved decisions in `v0-open-questions.md` but reframes them as enforceable invariants, gates, forbidden behaviors, and verification steps. Some gates below are intentionally adversarial hardening defaults beyond the resolved source docs; when a threshold is marked as an adversarial default, treat it as a proposed first-run guardrail that can be revised only with measured evidence. If this document and the original disagree, fail loud and reconcile before writing code.

The mental model: v0 is a plumbing test that is unusually easy to *appear* to pass while actually being broken. Treat every "green" with suspicion until a named gate proves it.

---

## 1. Scope (unchanged baseline)

v0 proves a single loop end to end:

```text
authorized local Splunk control-plane logs (_audit, _configtracker)
→ local feature extraction (deterministic, reproducible)
→ local training of a small CPU-safe model (logistic regression first)
→ exported scoring artifact (no Splunk ML app required)
→ deployment into the ai_tamperguard Splunk app namespace
→ Splunk-side scoring of a held-out fixture using SPL eval
→ local-vs-Splunk equivalence comparison
→ local report with diagnostics, comparison results, known limits
```

v0 does **not** prove tamper detection. v0 does **not** require an uncensored agent, a synthetic attack harness, ONNX, MLTK, AI Toolkit, GPU inference, or a dashboard. Every one of those is an explicit non-goal for this phase.

---

## 2. Invariants (must always hold)

Numbered for citation in code review and PRs. If any invariant is violated, the run is invalid regardless of metrics.

1. **No private byte leaves the private machine in a committed artifact.** This includes raw `_raw`, usernames, hostnames, IPs, Splunk URLs, REST paths with local names, raw SPL, saved-search names, object paths, session IDs, tokens, credential names/values, internal file paths, and any field listed under §10.
2. **Generated private run data is not committed in v0.** Not raw exports, not behavior-window CSVs, not trained model bundles, not reports, not held-out fixtures. Separate public-safe synthetic examples may be added only by explicit review in a later change; they must not be derived from private Splunk output.
3. **The behavior-window table is the modeling artifact.** Raw events are private evidence and never inputs to the model or to any committed file.
4. **Single source of truth for `(feature_order, intercept, coefficients, threshold, model_version)`.** This tuple is produced once by the training script, serialized to one artifact, and consumed by both the Splunk scoring template and the local verification harness. No second source is allowed to redefine any of these values.
5. **Deterministic training.** Given the same private input and the same git SHA of the training script, the produced artifact must be byte-identical for the parts that affect scoring (feature order, coefficients to documented precision, threshold, model_version).
6. **Deterministic weak label.** The label rule is a pure function of the behavior-window row and is reproducible from the script with no human-in-the-loop step required.
7. **No raw, high-cardinality string is ever a model feature.** Features are numeric or boolean only in v0. Categorical strings live only in schema/evidence, not in the linear score.
8. **Splunk-side scoring uses SPL `eval` only.** No `fit`, no `apply`, no `score`, no `onnx`, no `.mlmodel`, no Python custom commands, no external lookups that call code in v0.
9. **Held-out fixture is held out before training.** The split is computed first, persisted, and the training script must refuse to read the holdout partition.
10. **Equivalence is gated by numbers, not vibes.** See §6 for the exact tolerance and prediction-agreement requirement.
11. **`label_binary = 1` is a working-model positive proxy, not malicious ground truth.** Any public-facing artifact that says otherwise is non-compliant.
12. **No model artifact, no held-out fixture, and no report is committed without an explicit human review marking it public-safe.** Default is private and `.gitignored`; for the first v0 run, commit none of them.

---

## 3. Forbidden claims (public-facing language)

The following statements must not appear in README, commit messages, PR descriptions, dashboards, screenshots, blog posts, or any user-facing artifact derived from v0:

- "detects tampering"
- "detects malicious activity"
- "production-ready detection"
- "validated SOC efficacy"
- "outperforms / compared favorably to <vendor>"
- "labeled malicious / attack / tamper" (as ground truth)
- "trained on real attacks"
- "real-world detection performance"
- any phrasing implying the model's positive class corresponds to confirmed bad behavior

Approved phrasing:

- "lab smoke test of a local-training to Splunk-scoring pipeline"
- "non-production lab telemetry"
- "weak working-model positive proxy labels"
- "round-trip equivalence between local Python scoring and Splunk SPL scoring on a held-out fixture"

The label field name `label_binary` is allowed because it is structural. The label *value* description must be `working_model_positive_proxy` or `needs_review`, never `malicious`, `attack`, or `tamper`.

---

## 4. Forbidden behaviors

- Committing any file under `data/private/`, `models/private/`, or `reports/private/`.
- Including `actor_surrogate_private`, `evidence_*`, or `*_private` columns in any artifact intended to leave the private machine.
- Using `feature_*` wildcards in SPL without an explicit feature-order check against the model artifact's `feature_order`.
- Using `inputlookup` columns directly in arithmetic without `tonumber()` or an explicit cast — Splunk documents `tonumber()` for converting string field values to numbers, and explicit conversion prevents false-greens from lookup-field typing or silent string-numeric coercion.
- Comparing `scored_at` between local and Splunk runs (it is `now()`-derived and must be excluded from the comparison key set).
- Hand-editing the generated SPL scoring template. Regenerate it from the artifact.
- Running training and verification on overlapping rows.
- Manually uploading model artifacts through the Splunk UI. v0 requires Hermes-driven deployment.
- Bypassing the MCP write-path safeguard with a workaround that lacks an audit trail (see §8).
- Installing Splunk AI Toolkit, MLTK, or DSDL "to make verification easier." The whole point of the no-ML-app path is to prove it works without them.
- Touching `index=_internal`, `index=agentops`, or `index=openclaw_tamper_lab` as v0 training input.
- Including endpoint, router, or general LAN telemetry as v0 input.

---

## 5. Pass/fail gates

A v0 run passes only if **all** gates below are explicitly evaluated and explicitly pass. A missing gate is a fail.

### G1 — Volume gate
The following counts are adversarial defaults for the first run, not Splunk-documented minimums:

- `actor_60m` over the chosen 30-day private range produces **≥ 200 windows total** and **≥ 20 windows in each class** after applying the deterministic weak-label rule.
- If fewer, narrow the window or change the proxy rule and re-evaluate. Do not paper over by lowering the threshold.

### G2 — Non-degeneracy gate (anti-false-green)
The trained model must be non-trivial. The following thresholds are adversarial defaults for detecting common false-greens; revise only with measured evidence:
- At least **3 coefficients** with `|coef| > 1e-6`.
- Predicted probability distribution on the holdout has `std(probability) > 0.05`. A constant predictor fails.
- Predicted-class distribution on the holdout includes **both** classes. An all-zero or all-one predictor fails even if labels are imbalanced.
- The holdout has at least one row in each true class (forced by stratified split).

### G3 — Holdout integrity gate
- The held-out fixture's `window_id` set is disjoint from the training set.
- The split is computed and persisted before the first training call.
- The training script asserts it cannot read holdout rows.

### G4 — Schema conformance gate
- Every behavior-window row validates against `schemas/behavior_window_v0.schema.json`.
- All `feature_*` columns are present in every row. Missing columns are not silently filled; missing values within an existing column default to `0` per spec.
- `feature_order` in the model artifact equals the fixture feature manifest exactly. No extras, no omissions, no reordering. If the implementation chooses sorted feature names, the training script must generate and persist that order; reviewers must not infer or hand-edit it.

### G5 — Deployment gate
- The model artifact, the scoring SPL, and the held-out fixture lookup all exist under the `ai_tamperguard` app namespace, unless an explicitly approved MCP-readable equivalent namespace is documented in the deploy log before deployment.
- Hermes performed the deployment through an approved, audited write path (see §8). Manual UI upload by Ryan invalidates the run.
- A fresh Splunk MCP read can locate all three artifacts by their declared names.

### G6 — Local-vs-Splunk equivalence gate
See §6. Both sub-gates G6a (probability tolerance) and G6b (prediction agreement) must pass on the entire held-out fixture.

### G7 — Public-safety scan gate
- The repository pre-commit scan passes with zero hits on the public-safety patterns (§9).
- No file under `data/private/`, `models/private/`, or `reports/private/` is tracked by git.
- No tracked file references a private hostname, IP, raw username, raw object name, or raw Splunk URL.

### G8 — Report gate
- A local report exists at `reports/private/v0-smoke-test-<model_version>.md` and contains: model_version, training git SHA, label-rule fingerprint, dataset window summary, training diagnostics, holdout split sizes, deployment write-path used, MCP validation transcript summary, G2 anti-degeneracy numbers, G6 equivalence numbers, known limitations, and an explicit "this is not a tamper detector" disclaimer.

A run that passes G1–G8 is a passing v0 smoke test. It is **not** evidence that the model detects tampering, nor that the labels are meaningful beyond the working-model proxy.

---

## 6. Local-vs-Splunk equivalence (the most-likely-broken thing)

This is the only verification step that distinguishes v0 from a Jupyter exercise. Get it wrong and the whole run is theater.

### 6.1 Comparison keys
For each `window_id` in the holdout fixture, compare:
- `score` (raw linear combination, pre-sigmoid)
- `probability` (post-sigmoid)
- `prediction` (thresholded class)

Do **not** compare `scored_at`. Do **not** compare `model_version` for equivalence purposes (it is a label, not a value); instead assert the local and Splunk runs reference the same `model_version` string.

### 6.2 Tolerance — G6a
- `abs(probability_local - probability_splunk) <= 1e-6` for every row.
- `abs(score_local - score_splunk) <= 1e-6` for every row.
- The `1e-6` tolerance is an adversarial default for the first implementation. Splunk documents `exp()` and numeric-conversion helpers such as `tonumber()`, but the exact residual between Python and Splunk must be measured on the real fixture before treating this tolerance as empirically proven.

If `1e-6` turns out to be infeasible empirically because of a documented Splunk numeric quirk or measured Python/Splunk residual, **raise it explicitly in a follow-up PR with the measured residual and a reason**. Do not silently relax the tolerance in code.

### 6.3 Prediction agreement — G6b
- `prediction_local == prediction_splunk` for **100%** of holdout rows.
- One disagreement fails G6b. This is intentional. Probability tolerance can absorb float noise; the thresholded class cannot.

### 6.4 Numeric coercion hazards (must be handled)
- Treat `inputlookup` feature values as untrusted until explicitly converted. The scoring SPL must `tonumber()` every `feature_*` column or use a per-column `eval feature_x = tonumber(feature_x)` step before arithmetic. Verify by inspecting one intermediate row and failing if any converted feature is NULL unexpectedly.
- Boolean `feature_*` columns are `0` / `1` integers in the schema. Confirm they are not stringified as `"true"` / `"false"` anywhere in extraction or fixture serialization.
- Score magnitudes outside ±50 push `exp(-score)` into denormal/overflow territory. The artifact must record `min_score_seen_in_training` and `max_score_seen_in_training` and the verification harness must assert holdout scores fall inside `[min - 5, max + 5]`. Outside that envelope, equivalence may hold but is no longer a meaningful test.
- Sigmoid implementation in Python must use `1.0 / (1.0 + math.exp(-score))`, matching the SPL form, not `scipy.special.expit` (which is numerically stabilized differently and will produce a different residual pattern at extremes).

### 6.5 Known traps that look like passes
- All-zero features → local and Splunk both produce `probability = sigmoid(intercept)` → trivially equal. G2 catches this.
- Constant predictor → both sides agree on every row → equivalence passes vacuously. G2 catches this.
- Missing column silently filled by `fillnull value=0 feature_*` in SPL while the local extractor used a different default → equivalence holds but the model is not the model that was trained. G4 catches this.
- Feature reordering between training CSV and holdout CSV → equivalence either fails loud or, if coefficients happen to be similar, fails quiet. The `feature_order` byte-comparison in G4 catches this.

---

## 7. Artifact boundaries

### 7.1 Private only (never committed)
```
data/private/raw_exports/          # raw SPL exports
data/private/windows/              # generated behavior-window CSVs
data/private/holdout/              # held-out fixture CSVs (pre-deployment)
models/private/                    # trained model bundles (.json or .pkl)
reports/private/                   # local diagnostics, equivalence reports
splunk/private/                    # any rendered SPL containing concrete coefficients
```

These directories must exist in `.gitignore`. CI should refuse to track files under them.

### 7.2 Public-safe (committed)
```
docs/v0-model-pipeline-spec.md
docs/v0-model-pipeline-spec-adversarial.md
docs/v0-open-questions.md
schemas/behavior_window_v0.schema.json
schemas/model_artifact_v0.schema.json                # NEW: contract for the model bundle
schemas/holdout_fixture_v0.schema.json               # NEW: contract for the fixture lookup
splunk/searches/score_v0_logistic_regression_template.spl   # parameterized, no concrete coefficients
splunk/searches/validate_v0_scoring_template.spl
scripts/extract_windows_v0.py
scripts/split_holdout_v0.py                          # deterministic split
scripts/train_v0_logistic_regression.py
scripts/render_splunk_scoring_artifact_v0.py
scripts/verify_local_vs_splunk_v0.py
scripts/public_safety_scan.py
reports/v0-smoke-test-template.md
```

Templates contain placeholders only. A template with concrete coefficients, hostnames, or private object names is a leak.

### 7.3 Sample data
- No public sample data ships in v0.
- If sample rows are needed later for tests, they must be **fully synthetic**, generated from a checked-in seed script, and labeled `label_source = synthetic_demo`. They must not be derived by redacting lab output.

---

## 8. MCP deployment guardrails (the operational soft spot)

The original spec says "Hermes drives deployment via Splunk MCP" but does not specify how that is safe. v0 must:

### 8.1 Approved write paths (pick one and document which was used)
1. **Narrow MCP capability**: a Splunk MCP tool scoped to write only under `apps/ai_tamperguard/lookups/` and `apps/ai_tamperguard/local/savedsearches.conf`. No general `outputlookup`, no arbitrary REST. The tool's authorization scope must be inspectable from MCP metadata.
2. **Splunk REST via service-bound credentials**: REST calls scoped to the `ai_tamperguard` app namespace, with audit logging enabled in `_audit`. Credentials live outside the repo.
3. **App filesystem packaging**: build a `.spl` app bundle on the GPU rig, transfer it to the thin client by a documented mechanism, install via `splunk install app`. Manual UI upload is **not** an acceptable variant of this path.

### 8.2 Audit requirements
Every deployment run records:
- timestamp, operator (Hermes / Ryan), write path used
- list of files written (paths and SHA-256)
- model_version deployed
- a fresh MCP read-back that confirms each file is present with the expected SHA-256

This audit lives in `reports/private/deploy-<model_version>.log` and is referenced from the G5 report.

### 8.3 The MCP `outputlookup` block is a feature, not a bug
The existing safeguard that blocks generic `outputlookup` from MCP is doing its job. Do not weaken it. The fix is a narrower allowed surface, not a wider one. If a workaround is proposed that loses the audit trail, reject it.

### 8.4 Splunk version pinning
The spec pins Splunk Enterprise `10.2.3` build `4d61cf8a5c0c`. v0 scripts must **read the live Splunk version at deploy time and fail loud** if the major.minor differs. A different build of `10.2.x` may proceed with a warning logged; a different `10.x` minor must halt and require explicit re-approval; a different major version must halt unconditionally.

---

## 9. Public-safety scan (G7 enforcement)

A pre-commit hook (`scripts/public_safety_scan.py`) runs on every committed file and fails if any of the following patterns are detected. Patterns are illustrative, not exhaustive — extend as new private terms surface.

- Private hostnames or domains observed in the lab (parameterized list, not committed)
- IPv4/IPv6 addresses in private ranges (RFC1918, link-local, etc.) when they appear alongside other private context
- Usernames belonging to the lab operator(s)
- Raw `splunkd` URLs, `:8000` / `:8089` URLs with hostnames
- File paths under `/opt/splunk/`, `$SPLUNK_HOME`, or the operator's home directory
- Raw SPL containing `index=` followed by an unusual private index name, or `host=` with private hostnames
- Strings matching API-token shapes (long hex, JWT-like, AWS-style)
- Anything inside `data/private/`, `models/private/`, `reports/private/`, `splunk/private/`

The scan also fails on any committed file with a `.csv`, `.pkl`, `.joblib`, `.onnx`, or `.mlmodel` extension unless it is under `schemas/` and is a schema file.

Private scanner dictionaries, lab-specific host/user/domain lists, and other local denylist terms are themselves private artifacts. Keep them outside the repo or under a `.gitignored` private path; commit only generic scanner code and non-sensitive pattern classes.

The scan is intentionally noisy. False positives are cheap; false negatives are expensive.

---

## 10. Schema invariants

### 10.1 Behavior-window row (`schemas/behavior_window_v0.schema.json`)
- Identity: `window_id` (string, opaque, salted hash of `(actor_surrogate_private, window_start)` using a per-run salt not committed), `window_start` (ISO8601 UTC), `window_end` (ISO8601 UTC), `window_type` (enum: `actor_60m` for v0), `source_dataset` (string).
- Private-only: `actor_surrogate_private` (string, present in private CSVs, **must be stripped** before any artifact leaves the private machine).
- Label: `label` (string, e.g. `needs_review`), `label_binary` (integer 0/1), `label_source` (enum), `label_confidence` (float 0–1, optional).
- Features: 8–20 `feature_*` columns, all numeric (integer counts) or boolean (0/1 integers). No nulls. No strings.
- Controlled categoricals: present in schema for forward compatibility, **excluded** from v0 model input.
- Evidence: `evidence_*` fields private only.

### 10.2 Model artifact (`schemas/model_artifact_v0.schema.json`)
Required keys:
```
model_version           # format: "v0-<git_sha7>-<data_fingerprint8>-<label_rule_fingerprint8>"
trained_at_utc          # ISO8601, for the report only; not used in scoring
feature_order           # ordered list of feature_* column names
intercept               # float
coefficients            # ordered list aligned 1:1 with feature_order
threshold               # float in [0,1]
label_rule_id           # short string identifying the deterministic label rule
training_metadata       # { n_train, n_holdout, class_counts_train, class_counts_holdout, sklearn_version, python_version, random_seed }
score_envelope          # { min_score_train, max_score_train }
```
`model_version` is the integrity anchor for the entire run. It must change whenever any of code, data fingerprint, or label rule change. Treating it as a free-form label and not regenerating it after edits is a forbidden behavior (§4).

### 10.3 Held-out fixture (`schemas/holdout_fixture_v0.schema.json`)
- Required columns: `window_id`, every column in `feature_order`, plus locally-computed expected `score_local`, `probability_local`, `prediction_local` columns appended on the **private** copy.
- The Splunk-deployed lookup contains `window_id` and feature columns only. The local expected-values copy stays under `data/private/holdout/` and is never deployed.
- Verification harness joins the Splunk-side scoring output to the local expected-values copy by `window_id`.

---

## 11. Rollback and removal

A v0 run must be cleanly removable. The deploy script's inverse must:

1. Enumerate every artifact written under `ai_tamperguard` for this `model_version`: lookups, saved searches, generated result lookups.
2. Remove them via the same approved write path used at deploy.
3. Re-read via MCP and confirm every previously-deployed artifact name no longer resolves (except templates intentionally retained).
4. Append a removal record to `reports/private/deploy-<model_version>.log`.

A v0 run that cannot be cleanly removed is a v0 run that should not have been deployed. If rollback was never exercised, G5 is incomplete regardless of what scoring produced.

---

## 12. Drift fences (ONNX / MLTK / AI Toolkit)

These paths are deliberately kept in the repo as future work. v0 must not drift into them.

- `onnx`, `skl2onnx`, and `onnxruntime` may be installed in the local Python environment for future-compat experimentation. They must not appear in any v0 scoring path, any v0 deployment artifact, or any v0 SPL template.
- The `splunk/searches/` directory must contain **no** `apply onnx:`, `apply <model>`, `fit`, or `score` commands in v0. Future paths live in clearly-named separate templates under `splunk/searches/future/` and are excluded from v0 deployment scripts.
- Using AI Toolkit, MLTK, ONNX import, `fit`, `apply`, or `score` in the v0 scoring path invalidates the no-ML-app premise. If AI Toolkit or MLTK are installed on the thin client for a later phase, v0 remains valid only if its scoring/deployment artifacts still prove the no-ML-app path and a new spec (`v1-...`) explicitly re-resolves any ML-app deployment path question.

---

## 13. Weak-label honesty fence

Because `label_binary = 1` is a working-model proxy and not malicious ground truth, every place the label surfaces externally must carry that context:

- The model artifact's `training_metadata` includes `label_rule_id` and a short human-readable `label_rule_description`.
- The local report's G2 section reproduces the rule text verbatim.
- The Splunk scoring template's header comment includes a one-line "label is a working-model positive proxy, not malicious ground truth" disclaimer.
- The holdout fixture's filename includes `proxy` (e.g. `tamperguard_windows_holdout_proxy.csv`) so a downstream reader does not assume curated ground truth.

Metrics — accuracy, precision, recall, F1, confusion matrix — are reported only as plumbing diagnostics. They must appear in the report under a heading explicitly named "Plumbing diagnostics (not detection quality)".

---

## 14. Reproducibility requirements

- Pin a `random_seed` in the training script. Record it in the artifact.
- Pin `sklearn` and `python` versions in the artifact's `training_metadata`. The verification harness asserts the runtime versions match.
- The extraction script computes a `data_fingerprint` from `(sorted window_ids, sha256 of sorted-feature-row bytes)` and writes it to the artifact's `model_version`.
- The label rule is identified by `label_rule_id` and a fingerprint of the rule's source code (a SHA-256 of the function bytes is acceptable). Changing the rule changes the fingerprint changes `model_version`.

A re-run that produces a different `model_version` from the same private inputs and same git SHA is a reproducibility bug. Investigate before treating the new run as valid.

---

## 15. Known false-greens (a non-exhaustive checklist)

Each of these will *look* like a passing v0 run. Each must be excluded by a named gate.

| Failure mode | Why it looks green | Gate that catches it |
|---|---|---|
| Extractor produces all-zero features | Local and SPL both score `sigmoid(intercept)`; equivalence trivially holds | G2 (non-degeneracy) |
| Trained model collapses to constant prediction | Per-row equivalence holds for both classes | G2 |
| Holdout overlaps training set | Metrics look great, equivalence still passes | G3 (holdout integrity) |
| Holdout CSV reorders feature columns silently | SPL `eval` with positional `feature_*` reorder hides drift | G4 (feature_order byte match) |
| `fillnull value=0 feature_*` masks a missing column | Local fixture had the column; SPL fixture didn't | G4 + §6.4 column manifest check |
| String-typed `feature_*` from `inputlookup` | Implicit coercion mostly works, fails on edge values | §6.4 explicit `tonumber()` |
| Threshold edited in template but not in artifact | Probability matches; prediction disagrees | G6b (100% prediction agreement) |
| Splunk version drifted to a newer build with different `exp()` semantics | Equivalence breaks on extremes only | §8.4 version pin + §6.4 score envelope |
| MCP write succeeded but ended up in wrong app namespace | Splunk scoring runs against last week's artifact | G5 read-back by name + SHA-256 |
| Public-safety scan disabled to ship faster | No hits because no scan ran | G7 + CI |
| Report claims tamper detection because the writer skimmed §3 | Looks fine to a reader; violates the whole framing | §3 explicit forbidden claims |

---

## 16. Open implementation questions (narrowed)

Preserved from the original spec, sharpened:

1. **Window-volume verification.** Run the extractor on the last 30 days of `_audit` + `_configtracker` and report the actual G1 numbers before training. If G1 fails, decide between widening the window (e.g. `actor_120m`) or relaxing the proxy rule. Do not lower G1's class-count minimums.
2. **Concrete weak-label rule.** Pick exactly one rule for the first run, document it in `label_rule_description`, and freeze its `label_rule_id`. Resist the temptation to ensemble several heuristics in v0.
3. **Concrete MCP write path.** Pick exactly one of §8.1's three options for the first deployment. Record the choice in the deploy log.
4. **Equivalence tolerance empirical validation.** Run §6.2's 1e-6 tolerance on a synthetic fixture first to confirm it is achievable in this Splunk build. If not, file the relaxation with a reason before applying it to private data.

---

## 17. End-state definition

v0 is complete when, on a clean checkout, a documented sequence of scripts can:

1. Extract windows from the private Splunk indexes.
2. Compute a deterministic holdout split.
3. Train a logistic regression model and emit the bundled artifact.
4. Render a parameterized SPL scoring template from the artifact.
5. Have Hermes deploy the artifact + held-out fixture lookup to `ai_tamperguard` via an approved write path.
6. Trigger Splunk-side scoring of the held-out fixture.
7. Pull results back via MCP and run the verification harness.
8. Produce a report that passes G1–G8.
9. Cleanly roll back every artifact deployed in step 5.

If any of those nine steps requires manual UI clicks, undocumented edits, or "just this once" exceptions, v0 is not yet complete — it is a rehearsal.
