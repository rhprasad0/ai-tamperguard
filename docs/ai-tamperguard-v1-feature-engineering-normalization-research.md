# AI TamperGuard v1 Feature Engineering and Normalization Research

## Executive summary

**Closeout note:** this research helped inform the final engineering call to stop before Splunk deployment. The feasible path below is retained as future-work guidance; it is not a claim that v1 was deployed.

AI TamperGuard v1 is a good fit for a conservative Splunk-side inference path because the current dataset is already numeric, compact, and behavior-window shaped.

For the 5,000-row live batch `all_scenarios_5k_live_20260526T201126Z`:

- Rows: **5,000**
- Feature columns: **60**
- Binary-like features observed in the current CSV: **48 / 60**
- Count/bucket features observed in the current CSV: **12 / 60**
- Current model allowlist: **6 features**

The recommended next step is **not** to throw all 60 columns into a model. The safer path is:

```text
raw normalized Splunk events
  → deterministic behavior-window features
  → small leakage-reviewed model feature set
  → explicit normalization/scaler artifact
  → CPU-safe Splunk scoring SPL
  → alert when probability >= threshold
```

Splunk can handle this if the deployed model is kept SPL-friendly: logistic regression, linear scorecard, or another model that can be represented as basic arithmetic over numeric fields.

## Research-backed Splunk constraints

Splunk is capable of the feature extraction and normalization needed for this v1 inference path, but the deployment should stay within normal SPL mechanics unless AI Toolkit / MLTK availability is confirmed.

Relevant Splunk capabilities:

| Capability | Why it matters | Source |
|---|---|---|
| `eval` creates fields from mathematical, string, and boolean expressions. | Supports normalization, clipping, ratios, linear scores, and logistic probability math. | [Splunk eval docs](https://help.splunk.com/en/splunk-enterprise/search/spl-search-reference/10.4/search-commands/eval) |
| `stats`, `eventstats`, and `streamstats` compute summary, inline aggregate, and running statistics. | Supports behavior-window aggregation, actor baselines, peer baselines, and time-ordered features. | [Splunk stats/eventstats/streamstats docs](https://help.splunk.com/en/splunk-cloud-platform/search/search-manual/10.4.2604/calculate-statistics/use-the-stats-command-and-functions) |
| Splunk evaluation functions include math and conditional functions such as `case`, `coalesce`, `exp`, `log`, and `sqrt`. | Supports null handling, clipping, log transforms, z-scores, and sigmoid probability. | [Splunk evaluation functions docs](https://help.splunk.com/en/splunk-enterprise/search/spl-search-reference/10.4/evaluation-functions/evaluation-functions) |
| AI Toolkit `fit` and `apply` can train/apply models, but they are app-dependent and not intended for real-time searches. | Useful later, but not required for the first v1 deployable inference path. | [Splunk AI Toolkit fit/apply docs](https://help.splunk.com/en/splunk-enterprise/apply-machine-learning/use-ai-toolkit/5.6.4/ai-toolkit-commands-macros-and-visualizations/about-the-fit-and-apply-commands) |
| AI Toolkit preprocessing supports `StandardScaler`. | Confirms scaling is a normal Splunk ML workflow, but we can also export scaler params and apply them with plain SPL. | [Splunk ML data preparation docs](https://help.splunk.com/en/splunk-enterprise/apply-machine-learning/use-ai-toolkit/5.7.3/prepare-and-preprocess-your-data/preparing-your-data-for-machine-learning) |

## Deployment answer

Yes, the Splunk inference pipeline can handle the proposed feature engineering and normalization **if** we keep the model artifact explicit and simple.

Recommended first deployment path:

```text
No-ML-app / CPU-safe path
  - scheduled search
  - SPL feature extraction
  - lookup-backed scaler/model metadata
  - eval-based score/probability
  - Splunk alert on threshold
```

Avoid for the first deployment:

- dynamic Python scoring inside Splunk;
- broad custom scripted commands;
- depending on MLTK/AI Toolkit unless already installed and tested;
- tree/boosting/neural models that require a runtime more complex than SPL math;
- scoring every `feature_*` column by default.

## Current feature profile

The current 5k CSV is operationally friendly:

| Observation | Meaning |
|---|---|
| Most features are binary or near-binary. | Many should stay as `0/1` and do not need scaling. |
| Count ranges are currently small. | Scaling is not urgent for the current corpus, but live data may widen ranges. |
| Current allowed features are behavior-shape features. | Good for conservative first deployment. |
| Many strong semantic features are denylisted. | Good: they may encode scenario-generator signatures or lab-specific paths. |

Current allowlisted features from `v1/config/feature_policy_v1.yaml`:

| Feature | Observed role |
|---|---|
| `feature_action_switch_count` | Behavior sequence shape. |
| `feature_distinct_object_type_count` | Breadth of touched object types. |
| `feature_distinct_surface_count` | Breadth across source surfaces. |
| `feature_event_count` | Window activity volume. |
| `feature_search_count` | Investigation/search activity. |
| `feature_visibility_object_read_count` | Reads of detection/visibility artifacts. |

## Appropriate feature engineering families

### 1. Activity volume and breadth features

These are the safest first family because they describe behavior shape without directly encoding labels or scenario IDs.

Current examples:

- `feature_event_count`
- `feature_search_count`
- `feature_distinct_object_type_count`
- `feature_distinct_surface_count`
- `feature_action_switch_count`
- `feature_visibility_object_read_count`

Recommended additions:

| Proposed feature | Definition | Splunk feasibility | Notes |
|---|---|---|---|
| `feature_write_action_count` | Count of `modify`, `disable`, `enable`, `create`, `delete`. | Easy with `stats count(eval(...))`. | Useful as raw context; may need leakage review before scoring. |
| `feature_search_fraction` | `feature_search_count / max(feature_event_count, 1)`. | Easy with `eval`. | Normalizes search intensity by activity volume. |
| `feature_visibility_read_fraction` | `feature_visibility_object_read_count / max(feature_event_count, 1)`. | Easy with `eval`. | Good candidate for model input. |
| `feature_object_breadth_per_event` | `distinct_object_type_count / max(event_count, 1)`. | Easy with `eval`. | Helps compare windows of different sizes. |
| `feature_surface_breadth_per_event` | `distinct_surface_count / max(event_count, 1)`. | Easy with `eval`. | Captures multi-surface behavior density. |
| `feature_sensitive_surface_count` | Count of events from sensitive control-plane surfaces. | Easy if `source_surface` taxonomy is stable. | Useful for context and model experiments. |

Recommended stance: add ratios and capped/log counts before entropy-style features.

### 2. Sequence and transition features

Tamper-like behavior is often a sequence, not a single event.

Current examples:

- `feature_search_then_modify_flag`
- `feature_modify_then_requery_flag`
- `feature_search_modify_report_sequence_flag`
- `feature_state_changed_after_evidence_access_flag`
- `feature_downstream_mismatch_after_visibility_change_flag`

Recommended additions:

| Proposed feature | Definition | Splunk feasibility | Notes |
|---|---|---|---|
| `feature_search_to_write_seconds_min` | Minimum time between evidence/search action and later write action. | Feasible with ordered event logic. | Use `log1p` or bucket before scoring. |
| `feature_write_to_requery_seconds_min` | Minimum time from write/change to later search. | Feasible. | Helps identify validation/requery behavior. |
| `feature_evidence_to_visibility_change_count` | Count of evidence/review-to-change transitions. | Feasible. | Count version of an existing sequence idea. |
| `feature_repeated_change_after_read_count` | Number of write actions following prior read/search in the same window. | Feasible. | More expressive than one binary flag. |
| `feature_ordered_stage_count` | Number of expected stages observed in correct order. | Feasible. | Explainable and robust. |

Recommended stance: keep simple binary flags for v1 stability, then add count/gap features once equivalence tests pass.

### 3. Actor-relative baseline features

These will likely be more useful for live detection than absolute counts.

Instead of asking:

> Did this actor do three searches?

Ask:

> Is this actor doing more detection/control-plane activity than their own recent baseline?

Recommended features:

| Proposed feature | Definition | Splunk feasibility | Required state |
|---|---|---|---|
| `feature_actor_event_count_z_7d` | Current event count vs actor trailing baseline. | Feasible. | Actor baseline lookup or summary index. |
| `feature_actor_search_count_z_7d` | Current search count vs actor baseline. | Feasible. | Actor baseline lookup. |
| `feature_actor_surface_count_z_7d` | Current source-surface breadth vs actor baseline. | Feasible. | Actor baseline lookup. |
| `feature_actor_write_rate_z_7d` | Current write/change rate vs actor baseline. | Feasible. | Actor baseline lookup. |
| `feature_actor_object_type_novelty_count` | Count of object types not recently seen for actor. | Feasible. | Actor/object history lookup. |
| `feature_actor_first_seen_surface_flag` | Whether actor touched a new source surface. | Feasible. | Actor/surface history lookup. |

Recommended implementation pattern:

```text
nightly baseline job
  → actor_baseline_lookup.csv or KV Store

live scoring job
  → extract current features
  → lookup actor baseline
  → compute z-scores/deltas
  → score
```

Do **not** compute baselines ad hoc from the same scored batch. That risks train/serve skew and unstable alert behavior.

### 4. Role / peer-group normalized features

Actor-specific baselines can be sparse. Peer-group baselines are a useful fallback.

Example groups:

- `admin`
- `analyst`
- `service_account`
- `agent`
- `system`

Recommended features:

| Proposed feature | Definition |
|---|---|
| `feature_role_event_count_z` | Current actor/window volume vs role-family norm. |
| `feature_role_search_count_z` | Current search count vs role-family norm. |
| `feature_role_config_change_z` | Current config-change activity vs role-family norm. |
| `feature_role_surface_breadth_z` | Current source-surface breadth vs role-family norm. |
| `feature_role_visibility_read_z` | Current visibility-object reads vs role-family norm. |

This is safer than using raw `actor_id` as a model feature.

### 5. Explanation and analyst context features

Some features are semantically strong but may be too generator-signature-like for the model.

Examples:

- `feature_permission_denied_count`
- `feature_capability_denied_count`
- `feature_detection_disable_count`
- `feature_risk_score_tuning_count`
- `feature_macro_filter_change_count`
- `feature_downstream_omission_count`

Recommended stance:

```text
Use these first as alert context and analyst explanation fields.
Only promote them to model features after leakage tests and holdout validation pass.
```

This gives analysts useful evidence without letting the model cheat on lab-specific scenario construction.

## Normalization strategy

### Feature-type-specific normalization

| Feature type | Examples | Recommended normalization |
|---|---|---|
| Binary flags | `*_flag`, many 0/1 `*_count` fields | Leave unchanged as `0/1`. |
| Small bounded counts | `feature_event_count`, `feature_search_count` | `log1p(x)` or standard scaling. |
| Distinct counts | `feature_distinct_*_count` | Standard scaling or clipped min/max scaling. |
| Time gaps | `*_seconds_min`, `*_min_gap_*` | Bucket or `log1p(seconds)`, then optionally standardize. |
| Ratios | search fraction, write fraction, visibility-read fraction | Clip to sane bounds, then optionally standardize. |
| Rarity buckets | `*_rarity_bucket` | Treat carefully; keep ordinal only if semantics are stable. |
| Actor/role z-scores | `*_z_7d`, `*_z_30d` | Already normalized; clip to e.g. `[-5, 5]`. |
| Novelty features | first-seen flags, unseen object counts | Binary or capped count. |

### Recommended v1.5 normalization policy

```text
binary flags: unchanged
raw counts: log1p + standardize
ratio features: clip + standardize
time gaps: log1p or buckets + standardize
baseline z-scores: clip only
bucket features: keep only if bucket semantics are stable
```

### Scaler artifact shape

Export scaler/model parameters as a private artifact and optionally as a Splunk lookup.

Example CSV shape:

```csv
feature_name,transform,mean,stdev,clip_low,clip_high,coefficient
feature_event_count,log1p_standard,1.49,0.12,0,10,0.42
feature_search_count,log1p_standard,0.52,0.31,0,10,0.77
feature_action_switch_count,standard,2.19,0.75,0,10,0.31
```

Example JSON shape:

```json
{
  "model_version": "ai_tamperguard_v1_YYYYMMDD",
  "threshold": 0.70,
  "intercept": -1.23,
  "features": [
    {
      "name": "feature_event_count",
      "transform": "log1p_standard",
      "mean": 1.49,
      "stdev": 0.12,
      "clip_low": 0,
      "clip_high": 10,
      "coefficient": 0.42
    }
  ]
}
```

The deployed Splunk search should use the exact exported feature order and parameters. Do not infer feature order from column sorting at serve time.

## Splunk inference feasibility

### Supported and recommended

Splunk can handle:

- `fillnull value=0`
- count and distinct-count aggregation with `stats`
- ratios with `eval`
- clipping with `case()` or `if()`
- `log1p` using `log(x+1)`
- z-score normalization with `(x - mean) / stdev`
- logistic probability with `1/(1+exp(-score))`
- alert thresholding with `where probability >= threshold`

Example scoring shape:

```spl
... normalized event search ...
| bin _time span=15m
| stats
    count as feature_event_count
    count(eval(action="search")) as feature_search_count
    dc(object_type) as feature_distinct_object_type_count
    dc(source_surface) as feature_distinct_surface_count
    count(eval(object_role="detection_or_visibility_artifact" AND (action="read" OR action="search"))) as feature_visibility_object_read_count
  by actor_id _time
| fillnull value=0 feature_event_count feature_search_count feature_distinct_object_type_count feature_distinct_surface_count feature_visibility_object_read_count
| eval feature_event_count_clipped=case(feature_event_count<0,0,feature_event_count>10,10,true(),feature_event_count)
| eval feature_event_count_norm=(log(feature_event_count_clipped+1)-1.49)/0.12
| eval feature_search_count_clipped=case(feature_search_count<0,0,feature_search_count>10,10,true(),feature_search_count)
| eval feature_search_count_norm=(log(feature_search_count_clipped+1)-0.52)/0.31
| eval score=-1.23
    + 0.42*feature_event_count_norm
    + 0.77*feature_search_count_norm
    + 0.31*feature_distinct_object_type_count
| eval probability=1/(1+exp(-score))
| eval ai_tamperguard_prediction=if(probability>=0.70,1,0)
| where ai_tamperguard_prediction=1
```

### Possible but not first-choice

AI Toolkit / MLTK can support model application and preprocessing, including StandardScaler-style workflows, but use this only after app availability and permissions are verified.

Reasons not to depend on it for the first deployable loop:

- app availability may differ by Splunk instance;
- `fit` and `apply` are not meant for real-time searches;
- MLTK can perform implicit preprocessing that may surprise train/serve parity;
- the no-ML-app path already proves the local-training to Splunk-inference loop.

### Not recommended for v1

Avoid for the first live alert:

- Python scripted scoring commands;
- external lookup scripts for the core model path;
- tree ensembles that cannot be represented cleanly in SPL;
- neural models;
- dynamic category encoders over live high-cardinality fields;
- direct `actor_id`, `scenario_run_id`, path ID, prompt ID, or label-family-derived features.

## Recommended feature contract

Split the feature contract into three lists.

```yaml
model_features:
  - normalized, leakage-reviewed, scoreable fields

normalization_features:
  - raw fields required to compute normalized model features

alert_context_features:
  - useful analyst evidence shown in alerts but not scored
```

Example:

```yaml
model_features:
  - feature_event_count_log1p_z
  - feature_search_count_log1p_z
  - feature_action_switch_count_z
  - feature_distinct_surface_count_z
  - feature_visibility_object_read_count

normalization_features:
  - feature_event_count
  - feature_search_count
  - feature_action_switch_count
  - feature_distinct_surface_count

alert_context_features:
  - feature_permission_denied_count
  - feature_detection_disable_count
  - feature_macro_filter_change_count
  - feature_downstream_omission_count
```

This lets the alert be explanatory without allowing the model to depend on risky or lab-specific context fields.

## Recommended implementation sequence

### Phase 1: Add scaler/model artifact support

Produce a deterministic artifact containing:

- `model_version`
- feature order
- transform type per feature
- clip bounds
- mean/stdev or min/max parameters
- intercept
- coefficients
- threshold
- training data/code hashes

### Phase 2: Add transformed features

Add Tier 1 engineered features:

- `feature_search_fraction`
- `feature_visibility_read_fraction`
- `feature_object_breadth_per_event`
- `feature_surface_breadth_per_event`
- `feature_event_count_log1p`
- `feature_search_count_log1p`
- `feature_action_switch_count_log1p`

Then add normalized versions for model input:

- `*_z`
- `*_log1p_z`
- or explicitly named transformed fields.

### Phase 3: Generate Splunk scoring SPL

Create a script that reads the scaler/model artifact and emits a deterministic scoring SPL snippet.

This avoids hand-written coefficient drift and ensures the Splunk search uses the same feature order as local training.

### Phase 4: Run equivalence tests

Required gates:

1. Local Python scoring and Splunk scoring use the same input fixture.
2. Max score residual is below tolerance.
3. Max probability residual is below tolerance.
4. Prediction mismatches are zero.
5. Alert rows include model version and feature-order hash.

### Phase 5: Add actor/role baselines

Only after Phase 1–4 pass:

- create actor baseline lookup / summary index;
- create role-family baseline lookup;
- add z-score and novelty features;
- repeat leakage and equivalence validation.

## Deployment alert shape

A live positive alert should include:

| Field | Purpose |
|---|---|
| `model_version` | Identifies deployed model/scaler artifact. |
| `feature_order_hash` | Confirms exact scoring feature order. |
| `ai_tamperguard_score` | Raw linear/logit score. |
| `ai_tamperguard_probability` | Probability or calibrated risk score. |
| `ai_tamperguard_prediction` | Positive/negative prediction. |
| `actor_id` or actor surrogate | Investigation pivot. |
| `window_start`, `window_end` | Time window. |
| `top_contributing_features` | Analyst explanation for linear model. |
| `alert_context_features` | Non-scored evidence fields. |
| `drilldown_search` | Safe parameterized search back to evidence. |

Do not include raw credentials, tokens, private hostnames, raw private object names, or private paths.

## Bottom-line recommendation

Use a small, normalized, leakage-reviewed feature set for the model and keep the broader 60-feature catalog for explanation and future experiments.

Best v1.5 direction:

```text
1. Keep the current six allowlisted behavior-shape features.
2. Add ratio and log-count transforms.
3. Export scaler + coefficients + threshold.
4. Generate scoring SPL from the artifact.
5. Prove local-vs-Splunk equivalence.
6. Add actor/role baselines only after the basic loop is stable.
```

Conservative claim:

> AI TamperGuard can compute normalized behavior-window features from live Splunk control-plane telemetry, score those windows with a CPU-safe deployed model artifact, and raise a Splunk alert when a window crosses the current synthetic/lab positive threshold.

Avoid claiming production tamper detection until the model is validated against stronger real-world or red-team-derived ground truth.
