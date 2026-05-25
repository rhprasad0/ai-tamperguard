# V1 Data Dictionary

All public IDs are stable pseudonyms. Public rows use relative time and controlled vocabularies. Feature columns intended for model consumption use the `feature_*` prefix and are numeric or boolean-like integers.

## Normalized event metadata

These enriched fields are optional in `normalized_event_v1.schema.json` so older public-safe rows remain valid. Scenario generation and capture should fill them when known, or use `unknown`, `not_applicable`, or `false` defaults. They must never contain raw SPL, usernames, hostnames, URLs, tokens, private object names, private prompts, absolute timestamps, internal IPs, or local paths.

| Field | Type / values | Meaning |
|---|---|---|
| `actor_role_family` | `admin`, `analyst`, `service_account`, `agent`, `system`, `unknown` | Broad public-safe actor context. |
| `actor_capability_family` | `search`, `admin_all_objects`, `edit_savedsearches`, `edit_dashboards`, `edit_alerts`, `manage_tokens`, `unknown` | Capability family relevant to the event. |
| `capability_check_result` | `allowed`, `denied`, `not_checked`, `unknown` | Whether the public-safe capability check succeeded. |
| `object_criticality` | `low`, `medium`, `high`, `unknown` | Public-safe bucket for how important the object is to visibility or evidence. |
| `object_visibility_scope` | `private`, `team`, `global`, `unknown` | Public-safe visibility scope bucket. |
| `detection_lifecycle_stage` | `draft`, `enabled`, `scheduled`, `throttled`, `disabled`, `report_only`, `unknown` | Coarse detection/report lifecycle state. |
| `detection_effect_family` | `none`, `visibility_gain`, `visibility_loss`, `alert_volume_reduction`, `routing_change`, `report_change`, `unknown` | Public-safe effect family. |
| `before_state_family` / `after_state_family` | `enabled`, `disabled`, `broad`, `narrow`, `scheduled`, `unscheduled`, `present`, `absent`, `unknown` | Coarse before/after state buckets. |
| `change_magnitude_bucket` | `none`, `small`, `medium`, `large`, `unknown` | Coarse change-size bucket. |
| `visibility_delta` | `none`, `increase`, `decrease`, `unknown` | Whether the event appears to change visibility. |
| `protected_evidence_seen` | boolean | Public-safe indicator that protected evidence was observed. |
| `downstream_artifact_updated` | boolean | Whether a downstream report/visibility artifact was updated. |
| `downstream_artifact_matches_evidence` | `matches`, `omits_relevant_evidence`, `contradicts_evidence`, `not_applicable`, `unknown` | Coarse evidence-chain agreement label. |
| `evidence_chain_stage` | `search`, `read_visibility_object`, `change_visibility_object`, `write_report`, `verify`, `metadata_enumeration`, `knowledge_object_discovery`, `requery`, `unknown` | Ordered stage used for sequence features. |
| `mitre_tactic_family` | `defense_evasion`, `discovery`, `collection`, `impact`, `benign_admin`, `unknown` | Coarse ATT&CK-like tactic family for public-safe Splunk/SOC sequence context. |
| `mitre_technique_family` | `impair_defenses`, `indicator_removal`, `permission_discovery`, `defense_discovery`, `unknown` | Coarse technique family; conservative analogy only, not intent attribution. |
| `risk_object_type` | `user`, `host`, `service`, `synthetic_entity`, `not_applicable`, `unknown` | Splunk RBA-style risk object category. |
| `risk_score_bucket` | `none`, `low`, `medium`, `high`, `critical`, `unknown` | Public-safe risk score bucket, not a raw risk score. |
| `risk_event_count_bucket` | `none`, `single`, `few`, `many`, `unknown` | Bucketed count of contributing risk/finding events. |
| `finding_state` | `not_applicable`, `intermediate_finding_created`, `notable_created`, `suppressed_after_creation`, `throttled_before_creation`, `disabled`, `unknown` | Public-safe finding/notable state. |
| `suppression_mode` | `none`, `suppression_after_creation`, `throttle_before_creation`, `disable_detection`, `unknown` | Distinguishes hiding an existing finding from preventing finding creation or disabling a detection. |
| `notable_visibility_delta` | `none`, `hidden_from_mission_control`, `not_created`, `decrease`, `unknown` | Mission Control/notable-like public-safe visibility delta. |
| `audit_visibility_state` | `audit_seen`, `configtracker_seen`, `protected_outer_telemetry_seen`, `disk_change_gap`, `unknown` | Which protected audit/control-plane surface observed the change, or whether a disk-change gap exists. |
| `change_channel` | `web`, `rest`, `cli`, `disk`, `mcp_proxy`, `synthetic_fixture`, `none`, `unknown` | Public-safe channel family for the configuration/control-plane change. |
| `config_path_family` | `savedsearches`, `macros`, `lookups`, `dashboards`, `correlation_searches`, `risk_scoring`, `not_applicable`, `unknown` | Coarse Splunk knowledge-object/config path family. |
| `correlation_search_state` | `enabled`, `disabled`, `throttled`, `suppressed`, `score_lowered`, `not_applicable`, `unknown` | Public-safe state of a correlation-search-like detection artifact. |
| `macro_filter_state` | `not_applicable`, `broad`, `narrow`, `excludes_synthetic_entity`, `unknown` | Public-safe macro/filter state for filter-broadening or allowlist-like scenarios. |
| `lookup_row_delta_bucket` | `none`, `small`, `medium`, `large`, `unknown` | Bucketed lookup-row change size. |
| `sequence_stage` | `evidence_review`, `risk_context_review`, `knowledge_object_review`, `visibility_change`, `requery_after_change`, `reporting`, `control`, `unknown` | Splunk attack-pattern sequence stage used to model ordered stories. |

## Behavior window features

Every `derive_windows` output row emits the following enriched `feature_*` columns as non-negative integers. Bucket fields use `0` for absent/unknown; timing buckets use `1` fast/same-window, `2` medium, and `3` slow.

| Feature | Meaning |
|---|---|
| `feature_actor_admin_context_flag` | Window includes an admin-family actor context. |
| `feature_capability_denied_count` | Count of denied capability/status events. |
| `feature_capability_allowed_change_count` | Allowed capability checks paired with write/change actions. |
| `feature_permission_probe_before_change_flag` | Permission probe appears before a write/change action. |
| `feature_high_criticality_object_touch_count` | Events touching high-criticality objects. |
| `feature_high_criticality_object_write_count` | Write/change events on high-criticality objects. |
| `feature_detection_disable_count` | Disable actions or disabled lifecycle states. |
| `feature_detection_throttle_or_narrow_count` | Throttled/narrowed detection lifecycle or state changes. |
| `feature_global_visibility_object_write_count` | Write/change events on globally scoped visibility objects. |
| `feature_visibility_decrease_count` | Events with `visibility_delta=decrease`. |
| `feature_large_change_count` | Events with `change_magnitude_bucket=large`. |
| `feature_enabled_to_disabled_count` | Before/after transitions from enabled to disabled. |
| `feature_broad_to_narrow_count` | Before/after transitions from broad to narrow. |
| `feature_state_changed_after_evidence_access_flag` | Evidence access occurs before a visibility-object change. |
| `feature_protected_evidence_seen_count` | Count of events marked as protected evidence seen. |
| `feature_downstream_omission_count` | Downstream artifact omitted relevant evidence. |
| `feature_downstream_contradiction_count` | Downstream artifact contradicted evidence. |
| `feature_evidence_then_report_omission_flag` | Evidence was seen and a later report omitted relevant evidence. |
| `feature_evidence_target_overlap_count` | Events overlapping the target evidence/object family. |
| `feature_report_write_count` | Report write events. |
| `feature_search_to_change_min_gap_bucket` | Bucketed minimum search-to-change relative-time gap. |
| `feature_change_to_requery_min_gap_bucket` | Bucketed minimum change-to-requery relative-time gap. |
| `feature_distinct_surface_count` | Distinct public-safe source surfaces in the window. |
| `feature_action_switch_count` | Count of action changes in event order. |
| `feature_search_modify_report_sequence_flag` | Search → modify → report sequence exists. |
| `feature_read_modify_report_sequence_flag` | Read → modify → report sequence exists. |
| `feature_probe_denied_then_report_flag` | Permission probe precedes a report write. |
| `feature_actor_action_rarity_bucket` | Intra-sample actor/action rarity bucket: `0` unknown, `1` common, `2` uncommon, `3` rare. |
| `feature_object_type_actor_rarity_bucket` | Intra-sample actor/object-type rarity bucket: `0` unknown, `1` common, `2` uncommon, `3` rare. |
| `feature_high_risk_combo_count` | Count of high-criticality write/probe events with visibility decrease or denied capability context. |
| `feature_risk_context_review_count` | Count of events in risk-context review sequence stage. |
| `feature_intermediate_finding_review_count` | Count of intermediate-finding public-safe states. |
| `feature_suppression_after_creation_count` | Count of suppression-after-creation events. |
| `feature_throttle_before_creation_count` | Count of throttle-before-creation events. |
| `feature_suppression_or_throttle_present` | Flag for either suppression or throttling semantics present. |
| `feature_notable_hidden_after_creation_count` | Count of notable/finding visibility hidden after creation. |
| `feature_notable_not_created_count` | Count of finding/notable not-created outcomes from throttling. |
| `feature_risk_score_tuning_count` | Count of risk scoring or severity lowering signals. |
| `feature_macro_filter_change_count` | Count of macro/filter state changes or related re-query observations. |
| `feature_lookup_filter_change_count` | Count of non-empty lookup-row delta buckets. |
| `feature_requery_after_change_count` | Count of post-change re-query/verification events. |
| `feature_audit_config_change_seen_count` | Count of audit/configtracker-observed control-plane changes. |
| `feature_disk_change_gap_count` | Count of direct-disk-change-gap signals. |
| `feature_evidence_to_risk_tuning_sequence_flag` | Evidence/risk review occurs before risk-score tuning. |
| `feature_evidence_to_macro_filter_sequence_flag` | Evidence/risk review occurs before a macro/filter entity exclusion. |
| `feature_suppression_vs_throttle_disambiguated_flag` | Exactly one of suppression-after-creation or throttle-before-creation is present. |
| `feature_protected_evidence_agreement_count` | Protected evidence observations whose downstream agreement is matching or not-applicable. |
| `feature_downstream_mismatch_after_visibility_change_flag` | A downstream omission/contradiction appears after a visibility change. |

These features are SOC/SIEM practice signals for fixture/offline and sacrificial lab evaluation. They are not claims of real malicious intent or production detection quality.

## Training CSV exports

Raw harness files under `data/raw_exports/<batch_id>/<scenario_run_id>/public_safe_events.jsonl` are event-level public-safe atoms, not the final model table. Use `scripts/raw_harness_jsonl_to_training_csv_v1.py` to validate those rows, derive behavior-window features, and write a public-safe training CSV.

Example:

```bash
uv run --directory v1 python scripts/raw_harness_jsonl_to_training_csv_v1.py \
  --input data/raw_exports/v1_live_feature_verify_20260525T162448Z \
  --answer-key data/public_sample/scenarios/answer_key_public_redacted.jsonl \
  --output data/training/v1_live_feature_verify_20260525T162448Z/windows_actor_15m.csv \
  --window-size-sec 900
```

The output is one row per actor/window with `feature_*` columns, `label_binary`, `label_family`, `label_source`, and `split_id`. Keep generated training CSVs under `data/training/` unless Ryan explicitly promotes a public-safe fixture. For supervised training, provide an answer key or public-safe run manifest; `--allow-unlabeled` is debug-only and emits `background_unlabeled` labels.
