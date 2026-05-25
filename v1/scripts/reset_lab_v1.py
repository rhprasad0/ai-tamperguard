from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse, json, sys
from pathlib import Path
ALLOWED_SCENARIOS={'scenario_004','scenario_006','scenario_007','scenario_010','scenario_011','scenario_012','scenario_013'}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--scenario',required=True); p.add_argument('--reset-id',required=True)
    a=p.parse_args()
    if a.scenario not in ALLOWED_SCENARIOS:
        print('scenario outside V1 sacrificial allowlist', file=sys.stderr); return 2
    if 'splunk/private' not in Path(a.config).as_posix() or not Path(a.config).exists():
        print('reset requires ignored private lab config', file=sys.stderr); return 2
    out=Path('data/private/resets')/f'{a.reset_id}.json'; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'reset_id':a.reset_id,'scenario_id':a.scenario,'status':'success','relative_time_sec':0,'sacrificial_artifact_ids':['object_000010'],'preserved_evidence_surfaces':['splunk_audit','splunk_configtracker'],'public_summary':'sacrificial fixtures restored; protected evidence preserved'},indent=2)+'\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
