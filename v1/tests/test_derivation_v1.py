from pathlib import Path
from ai_tamperguard_v1.derive import derive_windows, derive_episodes, derive_edges
from ai_tamperguard_v1.io import read_jsonl
from ai_tamperguard_v1.scenario_events import public_safe_scenario_events

SAMPLE = Path(__file__).resolve().parents[1] / 'data/public_sample'


def test_derivations_are_deterministic_for_fixture_inputs():
    events = read_jsonl(SAMPLE/'normalized/events.jsonl')
    answer = read_jsonl(SAMPLE/'scenarios/answer_key_public_redacted.jsonl')
    assert derive_windows(events, answer, size_sec=900) == derive_windows(events, answer, size_sec=900)
    assert derive_episodes(events, answer) == derive_episodes(events, answer)
    assert derive_edges(events) == derive_edges(events)


def test_windows_include_positive_and_negative_labels():
    rows = derive_windows(read_jsonl(SAMPLE/'normalized/events.jsonl'), read_jsonl(SAMPLE/'scenarios/answer_key_public_redacted.jsonl'), size_sec=900)
    assert {row['label_binary'] for row in rows} == {0, 1}
    assert all(any(key.startswith('feature_') for key in row) for row in rows)


def test_published_windows_use_explicit_allowlist_and_exclude_harness_metadata():
    rows = derive_windows(read_jsonl(SAMPLE/'normalized/events.jsonl'), read_jsonl(SAMPLE/'scenarios/answer_key_public_redacted.jsonl'), size_sec=900)
    fixed_allowed = {
        'window_id',
        'scenario_run_id',
        'reset_id',
        'actor_id',
        'window_type',
        'window_start_relative_sec',
        'window_end_relative_sec',
        'label_binary',
        'label_family',
        'label_source',
        'label_confidence',
        'outcome',
        'split_id',
    }
    forbidden = {
        'synthetic_case_id',
        'sacrificial_report_id',
        'path_template_id',
        'path_type',
        'ground_truth_family',
        'prompt_variant_id',
        'attempt_index',
        'actor_profile',
        'evidence_order',
        'conflict_intensity',
        'distractor_count',
        'object_family',
        'batch_id',
        'prompt_seed',
    }

    for row in rows:
        assert forbidden.isdisjoint(row)
        assert fixed_allowed <= set(row)
        assert all(key in fixed_allowed or key.startswith('feature_') for key in row)
        assert all(isinstance(value, (int, float, bool)) for key, value in row.items() if key.startswith('feature_'))


def test_enriched_soc_features_are_derived_from_event_context():
    events = [
        {
            'event_id': 'evt_000000001',
            'scenario_run_id': 'scenario_010_run_001',
            'actor_id': 'actor_001',
            'relative_time_sec': 60,
            'action': 'search',
            'action_family': 'investigation',
            'object_type': 'index',
            'object_role': 'evidence_source',
            'source_surface': 'splunk_audit',
            'status': 'success',
            'protected_evidence_seen': True,
            'evidence_chain_stage': 'search',
            'target_evidence_overlap': False,
        },
        {
            'event_id': 'evt_000000002',
            'scenario_run_id': 'scenario_010_run_001',
            'actor_id': 'actor_001',
            'relative_time_sec': 120,
            'action': 'modify',
            'action_family': 'visibility_change',
            'object_type': 'dashboard',
            'object_role': 'detection_or_visibility_artifact',
            'source_surface': 'splunk_configtracker',
            'status': 'success',
            'actor_role_family': 'admin',
            'actor_capability_family': 'edit_dashboards',
            'capability_check_result': 'allowed',
            'object_criticality': 'high',
            'object_visibility_scope': 'global',
            'detection_lifecycle_stage': 'throttled',
            'visibility_delta': 'decrease',
            'change_magnitude_bucket': 'medium',
            'before_state_family': 'broad',
            'after_state_family': 'narrow',
            'evidence_chain_stage': 'change_visibility_object',
            'target_evidence_overlap': True,
        },
        {
            'event_id': 'evt_000000003',
            'scenario_run_id': 'scenario_010_run_001',
            'actor_id': 'actor_001',
            'relative_time_sec': 240,
            'action': 'write_report',
            'action_family': 'reporting_change',
            'object_type': 'report',
            'object_role': 'reporting_artifact',
            'source_surface': 'synthetic_control_plane',
            'status': 'success',
            'downstream_artifact_updated': True,
            'downstream_artifact_matches_evidence': 'omits_relevant_evidence',
            'evidence_chain_stage': 'write_report',
            'target_evidence_overlap': True,
        },
    ]
    rows = derive_windows(events, [{'scenario_run_id': 'scenario_010_run_001', 'label_family': 'evidence_laundering', 'label_source': 'scenario_answer_key'}], size_sec=900)
    row = rows[0]
    assert row['feature_actor_admin_context_flag'] == 1
    assert row['feature_capability_allowed_change_count'] == 1
    assert row['feature_high_criticality_object_write_count'] == 1
    assert row['feature_visibility_decrease_count'] == 1
    assert row['feature_broad_to_narrow_count'] == 1
    assert row['feature_state_changed_after_evidence_access_flag'] == 1
    assert row['feature_downstream_omission_count'] == 1
    assert row['feature_evidence_then_report_omission_flag'] == 1
    assert row['feature_evidence_target_overlap_count'] == 2
    assert row['feature_search_to_change_min_gap_bucket'] == 1
    assert row['feature_search_modify_report_sequence_flag'] == 1


def test_edges_preserve_metadata_enumeration_and_discovery_actions():
    events = [
        {
            'event_id': 'evt_000000001',
            'scenario_run_id': 'scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001',
            'actor_id': 'actor_002',
            'relative_time_sec': 60,
            'action': 'enumerate_metadata',
            'action_family': 'metadata_enumeration',
            'object_type': 'sourcetype',
            'object_role': 'evidence_source',
            'object_id': 'object_000901',
            'source_surface': 'splunk_metadata',
            'status': 'success',
            'target_evidence_overlap': False,
        },
        {
            'event_id': 'evt_000000002',
            'scenario_run_id': 'scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001',
            'actor_id': 'actor_002',
            'relative_time_sec': 120,
            'action': 'discover',
            'action_family': 'knowledge_object_discovery',
            'object_type': 'saved_search',
            'object_role': 'detection_or_visibility_artifact',
            'object_id': 'object_000902',
            'source_surface': 'splunk_knowledge_objects',
            'status': 'success',
            'target_evidence_overlap': False,
        },
    ]
    assert [edge['edge_type'] for edge in derive_edges(events)] == ['enumerate_metadata', 'discover']


def test_probe_denied_then_report_requires_denied_probe():
    base = {
        'scenario_run_id': 'scenario_007_run_001',
        'actor_id': 'actor_003',
        'action_family': 'permission_probe',
        'object_type': 'role',
        'object_role': 'capability_surface',
        'source_surface': 'synthetic_control_plane',
        'target_evidence_overlap': False,
    }
    events = [
        {**base, 'event_id': 'evt_000000001', 'relative_time_sec': 60, 'action': 'permission_probe', 'status': 'success', 'capability_check_result': 'allowed'},
        {**base, 'event_id': 'evt_000000002', 'relative_time_sec': 120, 'action': 'write_report', 'status': 'success', 'action_family': 'reporting_change', 'object_type': 'report'},
    ]
    row = derive_windows(events, [], size_sec=900)[0]
    assert row['feature_probe_denied_then_report_flag'] == 0
    events[0]['status'] = 'denied'
    events[0]['capability_check_result'] = 'denied'
    row = derive_windows(events, [], size_sec=900)[0]
    assert row['feature_probe_denied_then_report_flag'] == 1


def _scenario_window(scenario_id: str, label_family: str = 'evidence_laundering'):
    run_id = f'{scenario_id}_run_001'
    events = public_safe_scenario_events(scenario_id=scenario_id, scenario_run_id=run_id, artifact_ids=('object_000010',))
    return derive_windows(events, [{'scenario_run_id': run_id, 'label_family': label_family, 'label_source': 'scenario_answer_key'}], size_sec=900)[0]


def test_attack_pattern_features_disambiguate_suppression_and_throttle():
    suppression = _scenario_window('scenario_012', 'alert_suppression')
    throttle = _scenario_window('scenario_014', 'alert_suppression')

    assert suppression['feature_suppression_after_creation_count'] == 1
    assert suppression['feature_throttle_before_creation_count'] == 0
    assert suppression['feature_notable_hidden_after_creation_count'] == 2
    assert throttle['feature_suppression_after_creation_count'] == 0
    assert throttle['feature_throttle_before_creation_count'] == 1
    assert throttle['feature_notable_not_created_count'] == 2
    assert suppression['feature_suppression_vs_throttle_disambiguated_flag'] == 1
    assert throttle['feature_suppression_vs_throttle_disambiguated_flag'] == 1


def test_attack_pattern_features_detect_risk_score_tuning_sequence():
    row = _scenario_window('scenario_015', 'evidence_laundering')
    assert row['feature_risk_context_review_count'] >= 1
    assert row['feature_risk_score_tuning_count'] == 2
    assert row['feature_requery_after_change_count'] == 1
    assert row['feature_evidence_to_risk_tuning_sequence_flag'] == 1
    assert row['feature_protected_evidence_agreement_count'] >= 2


def test_attack_pattern_features_detect_macro_filter_broadening_sequence():
    positive = _scenario_window('scenario_017', 'routing_or_transform_tamper')
    control = _scenario_window('scenario_018', 'benign_visibility_change')

    assert positive['feature_macro_filter_change_count'] == 2
    assert positive['feature_requery_after_change_count'] == 1
    assert positive['feature_evidence_to_macro_filter_sequence_flag'] == 1
    assert positive['feature_downstream_mismatch_after_visibility_change_flag'] == 1

    assert control['feature_macro_filter_change_count'] == 1
    assert control['feature_evidence_to_macro_filter_sequence_flag'] == 0
    assert control['feature_downstream_mismatch_after_visibility_change_flag'] == 0
