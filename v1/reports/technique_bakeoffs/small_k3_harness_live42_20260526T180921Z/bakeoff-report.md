# AI TamperGuard External Technique Bakeoff

## Dataset
- source CSV: `data/training/small_k3_harness_live42_20260526T180921Z/windows_actor_15m.csv`
- source CSV sha256: `f4e3a735742eb5af511868ce13658189730e0c99ea65ae1ccb2a4b38aa61d59b`
- source batch IDs: ['small_k3_harness_live42_20260526T180921Z']
- rows: 42
- label distribution: {'0': 24, '1': 18}
- split strategy: deterministic_hash
- split distribution: {'train': 27, 'validation': 4, 'test': 11}
- fixture warning: this is a smoke-test-sized fixture; metric numbers are plumbing diagnostics only.

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
| leakage_probes | warning | leakage_suspect |

## Leakage Probes
- single-feature AUC max: 0.6911764705882353
- top single-feature AUCs: [('feature_distinct_object_type_count', 0.6911764705882353), ('feature_distinct_surface_count', 0.6617647058823529), ('feature_event_count', 0.6411764705882352), ('feature_action_switch_count', 0.6058823529411764), ('feature_visibility_object_read_count', 0.5529411764705882)]
- negative control validation AP drop: 0.0
- allowlist ablation validation AP drop: n/a
- cross-split correlation probe: True
- overall verdict: leakage_suspect

## Candidate Summary
| technique | profile | status | validation AP | validation balanced acc | deployability | leakage verdict | notes |
|---|---|---:|---:|---:|---|---|---|
| logistic_regression | default_balanced | leakage_suspect | 1.0000 | 1.0000 | direct_spl | leakage_suspect | negative control AP drop below required threshold; exported linear artifact matched estimator probabilities locally |
| logistic_regression | stronger_regularization | leakage_suspect | 1.0000 | 1.0000 | direct_spl | leakage_suspect | negative control AP drop below required threshold; exported linear artifact matched estimator probabilities locally |
| linear_sgd | log_loss_balanced | leakage_suspect | 0.6667 | 0.5000 | linear_local_only | leakage_suspect | constant predictor on validation; negative control AP drop below required threshold |
| linear_sgd | hinge_balanced | leakage_suspect | 1.0000 | 0.5000 | offline_only | leakage_suspect | constant predictor on validation; negative control AP drop below required threshold |
| decision_tree | stump | leakage_suspect | 1.0000 | 1.0000 | generated_spl_planned | leakage_suspect | negative control AP drop below required threshold |
| decision_tree | shallow | leakage_suspect | 1.0000 | 1.0000 | offline_only | leakage_suspect | negative control AP drop below required threshold |

## Selected Candidate
Selected: None

## Why This Won / Why Baseline Stayed
- No candidate is promoted because leakage probes were suspect; metrics are diagnostics only.

## Why Other Candidates Lost
- logistic_regression/default_balanced: negative control AP drop below required threshold; exported linear artifact matched estimator probabilities locally
- logistic_regression/stronger_regularization: negative control AP drop below required threshold; exported linear artifact matched estimator probabilities locally
- linear_sgd/log_loss_balanced: constant predictor on validation; negative control AP drop below required threshold
- linear_sgd/hinge_balanced: constant predictor on validation; negative control AP drop below required threshold
- decision_tree/stump: negative control AP drop below required threshold
- decision_tree/shallow: negative control AP drop below required threshold

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
