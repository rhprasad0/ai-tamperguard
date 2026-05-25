from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse, sys
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--output',required=True)
    a=p.parse_args(); cfg=Path(a.config); out=Path(a.output)
    if 'splunk/private' not in cfg.as_posix():
        print('config must live under ignored splunk/private/', file=sys.stderr); return 2
    if not cfg.exists():
        print(f'missing private lab config: {cfg}', file=sys.stderr); return 2
    text=cfg.read_text(encoding='utf-8')
    required=['authorized_lab_marker','target_namespace','capture_destination']
    missing=[key for key in required if key not in text]
    out.parent.mkdir(parents=True,exist_ok=True)
    if missing:
        out.write_text('# Splunk readiness failed\n\nMissing required private readiness keys: '+', '.join(missing)+'\n',encoding='utf-8'); return 2
    out.write_text('# Splunk readiness passed\n\nAuthorized lab marker, namespace, and private capture destination were present in the ignored config. Query checks must be attached by the operator-specific connector.\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
