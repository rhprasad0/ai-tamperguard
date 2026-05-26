from pathlib import Path
import csv, json, subprocess, sys
SAMPLE = Path(__file__).resolve().parents[1] / 'data/public_sample'
V1_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = V1_ROOT / 'scripts' / 'generate_splits_v1.py'


def rows(path):
    with path.open('r', encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def test_split_files_have_disjoint_windows_and_counts():
    seen = {}
    for split in ['train','validate','test']:
        split_rows = rows(SAMPLE / f'splits/{split}_windows.csv')
        assert split_rows
        for row in split_rows:
            assert row['split_id'] == split
            assert row['window_id'] not in seen
            seen[row['window_id']] = split
    manifest = json.loads((SAMPLE/'splits/split_manifest.json').read_text(encoding='utf-8'))
    assert manifest['splits']['train']['row_count'] > 0
    assert 'fixture_smoke_only' in ' '.join(manifest['relaxations'])


def _write_csv(path: Path, rows_: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_[0]))
        writer.writeheader()
        writer.writerows(rows_)


def _write_jsonl(path: Path, rows_: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows_), encoding='utf-8')


def test_generate_splits_fails_closed_on_manifest_proxy_columns(tmp_path: Path):
    windows = tmp_path / 'data' / 'training' / 'batch' / 'windows.csv'
    runs = tmp_path / 'data' / 'run_manifests' / 'batch' / 'scenario_runs.jsonl'
    _write_csv(windows, [
        {
            'window_id': 'window_000001', 'scenario_run_id': 'run_001', 'actor_id': 'actor_001',
            'window_start_relative_sec': '0', 'window_end_relative_sec': '900', 'feature_search_count': '2',
            'label_binary': '1', 'label_family': 'evidence_laundering', 'label_source': 'scenario_answer_key',
            'split_id': 'unsplit', 'path_type': 'successful_synthetic',
        }
    ])
    _write_jsonl(runs, [{'scenario_run_id': 'run_001', 'scenario_id': 'scenario_010'}])

    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--windows', str(windows), '--scenario-runs', str(runs), '--output-dir', str(tmp_path / 'data' / 'splits')],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 2
    assert 'forbidden public window columns' in result.stderr


def test_generate_splits_manifest_records_fail_closed_leakage_checks(tmp_path: Path):
    windows = tmp_path / 'data' / 'training' / 'batch' / 'windows.csv'
    runs = tmp_path / 'data' / 'run_manifests' / 'batch' / 'scenario_runs.jsonl'
    rows_ = []
    run_rows = []
    for idx in range(1, 7):
        run_id = f'run_{idx:03d}'
        rows_.append({
            'window_id': f'window_{idx:06d}', 'scenario_run_id': run_id, 'actor_id': f'actor_{idx:03d}',
            'window_start_relative_sec': '0', 'window_end_relative_sec': '900', 'feature_search_count': str(idx),
            'label_binary': str(idx % 2), 'label_family': 'benign_investigation' if idx % 2 == 0 else 'evidence_laundering',
            'label_source': 'scenario_answer_key', 'split_id': 'unsplit',
        })
        run_rows.append({'scenario_run_id': run_id, 'scenario_id': f'scenario_{idx:03d}', 'paired_control_run_id': ''})
    _write_csv(windows, rows_)
    _write_jsonl(runs, run_rows)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--windows', str(windows), '--scenario-runs', str(runs), '--output-dir', str(tmp_path / 'data' / 'splits')],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / 'data' / 'splits' / 'split_manifest.json').read_text(encoding='utf-8'))
    assert manifest['leakage_check'] == 'pass'
    assert manifest['leakage_report']['forbidden_public_window_columns_present'] == []
    assert manifest['leakage_report']['scenario_run_overlap'] is False
    assert manifest['public_window_column_policy'] == 'ids_labels_and_feature_prefix_only'
