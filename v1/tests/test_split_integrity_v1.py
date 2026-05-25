from pathlib import Path
import csv, json
SAMPLE = Path(__file__).resolve().parents[1] / 'data/public_sample'


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
