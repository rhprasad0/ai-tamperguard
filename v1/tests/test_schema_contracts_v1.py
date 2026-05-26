import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, ValidationError

SCHEMA_DIR = Path(__file__).resolve().parents[1] / 'schemas'
SAMPLE = Path(__file__).resolve().parents[1] / 'data/public_sample'


def load_schema(name):
    return json.loads((SCHEMA_DIR/name).read_text(encoding='utf-8'))


def first_jsonl(path):
    return json.loads(path.read_text(encoding='utf-8').splitlines()[0])


def all_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


@pytest.mark.parametrize('schema_name,sample_path', [
    ('normalized_event_v1.schema.json', SAMPLE/'normalized/events.jsonl'),
    ('scenario_catalog_v1.schema.json', SAMPLE/'scenarios/scenario_catalog.jsonl'),
    ('scenario_run_v1.schema.json', SAMPLE/'scenarios/scenario_runs.jsonl'),
    ('reset_manifest_v1.schema.json', SAMPLE/'scenarios/reset_manifest_public_redacted.jsonl'),
    ('answer_key_v1.schema.json', SAMPLE/'scenarios/answer_key_public_redacted.jsonl'),
    ('episode_v1.schema.json', SAMPLE/'derived/episodes.jsonl'),
    ('actor_object_edge_v1.schema.json', SAMPLE/'derived/actor_object_edges.jsonl'),
])
def test_jsonl_schema_accepts_public_sample_rows(schema_name, sample_path):
    validator = Draft202012Validator(load_schema(schema_name))
    rows = [json.loads(line) for line in sample_path.read_text(encoding='utf-8').splitlines() if line]
    assert rows
    for row in rows:
        validator.validate(row)


def test_normalized_event_accepts_enriched_public_safe_metadata():
    schema = load_schema('normalized_event_v1.schema.json')
    row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    row.update({
        'actor_role_family': 'admin',
        'actor_capability_family': 'edit_dashboards',
        'capability_check_result': 'allowed',
        'object_criticality': 'high',
        'object_visibility_scope': 'global',
        'detection_lifecycle_stage': 'throttled',
        'detection_effect_family': 'visibility_loss',
        'before_state_family': 'broad',
        'after_state_family': 'narrow',
        'change_magnitude_bucket': 'medium',
        'visibility_delta': 'decrease',
        'protected_evidence_seen': True,
        'downstream_artifact_updated': False,
        'downstream_artifact_matches_evidence': 'not_applicable',
        'evidence_chain_stage': 'change_visibility_object',
    })
    Draft202012Validator(schema).validate(row)


def test_normalized_event_accepts_live_splunk_public_redacted_source_derivation():
    schema = load_schema('normalized_event_v1.schema.json')
    row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    row['source_derivation'] = 'live_splunk_public_redacted'
    Draft202012Validator(schema).validate(row)


def test_normalized_event_accepts_splunk_attack_pattern_suppression_metadata():
    schema = load_schema('normalized_event_v1.schema.json')
    row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    row.update({
        'mitre_tactic_family': 'defense_evasion',
        'mitre_technique_family': 'impair_defenses',
        'risk_object_type': 'synthetic_entity',
        'risk_score_bucket': 'high',
        'risk_event_count_bucket': 'many',
        'finding_state': 'suppressed_after_creation',
        'suppression_mode': 'suppression_after_creation',
        'notable_visibility_delta': 'hidden_from_mission_control',
        'audit_visibility_state': 'audit_seen',
        'change_channel': 'rest',
        'config_path_family': 'correlation_searches',
        'correlation_search_state': 'suppressed',
        'macro_filter_state': 'not_applicable',
        'lookup_row_delta_bucket': 'none',
        'sequence_stage': 'visibility_change',
    })
    Draft202012Validator(schema).validate(row)


def test_normalized_event_accepts_splunk_attack_pattern_macro_filter_metadata():
    schema = load_schema('normalized_event_v1.schema.json')
    row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    row.update({
        'mitre_tactic_family': 'defense_evasion',
        'mitre_technique_family': 'indicator_removal',
        'risk_object_type': 'user',
        'risk_score_bucket': 'medium',
        'risk_event_count_bucket': 'few',
        'finding_state': 'not_applicable',
        'suppression_mode': 'none',
        'notable_visibility_delta': 'decrease',
        'audit_visibility_state': 'configtracker_seen',
        'change_channel': 'web',
        'config_path_family': 'macros',
        'correlation_search_state': 'enabled',
        'macro_filter_state': 'excludes_synthetic_entity',
        'lookup_row_delta_bucket': 'small',
        'sequence_stage': 'knowledge_object_review',
    })
    Draft202012Validator(schema).validate(row)


def test_scenario_run_and_answer_key_accept_opaque_nondeterministic_ids():
    run_schema = load_schema('scenario_run_v1.schema.json')
    run_row = first_jsonl(SAMPLE/'scenarios/scenario_runs.jsonl')
    run_row['scenario_run_id'] = 'run_0123456789abcdef'
    run_row['scenario_id'] = 'scenario_006'
    run_row['reset_id'] = 'reset_0123456789abcdef'
    run_row['paired_control_run_id'] = None
    Draft202012Validator(run_schema).validate(run_row)

    answer_schema = load_schema('answer_key_v1.schema.json')
    answer_row = first_jsonl(SAMPLE/'scenarios/answer_key_public_redacted.jsonl')
    answer_row['scenario_run_id'] = 'run_0123456789abcdef'
    Draft202012Validator(answer_schema).validate(answer_row)

    event_schema = load_schema('normalized_event_v1.schema.json')
    event_row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    event_row['scenario_run_id'] = 'run_0123456789abcdef'
    event_row['scenario_id'] = 'scenario_006'
    event_row['prompt_family'] = 'model_training_validation'
    event_row['prompt_variant_id'] = 'model_training_validation_v1_a'
    Draft202012Validator(event_schema).validate(event_row)


def test_manifest_label_source_vocab_rejects_label_binary_policy_values():
    answer_schema = load_schema('answer_key_v1.schema.json')
    answer_row = first_jsonl(SAMPLE/'scenarios/answer_key_public_redacted.jsonl')
    for bad_source in {'benign', 'positive_proxy', 'needs_review', 'hard_negative'}:
        answer_row['label_source'] = bad_source
        with pytest.raises(ValidationError):
            Draft202012Validator(answer_schema).validate(answer_row)


def test_behavior_window_schema_rejects_non_numeric_feature_values():
    schema = load_schema('behavior_window_v1.schema.json')
    row = first_jsonl(SAMPLE/'derived/windows_actor_15m.csv') if False else {
        'window_id': 'window_900_000001',
        'scenario_run_id': 'run_0123456789abcdef',
        'reset_id': 'reset_0123456789abcdef',
        'actor_id': 'actor_001',
        'window_type': 'actor_15m',
        'window_start_relative_sec': 0,
        'window_end_relative_sec': 900,
        'feature_event_count': 'five',
        'label_binary': 0,
        'label_family': 'benign_investigation',
        'label_source': 'scenario_answer_key',
        'label_confidence': 0.8,
        'outcome': 'benign',
        'split_id': 'unassigned',
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(row)


def test_normalized_event_rejects_private_raw_metadata_fields():
    schema = load_schema('normalized_event_v1.schema.json')
    row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    row['raw_spl'] = 'index=_internal | table host user token'
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(row)


def test_normalized_event_rejects_missing_public_safe_fields():
    schema = load_schema('normalized_event_v1.schema.json')
    row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    row.pop('redaction_level')
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(row)


def test_actor_object_edge_accepts_metadata_enumeration_and_discovery_edge_types():
    schema = load_schema('actor_object_edge_v1.schema.json')
    row = first_jsonl(SAMPLE/'derived/actor_object_edges.jsonl')
    row['scenario_run_id'] = 'scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001'
    row['edge_type'] = 'enumerate_metadata'
    Draft202012Validator(schema).validate(row)
    row['edge_type'] = 'discover'
    Draft202012Validator(schema).validate(row)


def test_scenario_catalog_rejects_unknown_label_family():
    schema = load_schema('scenario_catalog_v1.schema.json')
    row = first_jsonl(SAMPLE/'scenarios/scenario_catalog.jsonl')
    row['family'] = 'malicious'
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(row)


def test_attack_pattern_scenario_catalog_contains_required_splunk_rows():
    rows = {row['scenario_id']: row for row in all_jsonl(Path(__file__).resolve().parents[1] / 'scenarios/scenario_subset_v1.jsonl')}
    required = {'scenario_012', 'scenario_014', 'scenario_015', 'scenario_017', 'scenario_018'}
    assert required <= rows.keys()

    assert rows['scenario_012']['name'] == 'notable_suppression_after_finding_creation'
    assert rows['scenario_012']['paired_control_scenario_id'] == 'scenario_013'
    assert 'already-created' in rows['scenario_012']['positive_condition']
    assert 'throttle' not in rows['scenario_012']['name']

    assert rows['scenario_014']['name'] == 'throttle_before_finding_creation'
    assert rows['scenario_014']['paired_control_scenario_id'] == 'scenario_013'
    assert 'prevents new finding creation' in rows['scenario_014']['positive_condition']
    assert 'suppression' not in rows['scenario_014']['name']

    assert rows['scenario_015']['name'] == 'risk_score_tuning_after_evidence_discovery'
    assert rows['scenario_015']['paired_control_scenario_id'] == 'scenario_013'
    assert rows['scenario_017']['name'] == 'macro_filter_broadening_after_entity_review'
    assert rows['scenario_017']['paired_control_scenario_id'] == 'scenario_018'
    assert rows['scenario_018']['family'] == 'benign_visibility_change'


def test_required_positive_attack_pattern_scenarios_are_paired_controls():
    rows = all_jsonl(Path(__file__).resolve().parents[1] / 'scenarios/scenario_subset_v1.jsonl')
    required_positive_ids = {'scenario_010', 'scenario_011', 'scenario_012', 'scenario_014', 'scenario_015', 'scenario_017'}
    rows_by_id = {row['scenario_id']: row for row in rows}
    missing = [sid for sid in required_positive_ids if not rows_by_id[sid]['paired_control_scenario_id']]
    assert missing == []


def test_scenario_catalog_ids_are_unique_and_schema_valid():
    schema = load_schema('scenario_catalog_v1.schema.json')
    rows = all_jsonl(Path(__file__).resolve().parents[1] / 'scenarios/scenario_subset_v1.jsonl')
    ids = [row['scenario_id'] for row in rows]
    assert len(ids) == len(set(ids))
    validator = Draft202012Validator(schema)
    for row in rows:
        validator.validate(row)
