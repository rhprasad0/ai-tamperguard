from __future__ import annotations

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse
import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator
from ai_tamperguard_v1.io import read_jsonl, read_csv_rows
from ai_tamperguard_v1.safety import scan_paths

SCHEMA_MAP = {
    'events': 'normalized_event_v1.schema.json',
    'scenario_catalog': 'scenario_catalog_v1.schema.json',
    'scenario_runs': 'scenario_run_v1.schema.json',
    'reset_manifest': 'reset_manifest_v1.schema.json',
    'answer_key': 'answer_key_v1.schema.json',
    'episodes': 'episode_v1.schema.json',
    'edges': 'actor_object_edge_v1.schema.json',
}


def load_schema(schema_dir: Path, name: str) -> dict:
    return json.loads((schema_dir / name).read_text(encoding='utf-8'))


def validate_jsonl(schema_dir: Path, name: str, path: Path) -> list[str]:
    errors=[]
    schema=load_schema(schema_dir, SCHEMA_MAP[name])
    validator=Draft202012Validator(schema)
    rows=read_jsonl(path)
    if not rows:
        return [f'{path}: no rows']
    for idx,row in enumerate(rows,1):
        for err in validator.iter_errors(row):
            errors.append(f'{path}:{idx}: {err.message}')
    return errors


def validate_schemas_exist(schema_dir: Path) -> list[str]:
    missing=[name for name in SCHEMA_MAP.values()] + ['behavior_window_v1.schema.json','split_manifest_v1.schema.json']
    return [f'missing schema: {name}' for name in missing if not (schema_dir/name).exists()]


def validate_windows(schema_dir: Path, path: Path) -> list[str]:
    errors=[]; rows=read_csv_rows(path)
    if not rows: return [f'{path}: no rows']
    schema=load_schema(schema_dir,'behavior_window_v1.schema.json')
    validator=Draft202012Validator(schema)
    labels=set()
    for idx,row in enumerate(rows,1):
        converted={}
        for k,v in row.items():
            if k.startswith('feature_') or k in {'window_start_relative_sec','window_end_relative_sec','label_binary'}:
                converted[k]=int(v)
            else:
                converted[k]=v
        labels.add(converted['label_binary'])
        for err in validator.iter_errors(converted): errors.append(f'{path}:{idx}: {err.message}')
        for k,v in converted.items():
            if k.startswith('feature_') and v == '': errors.append(f'{path}:{idx}: empty feature {k}')
    if labels != {0,1}: errors.append(f'{path}: expected both positive and negative labels, got {sorted(labels)}')
    return errors


def validate_relationships(sample: Path) -> list[str]:
    errors=[]
    scenarios={r['scenario_id'] for r in read_jsonl(sample/'scenarios/scenario_catalog.jsonl')}
    runs=read_jsonl(sample/'scenarios/scenario_runs.jsonl')
    run_ids={r['scenario_run_id'] for r in runs}
    reset_ids={r['reset_id'] for r in runs}
    events=read_jsonl(sample/'normalized/events.jsonl')
    event_run_ids={e['scenario_run_id'] for e in events if e.get('scenario_run_id')}
    for r in runs:
        if r['scenario_id'] not in scenarios: errors.append(f"run {r['scenario_run_id']} references unknown scenario {r['scenario_id']}")
    for run_id in event_run_ids:
        if run_id not in run_ids: errors.append(f'event references unknown scenario_run_id {run_id}')
    answers=read_jsonl(sample/'scenarios/answer_key_public_redacted.jsonl')
    answer_runs={a['scenario_run_id'] for a in answers}
    for run_id in answer_runs:
        if run_id not in run_ids: errors.append(f'answer key references unknown run {run_id}')
        if run_id not in event_run_ids: errors.append(f'answer key has no matching public events for {run_id}')
    resets={r['reset_id'] for r in read_jsonl(sample/'scenarios/reset_manifest_public_redacted.jsonl')}
    missing_resets=reset_ids-resets
    if missing_resets: errors.append('scenario runs reference missing reset ids: '+', '.join(sorted(missing_resets)))
    return errors


def validate_splits(schema_dir: Path, sample: Path) -> list[str]:
    errors=[]
    splits=sample/'splits'
    manifest_path=splits/'split_manifest.json'
    if not manifest_path.exists(): return ['missing split manifest']
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for err in Draft202012Validator(load_schema(schema_dir,'split_manifest_v1.schema.json')).iter_errors(manifest): errors.append(f'split_manifest: {err.message}')
    by_window={}
    for split in ['train','validate','test']:
        for row in read_csv_rows(splits/f'{split}_windows.csv'):
            wid=row['window_id']
            if wid in by_window: errors.append(f'window {wid} appears in multiple splits')
            by_window[wid]=split
            if row.get('split_id') != split: errors.append(f'{wid} has split_id={row.get("split_id")} in {split}')
    return errors


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--schemas', default='schemas')
    p.add_argument('--sample')
    p.add_argument('--events')
    p.add_argument('--scenario-catalog')
    p.add_argument('--answer-key')
    p.add_argument('--check', default='all', choices=['all','schemas-only','scenario_catalog','answer_key','relationships','splits'])
    p.add_argument('--allow-fixture-only', action='store_true')
    a=p.parse_args()
    schema_dir=Path(a.schemas); errors=[]
    errors += validate_schemas_exist(schema_dir)
    if a.check == 'schemas-only':
        pass
    elif a.check == 'scenario_catalog':
        errors += validate_jsonl(schema_dir,'scenario_catalog',Path(a.scenario_catalog))
    elif a.check == 'answer_key':
        errors += validate_jsonl(schema_dir,'events',Path(a.events)); errors += validate_jsonl(schema_dir,'answer_key',Path(a.answer_key))
    else:
        sample=Path(a.sample or 'data/public_sample')
        errors += validate_jsonl(schema_dir,'scenario_catalog',sample/'scenarios/scenario_catalog.jsonl')
        errors += validate_jsonl(schema_dir,'scenario_runs',sample/'scenarios/scenario_runs.jsonl')
        errors += validate_jsonl(schema_dir,'reset_manifest',sample/'scenarios/reset_manifest_public_redacted.jsonl')
        errors += validate_jsonl(schema_dir,'events',sample/'normalized/events.jsonl')
        errors += validate_jsonl(schema_dir,'answer_key',sample/'scenarios/answer_key_public_redacted.jsonl')
        errors += validate_jsonl(schema_dir,'episodes',sample/'derived/episodes.jsonl')
        errors += validate_jsonl(schema_dir,'edges',sample/'derived/actor_object_edges.jsonl')
        errors += validate_windows(schema_dir, sample/'derived/windows_actor_15m.csv')
        errors += validate_relationships(sample)
        errors += validate_splits(schema_dir, sample)
        safety=scan_paths([str(sample),'docs','schemas','scenarios'])
        errors += [f'{f.path}: {f.reason}' for f in safety]
        manifest_path=sample/'dataset_manifest.json'
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
            release_status = manifest.get('release_status')
            if release_status != 'release_candidate' and not a.allow_fixture_only:
                errors.append(f'sample is fixture-only / non-release-candidate ({release_status}); pass --allow-fixture-only for offline smoke validation or collect live lab rows before release validation')
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
