from ai_tamperguard_v1.safety import scan_paths


def reasons(paths):
    return [f.reason for f in scan_paths(paths)]


def test_public_sample_scans_clean():
    assert scan_paths(['data/public_sample', 'docs', 'schemas', 'scenarios']) == []


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
