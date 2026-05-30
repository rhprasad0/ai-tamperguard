# AI TamperGuard Project Closeout

## Final engineering call

AI TamperGuard is being stopped at the **v1 evidence/data plumbing milestone** rather than pushed into Splunk deployment.

The original hypothesis was:

> Train a custom Python model locally, deploy it into Splunk, and flag cases where an AI agent appears to be tampering with Splunk monitoring, auditability, alerting, or evidence trails.

The project proved a meaningful slice of that loop, but the deployment step is intentionally not being claimed. The current judgment is that the Splunk-side deployment path is not worth turning into a production-ish claim for this repo: the SPL scoring shape is mechanically simple, while the real difficulty is feature normalization, train/serve parity, leakage control, and proving that live inference does not silently drift from the local pipeline. That is where the sharp rocks live. Tiny crab-walk, giant rake field.

## What was built

### v0: local-training to Splunk-scoring smoke test

The v0 milestone built a small end-to-end smoke test:

```text
Splunk lab data
→ local feature extraction
→ deterministic train/holdout split
→ local baseline model training
→ SPL scoring artifact
→ Splunk-side holdout scoring
→ local-vs-Splunk equivalence verification
→ public-safety checks
```

v0 was useful because it made the deployment boundary explicit. It was never a production detection-quality claim.

### v1: scenario harness and live 5k behavior-window corpus

The v1 milestone built a larger scenario-driven harness around synthetic, public-safe Splunk/SOC behavior:

```text
scenario catalog + path templates + prompt pack
→ generated run manifest
→ live Splunk seed/read-back capture
→ public-safe raw events
→ actor/window training CSV
→ leakage and public-safety validation
```

The primary live validation batch was `all_scenarios_5k_live_20260526T201126Z`.

Recorded validation evidence:

- **5,000** live scenario runs seeded and captured.
- **17,218** expected events verified by Splunk read-back and captured as public-safe rows.
- **5,000** behavior-window training rows produced.
- **71** total training CSV columns.
- **60** `feature_*` columns.
- Binary label distribution: **3,623** label `0`, **1,377** label `1`.
- Outcome distribution: **1,650** `benign`, **950** `failed`, **950** `successful_synthetic`, **625** `attempted`, **425** `needs_review`, **400** `blocked`.
- Full v1 test suite passed at the time of final live validation: `uv run --directory v1 pytest -q` reported **164 passed**.
- Public-safety scan passed across the 5k reports/training artifacts at the time of validation.

Important caveats:

- The corpus is synthetic and lab-based.
- Labels are weak working-model proxies, not malicious ground truth.
- No Openclaw grading was performed for the 5k dataset milestone.
- The run proves live plumbing and public-safe feature generation, not real-world Splunk tamper detection.

### AutoResearch / technique bakeoff

A bounded external technique bakeoff was added for the 5k training CSV.

The best eligible candidate in the final recorded bakeoff was:

- `logistic_regression/default_balanced`
- validation AP: **0.6515**
- validation balanced accuracy: **0.7825**
- deployability class: `direct_spl`
- leakage verdict: `honest`
- selected because no simpler eligible candidate justified replacement

The bakeoff also produced a direct linear model artifact and verified local exported-artifact-vs-estimator scoring equivalence for the selected linear artifact.

This is a useful research result, but not a deployment result. The bakeoff does **not** prove Splunk-side scoring equivalence, live alert quality, or production detection value.

## Why deployment is intentionally deferred

The current no-deploy decision is based on engineering judgment, not a single blocker.

Reasons:

1. **The scoring SPL is the easy part.**
   - A logistic regression score can be represented as `intercept + Σ(feature_i * coefficient_i)`, followed by a sigmoid and threshold.
   - That part is almost boring enough to wear a cardigan.

2. **The hard part is live feature parity.**
   - Splunk-side live extraction would need to reproduce the local normalization and windowing pipeline exactly enough to avoid train/serve skew.
   - That includes field mapping, null handling, bucket semantics, actor/window grouping, feature order, and threshold behavior.

3. **The current model only uses a tiny reviewed feature allowlist.**
   - The explicit allowlist currently resolves to six features: `feature_action_switch_count`, `feature_distinct_object_type_count`, `feature_distinct_surface_count`, `feature_event_count`, `feature_search_count`, and `feature_visibility_object_read_count`.
   - Most semantic features remain useful for explanation, but are intentionally denylisted as possible generator-signature or split-population risks until proven safer.

4. **The dataset is still a lab harness output.**
   - The positive/negative labels are scenario-family working labels.
   - The harness demonstrates data generation, normalization, leakage-aware policy, and model selection, not external validity.

5. **Research and implementation risk point in the same direction.**
   - Splunk can support simple arithmetic scoring.
   - But packaging the full normalization and inference pipeline cleanly enough to claim deployment would be a separate project, not the last five yards of this one.

## Final status

**Call:** stop here and archive as a successful experimental milestone.

What can be claimed:

> AI TamperGuard v1 built and validated a public-safe Splunk lab harness that generated 5,000 live-backed behavior windows, ran leakage-aware feature policy checks, and used an AutoResearch-style bakeoff to select a conservative logistic-regression baseline over weak proxy labels.

What should not be claimed:

> AI TamperGuard detects real-world Splunk tampering.

> AI TamperGuard has a production-ready Splunk deployment.

> The selected logistic regression model is validated against real adversaries or real SOC operators.

## Useful repo artifacts

- Root project framing: [`README.md`](../README.md)
- v1 workspace and commands: [`v1/README.md`](../v1/README.md)
- Scenario design: [`scenario-design.md`](scenario-design.md)
- 5k final validation report: [`../v1/reports/5k_runs/all_scenarios_5k_live_20260526T201126Z/final_validation.md`](../v1/reports/5k_runs/all_scenarios_5k_live_20260526T201126Z/final_validation.md)
- Feature engineering / normalization research: [`ai-tamperguard-v1-feature-engineering-normalization-research.md`](ai-tamperguard-v1-feature-engineering-normalization-research.md)
- Feature-to-alerting report: [`ai-tamperguard-v1-feature-to-splunk-alerting-report.md`](ai-tamperguard-v1-feature-to-splunk-alerting-report.md)
- External technique bakeoff docs: [`v1-autoresearch-technique-bakeoff.md`](v1-autoresearch-technique-bakeoff.md)
- Final 5k bakeoff report: [`../v1/reports/technique_bakeoffs/all_scenarios_5k_live_20260526T201126Z_fixed_csv_autoresearch_probe/bakeoff-report.md`](../v1/reports/technique_bakeoffs/all_scenarios_5k_live_20260526T201126Z_fixed_csv_autoresearch_probe/bakeoff-report.md)

## If this project is revived later

Treat revival as a new phase, not a continuation of v1 deployment.

The next serious phase would need:

1. A Splunk app or saved-search package that owns the live normalization and feature extraction path.
2. A fixed model artifact format with feature order, scaler/null policy, coefficients, threshold, and hashes.
3. A held-out fixture suite where local Python scoring and Splunk-side scoring match within tolerance.
4. A live smoke where known positive and negative public-safe scenarios alert or do not alert as expected.
5. Stronger labels, preferably with paired controls and external holdouts that are not scenario-generator answer keys.

Until then, this repo should be read as an engineering experiment with receipts, not as a detector product.
