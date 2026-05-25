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


def test_normalized_event_rejects_missing_public_safe_fields():
    schema = load_schema('normalized_event_v1.schema.json')
    row = first_jsonl(SAMPLE/'normalized/events.jsonl')
    row.pop('redaction_level')
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(row)


def test_scenario_catalog_rejects_unknown_label_family():
    schema = load_schema('scenario_catalog_v1.schema.json')
    row = first_jsonl(SAMPLE/'scenarios/scenario_catalog.jsonl')
    row['family'] = 'malicious'
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(row)
