from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse, json, sys
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--scenario-run-id',required=True); p.add_argument('--reset-id',required=True); p.add_argument('--output-dir',required=True)
    a=p.parse_args(); out=Path(a.output_dir)
    if 'data/private/raw_exports' not in out.as_posix():
        print('capture output must stay under data/private/raw_exports', file=sys.stderr); return 2
    reset=Path('data/private/resets')/f'{a.reset_id}.json'
    if not reset.exists():
        print('capture requires successful private reset manifest', file=sys.stderr); return 2
    out.mkdir(parents=True,exist_ok=True)
    (out/'capture_manifest.json').write_text(json.dumps({'scenario_run_id':a.scenario_run_id,'reset_id':a.reset_id,'status':'captured_private_placeholder','public_release_ready':False},indent=2)+'\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
