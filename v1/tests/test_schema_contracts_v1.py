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


def test_scenario_run_and_answer_key_accept_nondeterministic_prompt_pack_ids():
    run_schema = load_schema('scenario_run_v1.schema.json')
    run_row = first_jsonl(SAMPLE/'scenarios/scenario_runs.jsonl')
    run_row['scenario_run_id'] = 'scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001'
    run_row['scenario_id'] = 'scenario_006'
    Draft202012Validator(run_schema).validate(run_row)

    answer_schema = load_schema('answer_key_v1.schema.json')
    answer_row = first_jsonl(SAMPLE/'scenarios/answer_key_public_redacted.jsonl')
    answer_row['scenario_run_id'] = 'scenario_006_nondet_operator_handoff_asset_map_v1_a_attempt_001'
    Draft202012Validator(answer_schema).validate(answer_row)


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
