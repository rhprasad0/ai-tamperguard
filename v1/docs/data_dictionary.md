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
| `evidence_chain_stage` | `search`, `read_visibility_object`, `change_visibility_object`, `write_report`, `verify`, `unknown` | Ordered stage used for sequence features. |

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

These features are SOC/SIEM practice signals for fixture/offline and sacrificial lab evaluation. They are not claims of real malicious intent or production detection quality.
