# AI TamperGuard External Technique Bakeoff

## Dataset
- source CSV: `data/training/all_scenarios_5k_live_20260526T201126Z/windows_actor_15m_with_required_metadata_sample.csv`
- source CSV sha256: `96d70cf9f8e1448d963331a898a5168711f8687bfbfc072aa771a03aebc159ca`
- source batch IDs: ['all_scenarios_5k_live_20260526T201126Z']
- rows: 5000
- label distribution: {'0': 3623, '1': 1377}
- split strategy: deterministic_hash
- split distribution: {'train': 2978, 'validation': 991, 'test': 1031}

## Feature Policy
- policy file: `config/feature_policy_v1.yaml`
- policy sha256: `f74b497a1016b5400052f0ea2827f1a3840e519b852cc7f7cb0bcfa4df069e90`
- allowlist size: 6
- allowlist resolved: ['feature_action_switch_count', 'feature_distinct_object_type_count', 'feature_distinct_surface_count', 'feature_event_count', 'feature_search_count', 'feature_visibility_object_read_count']
- denylist_generator_signature applied: ['feature_actor_admin_context_flag', 'feature_alert_modify_count', 'feature_audit_config_change_seen_count', 'feature_broad_to_narrow_count', 'feature_capability_allowed_change_count', 'feature_capability_denied_count', 'feature_change_to_requery_min_gap_bucket', 'feature_config_change_count', 'feature_dashboard_modify_count', 'feature_detection_disable_count', 'feature_detection_throttle_or_narrow_count', 'feature_disk_change_gap_count', 'feature_downstream_contradiction_count', 'feature_downstream_mismatch_after_visibility_change_flag', 'feature_downstream_omission_count', 'feature_enabled_to_disabled_count', 'feature_evidence_target_overlap_count', 'feature_evidence_then_report_omission_flag', 'feature_evidence_to_macro_filter_sequence_flag', 'feature_evidence_to_risk_tuning_sequence_flag', 'feature_global_visibility_object_write_count', 'feature_high_criticality_object_touch_count', 'feature_high_criticality_object_write_count', 'feature_high_risk_combo_count', 'feature_intermediate_finding_review_count', 'feature_large_change_count', 'feature_lookup_filter_change_count', 'feature_macro_filter_change_count', 'feature_modify_then_requery_flag', 'feature_notable_hidden_after_creation_count', 'feature_notable_not_created_count', 'feature_permission_denied_count', 'feature_permission_probe_before_change_flag', 'feature_probe_denied_then_report_flag', 'feature_protected_evidence_agreement_count', 'feature_protected_evidence_seen_count', 'feature_read_modify_report_sequence_flag', 'feature_report_write_count', 'feature_requery_after_change_count', 'feature_risk_context_review_count', 'feature_risk_score_tuning_count', 'feature_saved_search_modify_count', 'feature_search_modify_report_sequence_flag', 'feature_search_then_modify_flag', 'feature_search_to_change_min_gap_bucket', 'feature_state_changed_after_evidence_access_flag', 'feature_suppression_after_creation_count', 'feature_suppression_or_throttle_present', 'feature_suppression_vs_throttle_disambiguated_flag', 'feature_throttle_before_creation_count', 'feature_visibility_decrease_count', 'feature_visibility_object_write_count']
- denylist_cross_split_population applied: ['feature_actor_action_rarity_bucket', 'feature_object_type_actor_rarity_bucket']
- unclassified feature_* columns: []
- selection mode: explicit_allowlist_only

## Gate Summary
| gate | status | notes |
|---|---|---|
| required_columns | passed | 10 required columns present |
| feature_policy | passed | explicit allowlist resolved |
| splits | passed | deterministic_hash by scenario_run_id |
| leakage_probes | passed | honest |

## Leakage Probes
- single-feature AUC max: 0.7508732157419897
- top single-feature AUCs: [('feature_action_switch_count', 0.7508732157419897), ('feature_distinct_object_type_count', 0.7147404060246614), ('feature_event_count', 0.6993541993285542), ('feature_visibility_object_read_count', 0.65793023506301), ('feature_search_count', 0.6485295953031849)]
- negative control validation AP drop: 0.41676403810959967
- allowlist ablation validation AP drop: n/a
- cross-split correlation probe: True
- overall verdict: honest

## Candidate Summary
| technique | profile | status | validation AP | validation balanced acc | deployability | leakage verdict | notes |
|---|---|---:|---:|---:|---|---|---|
| logistic_regression | default_balanced | passed | 0.6515 | 0.7825 | direct_spl | honest | exported linear artifact matched estimator probabilities locally |
| logistic_regression | stronger_regularization | passed | 0.6225 | 0.7799 | direct_spl | honest | exported linear artifact matched estimator probabilities locally |
| linear_sgd | log_loss_balanced | failed | 0.6478 | 0.5000 | linear_local_only | honest | constant predictor on validation |
| linear_sgd | hinge_balanced | passed | 0.6498 | 0.7092 | offline_only | honest |  |
| decision_tree | stump | leakage_suspect | 0.3997 | 0.6969 | generated_spl_planned | leakage_suspect | negative control AP drop below required threshold |
| decision_tree | shallow | passed | 0.6561 | 0.8125 | offline_only | honest |  |

## Selected Candidate
Selected: logistic_regression/default_balanced

## Why This Won / Why Baseline Stayed
- Baseline logistic regression stayed selected because no simpler eligible candidate justified replacement.

## Why Other Candidates Lost
- logistic_regression/stronger_regularization: exported linear artifact matched estimator probabilities locally
- linear_sgd/log_loss_balanced: constant predictor on validation
- linear_sgd/hinge_balanced: 
- decision_tree/stump: negative control AP drop below required threshold
- decision_tree/shallow: 

## Deployment Notes
- Direct SPL candidates are previews only until a separate Splunk-side equivalence check exists.
- Offline-only candidates are diagnostic comparisons, not deployable replacements.
- Equivalence checks completed: local exported-artifact-vs-estimator only for exported linear artifacts.

## Non-Claims
- weak proxy labels, not malicious ground truth
- not production detection quality
- not a public benchmark result
- local bakeoff metrics do not prove Splunk-side success
- feature set restricted to explicit allowlist; any future prefix-based widening must be reviewed for generator-signature leakage
