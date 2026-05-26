from pathlib import Path

from ai_tamperguard_v1.safety import scan_paths


V1_ROOT = Path(__file__).resolve().parents[1]


def reasons(paths):
    return [f.reason for f in scan_paths(paths)]


def test_public_sample_scans_clean():
    assert scan_paths(['data/public_sample', 'docs', 'schemas', 'scenarios']) == []


def test_generated_run_manifests_are_ignored_by_git_policy():
    gitignore = (V1_ROOT / '.gitignore').read_text(encoding='utf-8')
    assert 'data/run_manifests/' in gitignore


def test_blocks_secret_private_config_path_metadata():
    assert any('secret/private config path' in reason for reason in reasons(['splunk/private/lab.toml']))


def test_blocks_secret_assignment(tmp_path):
    p = tmp_path / 'leak.md'
    p.write_text('api_key = do-not-commit', encoding='utf-8')
    assert any('secret assignment' in reason for reason in reasons([str(p)]))


def test_blocks_overclaim(tmp_path):
    p = tmp_path / 'claim.md'
    p.write_text('This proves malicious intent.', encoding='utf-8')
    assert any('forbidden public claim' in reason for reason in reasons([str(p)]))
