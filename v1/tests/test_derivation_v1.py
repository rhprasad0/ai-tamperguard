from pathlib import Path
from ai_tamperguard_v1.derive import derive_windows, derive_episodes, derive_edges
from ai_tamperguard_v1.io import read_jsonl

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
