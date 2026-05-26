from pathlib import Path
import csv
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_allows_fixture_only_validation():
    result = subprocess.run([
        'python', 'scripts/validate_dataset_v1.py', '--schemas', 'schemas', '--sample', 'data/public_sample', '--check', 'all', '--allow-fixture-only'
    ], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_release_validation_fails_closed_for_fixture_only_sample():
    result = subprocess.run([
        'python', 'scripts/validate_dataset_v1.py', '--schemas', 'schemas', '--sample', 'data/public_sample', '--check', 'all'
    ], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode != 0
    assert 'fixture-only' in result.stderr


def test_derived_windows_preserve_scenario_run_reset_ids():
    runs = {
        row['scenario_run_id']: row['reset_id']
        for row in (json.loads(line) for line in (ROOT / 'data/public_sample/scenarios/scenario_runs.jsonl').read_text(encoding='utf-8').splitlines() if line)
    }
    with (ROOT / 'data/public_sample/derived/windows_actor_15m.csv').open(newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            assert row['reset_id'] == runs[row['scenario_run_id']]
