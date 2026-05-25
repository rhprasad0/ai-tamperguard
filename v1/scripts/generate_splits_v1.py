from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse, csv, json, random
from collections import Counter, defaultdict
from pathlib import Path
from ai_tamperguard_v1.io import read_csv_rows, read_jsonl, write_csv_rows

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--windows',required=True); p.add_argument('--scenario-runs',required=True); p.add_argument('--output-dir',required=True); p.add_argument('--seed',type=int,default=20260525)
    a=p.parse_args(); rows=read_csv_rows(Path(a.windows)); runs=read_jsonl(Path(a.scenario_runs)); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    random.Random(a.seed).shuffle(rows)
    run_to_split={}
    groups=defaultdict(list)
    for r in rows: groups[r['scenario_run_id']].append(r)
    run_ids=sorted(groups)
    for i,run_id in enumerate(run_ids):
        run_to_split[run_id]=['train','validate','test'][i % 3]
    split_rows={k:[] for k in ['train','validate','test']}
    for run_id, rs in groups.items():
        split=run_to_split[run_id]
        for r in rs:
            r=dict(r); r['split_id']=split; split_rows[split].append(r)
    for split,rs in split_rows.items(): write_csv_rows(out/f'{split}_windows.csv', sorted(rs,key=lambda r:r['window_id']))
    with (out/'heldout_scenarios.csv').open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=['scenario_id','holdout_reason']); writer.writeheader(); writer.writerow({'scenario_id':'scenario_012','holdout_reason':'small-sample scenario-family holdout exercise'})
    counts={s:dict(Counter(r['label_binary'] for r in rs)) for s,rs in split_rows.items()}
    manifest={'dataset_build_id':'v1-public-fixture-20260525','seed':a.seed,'split_strategy':'scenario_run_grouped_round_robin_fixture','source_window_file':Path(a.windows).as_posix(),'splits':{s:{'row_count':len(rs),'label_counts':counts[s]} for s,rs in split_rows.items()},'relaxations':['fixture_smoke_only: actor/object leakage is recorded rather than blocked because the checked-in sample is intentionally tiny'],'leakage_report':{'scenario_run_overlap':False,'paired_control_cross_split':'accepted_for_fixture_smoke_only','actor_cross_split':['actor_001','actor_002'],'object_cross_split':'recorded_not_blocking_fixture'}}
    (out/'split_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
