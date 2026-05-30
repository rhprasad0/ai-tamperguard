# AI TamperGuard v1 Feature Mapping and Live Alerting Report

Generated for the 5,000-row live validation batch `all_scenarios_5k_live_20260526T201126Z`.

## Executive summary

**Closeout note:** this report remains as research/design documentation. After reviewing the implementation risk, the project stopped short of deploying the custom model into Splunk. Treat the alerting path below as a future-project sketch, not as completed project scope.

AI TamperGuard v1 turns live Splunk-backed, public-safe behavior events into **actor/window feature rows**. The 5k batch produced:

- **5,000** behavior-window rows
- **60** `feature_*` columns
- **71** total CSV columns
- **1,377** current positive labels and **3,623** current negative labels
- live read-back/capture validation for **5,000** runs and **17,218** events

The important deployment point is:

> The deployed alert must not score raw labels, outcomes, scenario IDs, path IDs, prompt metadata, or manifest metadata. It should score only the reviewed feature vector for a live actor/window, then raise an alert when the model probability/score crosses the configured positive threshold.

The current model-facing feature policy is intentionally conservative. `v1/config/feature_policy_v1.yaml` allows only these six features for the leakage-aware baseline model:

| Feature | Why it is currently allowed |
|---|---|
| `feature_action_switch_count` | Behavioral shape, not a direct scenario label. |
| `feature_distinct_object_type_count` | Breadth of touched object types. |
| `feature_distinct_surface_count` | Breadth of Splunk/control-plane surfaces. |
| `feature_event_count` | Window activity volume. |
| `feature_search_count` | Investigation/search activity count. |
| `feature_visibility_object_read_count` | Reads of detection/visibility artifacts. |

The remaining features are still valuable for analyst explanation and future model experiments, but the current policy deny-lists most of them as possible generator-signature or split-population features until they are proven safe under holdout and leakage tests.

## Pipeline: from Splunk to alert

```text
Live Splunk data
  → normalized public-safe event rows
  → actor/window aggregation, usually 15 minutes
  → feature vector in the exact model feature order
  → model scoring
  → alert if score/probability >= threshold
  → analyst drilldown back to Splunk evidence
```

For deployment, the live path should be packaged as a scheduled Splunk search or app-scoped saved search that performs four phases:

1. **Collect live control-plane events** from approved indexes/sourcetypes.
2. **Normalize** those events to the TamperGuard event schema.
3. **Aggregate** by actor and time window into `feature_*` values.
4. **Score and alert** using the deployed model artifact and threshold.

## Source surfaces and Splunk mapping

The normalized event schema abstracts Splunk data into a small number of public-safe source surfaces. Those surfaces are the bridge between real Splunk events and model features.

| Normalized source surface | Splunk-side source | Typical evidence represented |
|---|---|---|
| `splunk_audit` | `index=_audit sourcetype=audittrail` | Searches, REST/control-plane actions, capability denials, auth/session/admin activity. |
| `splunk_configtracker` | `index=_configtracker sourcetype=splunk_configuration_change` | Saved-search, alert, dashboard, macro, lookup, input, transform, model, and app config changes. |
| `splunk_metadata` | Metadata/REST inventory searches | Index/sourcetype/source discovery, metadata enumeration, object inventory. |
| `splunk_knowledge_objects` | REST/config lookup of saved searches, dashboards, macros, lookups, alerts, models | Discovery/read context around knowledge objects. |
| `synthetic_control_plane` | Lab-only operator notes / public-safe synthetic fixtures | Public-safe reports, blocked-control markers, scenario verification notes. In production this should map to a real but safe case-management or analyst-note surface if used. |
| `agentops` | AI-agent telemetry index, if enabled | Agent/tool activity around analyst workflows; optional for v1 scoring. |

## Non-feature columns: never score these

The training CSV contains useful metadata that must stay out of the model feature vector:

| Column | Use | Scoring status |
|---|---|---|
| `window_id` | Unique derived row ID | Do not score. |
| `scenario_run_id` | Run identity / join key | Do not score; leakage risk. |
| `reset_id` | Lab reset identity | Do not score; leakage/provenance. |
| `actor_id` | Pseudonymous actor ID | Do not score in current baseline. Use for grouping/drilldown only. |
| `window_type` | Window grain, e.g. `actor_15m` | Do not score unless model is trained per-grain. |
| `window_start_relative_sec`, `window_end_relative_sec` | Relative lab window timing | Do not score in live deployment. Use live `_time` windows instead. |
| `label_binary`, `label_family`, `label_source`, `label_confidence` | Training labels | Never present in live scoring input. |
| `outcome` | Scenario execution metadata | Never present in live scoring input. |
| `split_id` | Train/validation/test split | Never present in live scoring input. |

## Feature catalog and Splunk mapping

The table below describes the current 60 derived feature columns in the 5k dataset. “Normalized input” names the event fields the feature uses; “Splunk mapping” explains where those fields should come from in live Splunk.

| Feature | Meaning | Normalized input | Splunk mapping |
|---|---|---|---|
| `feature_event_count` | Number of normalized events in the actor/window. | event row count | Count rows after normalizing `_audit`, `_configtracker`, metadata, and optional agent/control-plane sources. |
| `feature_search_count` | Count of investigation/search events. | `action=search` | `_audit` search/audittrail events, especially searches over protected or relevant evidence. |
| `feature_config_change_count` | Count of write/change actions. | `action in modify, disable, enable, create, delete` | `_configtracker` config changes and REST/admin audit events. |
| `feature_visibility_object_read_count` | Reads/searches of detection or visibility artifacts. | `object_role=detection_or_visibility_artifact`, `action in read, search` | Reads/discovery of saved searches, alerts, dashboards, macros, lookups, models, inputs, transforms. |
| `feature_visibility_object_write_count` | Writes to detection or visibility artifacts. | `object_role=detection_or_visibility_artifact`, write actions | `_configtracker` changes to saved searches, alerts, dashboards, macros, lookups, inputs, transforms, model outputs. |
| `feature_saved_search_modify_count` | Saved-search modification count. | `object_type=saved_search`, `action=modify` | `_configtracker` changes to saved searches / correlation searches. |
| `feature_dashboard_modify_count` | Dashboard modification count. | `object_type=dashboard`, `action=modify` | `_configtracker` dashboard XML/view changes. |
| `feature_alert_modify_count` | Alert modification/disable count. | `object_type=alert`, `action in modify, disable` | `_configtracker` alert/correlation-search changes and audit REST changes. |
| `feature_permission_denied_count` | Count of explicitly denied events. | `status=denied` | `_audit` capability/REST denial events or bounded control-plane denial markers. |
| `feature_distinct_object_type_count` | Breadth of object types touched. | distinct `object_type` | Distinct normalized object classes such as index, saved_search, alert, dashboard, lookup, macro, input, token. |
| `feature_search_then_modify_flag` | Search occurred before a later modify/disable action. | ordered `action=search` before write action | Time-order `_audit` searches before `_configtracker` modifications. |
| `feature_modify_then_requery_flag` | Modify/disable occurred before later search. | ordered write action before `search` | Re-query behavior after config change, from `_configtracker` then `_audit`. |
| `feature_actor_admin_context_flag` | Window includes admin-role context. | `actor_role_family=admin` | Role/capability mapping from Splunk user/RBAC context. Denylisted for current model because it may be lab-signature-like. |
| `feature_capability_denied_count` | Denied capability/status count. | `capability_check_result=denied` or `status=denied` | `_audit` capability failures, REST 403-ish outcomes, or bounded synthetic denied actions. |
| `feature_capability_allowed_change_count` | Allowed capability check followed by write action. | `capability_check_result=allowed`, write action | Audit/RBAC context plus configtracker write event. |
| `feature_permission_probe_before_change_flag` | Permission probe occurred before a write action. | ordered `permission_probe` before write action | Audit/control-plane denial/probe followed by later config change. |
| `feature_high_criticality_object_touch_count` | Touches of high-criticality objects. | `object_criticality=high` | Normalizer must assign criticality to detection, alert, input, token, route, index, or model objects. |
| `feature_high_criticality_object_write_count` | Writes to high-criticality objects. | high criticality plus write action | Configtracker/audit writes to high-criticality knowledge objects or ingest/routing controls. |
| `feature_detection_disable_count` | Disable lifecycle count. | `detection_lifecycle_stage=disabled` or `action=disable` | Alert/correlation-search disable operations. |
| `feature_detection_throttle_or_narrow_count` | Detection throttled or narrowed. | `detection_lifecycle_stage=throttled` or `after_state_family=narrow` | Saved-search/alert SPL narrowing, throttle/suppression changes. |
| `feature_global_visibility_object_write_count` | Writes to globally visible detection artifacts. | `object_visibility_scope=global`, detection artifact, write action | Global saved searches, alerts, dashboards, macros, transforms. |
| `feature_visibility_decrease_count` | Events that reduce downstream visibility. | `visibility_delta=decrease` | Normalizer must infer from disable/narrow/throttle/routing changes. |
| `feature_large_change_count` | Large magnitude changes. | `change_magnitude_bucket=large` | Disable/delete or broad high-impact changes. |
| `feature_enabled_to_disabled_count` | Enabled state changed to disabled. | `before_state_family=enabled`, `after_state_family=disabled` | Configtracker before/after diff for alerts/searches/detections. |
| `feature_broad_to_narrow_count` | Broad detection/search changed to narrow. | `before_state_family=broad`, `after_state_family=narrow` | SPL/filter/macro/lookup narrowing after evidence access. |
| `feature_state_changed_after_evidence_access_flag` | Visibility object changed after evidence search. | `evidence_chain_stage=search` before `change_visibility_object` | `_audit` search followed by `_configtracker` change in the same actor/window. |
| `feature_protected_evidence_seen_count` | Count of events where protected evidence was seen. | `protected_evidence_seen=true` | Derived from searches against protected/audit/evidence surfaces. In production, this should be rule-based and conservative. |
| `feature_downstream_omission_count` | Downstream report/artifact omits relevant evidence. | `downstream_artifact_matches_evidence=omits_relevant_evidence` | Lab/reporting/case-management comparison; in production requires explicit report/case evidence matching. |
| `feature_downstream_contradiction_count` | Downstream report contradicts evidence. | `downstream_artifact_matches_evidence=contradicts_evidence` | Report/case-note validation against protected evidence. |
| `feature_evidence_then_report_omission_flag` | Evidence search followed by report omission. | search stage plus omitted-evidence report | Protected evidence access followed by inaccurate/missing downstream report. |
| `feature_evidence_target_overlap_count` | Events touching objects related to the evidence under review. | `target_evidence_overlap=true` | Normalizer must map searches and objects to the same synthetic or case entity. |
| `feature_report_write_count` | Count of report/note writes. | `action=write_report` | Synthetic operator note in lab; production case note/report/ticket update if integrated. |
| `feature_search_to_change_min_gap_bucket` | Time gap bucket from search to write/change. | min relative-time gap, search → write | Convert live `_time` to window-relative order and bucket the gap. |
| `feature_change_to_requery_min_gap_bucket` | Time gap bucket from write/change to later search. | min relative-time gap, write → search | Post-change validation/requery behavior. |
| `feature_distinct_surface_count` | Number of source surfaces involved. | distinct `source_surface` | Breadth across `_audit`, `_configtracker`, metadata, knowledge-object, agent/control surfaces. |
| `feature_action_switch_count` | Number of action transitions in sequence. | ordered `action` sequence | Behavior-shape feature independent of exact scenario ID. |
| `feature_search_modify_report_sequence_flag` | Search → modify → report sequence occurred. | ordered actions | Evidence search followed by config change followed by report/write-up. |
| `feature_read_modify_report_sequence_flag` | Read → modify → report sequence occurred. | ordered actions | Knowledge-object read followed by modification and report. |
| `feature_probe_denied_then_report_flag` | Denied probe followed by report. | denied permission probe before `write_report` | Permission/RBAC failure followed by write-up. Current blocked rows usually do not set this. |
| `feature_actor_action_rarity_bucket` | Rarity of dominant actor/action pair within the population. | cross-population actor/action counts | Not stable for live deployment unless computed against a fixed baseline; denylisted in current policy. |
| `feature_object_type_actor_rarity_bucket` | Rarity of actor/object-type pair within the population. | cross-population actor/object counts | Not stable for live deployment unless computed against a fixed baseline; denylisted in current policy. |
| `feature_high_risk_combo_count` | High-criticality write/probe plus visibility decrease or denial. | criticality + action + visibility/denial | Combines configtracker/audit changes with object criticality. |
| `feature_risk_context_review_count` | Risk-context review events. | `sequence_stage=risk_context_review` | ES/ITSI/risk-analysis context review or synthetic equivalent. |
| `feature_intermediate_finding_review_count` | Intermediate finding review count. | `finding_state=intermediate_finding_created` | Notable/intermediate finding lifecycle surface. |
| `feature_suppression_after_creation_count` | Suppression after a finding was created. | `suppression_mode=suppression_after_creation` | ES notable/correlation-search suppression after finding creation. |
| `feature_throttle_before_creation_count` | Throttle before finding creation. | `suppression_mode=throttle_before_creation` | Alert throttle change before finding/notable creation. |
| `feature_suppression_or_throttle_present` | Any suppression/throttle mode present. | suppression mode set | ES alert throttle/suppression state. |
| `feature_notable_hidden_after_creation_count` | Notable hidden from downstream view after creation. | `notable_visibility_delta=hidden_from_mission_control` | ES/ITSI/notable visibility path. |
| `feature_notable_not_created_count` | Notable did not get created due to earlier throttle/suppression. | `notable_visibility_delta=not_created` | Alert/correlation path where suppression prevents downstream finding. |
| `feature_risk_score_tuning_count` | Risk score/severity lowered. | `correlation_search_state=score_lowered` or risk-scoring config writes | ES/RBA correlation search and risk score configuration. |
| `feature_macro_filter_change_count` | Macro/filter changed. | `macro_filter_state in broad,narrow,excludes_synthetic_entity` | Macro/configtracker changes affecting search filters. |
| `feature_lookup_filter_change_count` | Lookup row/filter change count. | `lookup_row_delta_bucket` not none/unknown | Lookup edits that alter classification/filter behavior. |
| `feature_requery_after_change_count` | Re-query after change count. | `sequence_stage=requery_after_change` | Audit search after config change. |
| `feature_audit_config_change_seen_count` | Protected audit/config evidence was observed. | `audit_visibility_state in audit_seen, configtracker_seen` | Confirmation that protected outer evidence saw the activity. |
| `feature_disk_change_gap_count` | Disk/config gap marker. | `audit_visibility_state=disk_change_gap` | Potential config change not reflected in expected audit/configtracker path. Requires careful production semantics. |
| `feature_evidence_to_risk_tuning_sequence_flag` | Evidence/risk review before score lowering. | evidence/review stage before `correlation_search_state=score_lowered` | Search/review followed by RBA/correlation risk tuning. |
| `feature_evidence_to_macro_filter_sequence_flag` | Evidence/risk review before macro exclusion. | evidence/review stage before macro excludes entity | Search/review followed by macro/filter change. |
| `feature_suppression_vs_throttle_disambiguated_flag` | Exactly one suppression mode is present. | exactly one of suppression-after-creation or throttle-before-creation | Distinguishes post-finding suppression from pre-finding throttle. |
| `feature_protected_evidence_agreement_count` | Protected evidence seen and downstream artifact agrees. | `protected_evidence_seen=true`, downstream matches/not_applicable | Useful for benign/control behavior and explanation. |
| `feature_downstream_mismatch_after_visibility_change_flag` | Visibility change followed by report/evidence mismatch. | visibility-change stage before downstream omission/contradiction | Core evidence-laundering / visibility-degradation sequence. |

## Current deployment stance

There are two different feature sets to keep separate:

1. **Dataset feature catalog:** all 60 features above, useful for analysis, explanation, and future experiments.
2. **Current model feature order:** the explicit allowlist in `config/feature_policy_v1.yaml`, currently six features.

For the first deployable alert, use the exact model artifact’s feature order, not “all columns that start with `feature_`.” That avoids silent train/serve skew and avoids accidentally scoring denylisted generator-signature columns.

## Recommended live alert implementation

### Option A: no-ML-app / CPU-safe baseline

This is the preferred first deployment path if Splunk AI Toolkit / MLTK / ONNX support is not already installed.

1. Train locally and export a deterministic model artifact:
   - `model_version`
   - feature order
   - intercept
   - coefficient per feature
   - threshold
   - training code/data hashes
2. Install the artifact as a scoped lookup or app-local file.
3. A Splunk saved search builds live window features and computes:
   - `score = intercept + Σ(feature_i * coefficient_i)`
   - `probability = 1/(1+exp(-score))`
   - `prediction = if(probability >= threshold, 1, 0)`
4. Alert on `prediction=1`.

The alert condition should be conservative:

```spl
... feature extraction and scoring ...
| where ai_tamperguard_prediction=1 AND ai_tamperguard_probability >= <threshold>
| eval alert_severity=case(ai_tamperguard_probability>=0.90,"high", ai_tamperguard_probability>=0.75,"medium", true(),"low")
| table _time actor_id window_start window_end ai_tamperguard_probability ai_tamperguard_score alert_severity model_version feature_*
```

### Option B: AI Toolkit / MLTK / ONNX

Use this only after app availability and permissions are verified. The benefit is cleaner model lifecycle integration; the cost is more moving parts. The same train/serve requirements still apply: exact feature order, exact normalization, threshold, and local-vs-Splunk scoring equivalence.

## Alert payload requirements

A live positive alert should include:

| Field | Purpose |
|---|---|
| `model_version` | Integrity anchor for scoring behavior. |
| `ai_tamperguard_score` | Raw model score/logit if available. |
| `ai_tamperguard_probability` | Probability or calibrated risk score. |
| `ai_tamperguard_prediction` | `1` for positive. |
| `actor_id` / actor surrogate | Grouping and investigation pivot. |
| `window_start`, `window_end` | Time window for drilldown. |
| `feature_order_hash` | Confirms deployed search used the expected features. |
| `top_contributing_features` | Explanation, if using a linear model or SHAP-like postprocess. |
| `source_surface_summary` | Which Splunk surfaces contributed to the window. |
| `drilldown_search` | Parameterized SPL back to raw/protected evidence. |

Do **not** include secrets, private hostnames, raw tokens, or raw private object names in the alert payload.

## Minimum acceptance gates before calling it deployed

1. **Feature parity:** Live Splunk feature extraction produces the same feature columns, names, types, and order as the model artifact expects.
2. **No labels at serve time:** `label_binary`, `label_family`, `outcome`, `scenario_run_id`, `path_type`, prompt metadata, and manifest fields are absent from scoring input.
3. **Equivalence test:** Splunk-side scoring matches local Python scoring on a held-out fixture: max residual within tolerance and zero prediction mismatches.
4. **Fresh live smoke:** Seed or observe a known public-safe positive path and verify that the saved search emits exactly the expected alert.
5. **Negative controls:** Benign/blocked/failed windows should not alert except where intentionally threshold-tested.
6. **Drilldown works:** Every alert links back to supporting Splunk evidence in `_audit`, `_configtracker`, synthetic lab index, or approved case/agent telemetry surfaces.
7. **Rollback:** The deployed saved search, lookup/model artifact, and alert can be disabled or removed cleanly.

## Claim boundary

Good public/internal wording:

> “AI TamperGuard v1 can derive behavior-window features from live Splunk-backed control-plane events, score those windows with a deployed baseline model, and raise a Splunk alert when a window matches the current synthetic/lab positive definition.”

Avoid:

> “This detects real-world Splunk tampering.”

The current corpus is a controlled synthetic/lab dataset with weak working-model labels. A future deployable milestone would require end-to-end live alert plumbing and local-vs-Splunk equivalence checks; this v1 closeout intentionally stops before that claim.
