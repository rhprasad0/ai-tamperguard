from pathlib import Path
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
