from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse, sys
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--reset-id',required=True); p.add_argument('--output',required=True)
    a=p.parse_args(); manifest=Path('data/resets')/f'{a.reset_id}.json'; out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    if not manifest.exists():
        out.write_text('# Reset verification failed\n\nPrivate reset manifest is missing.\n',encoding='utf-8'); return 2
    out.write_text('# Reset verification passed\n\nPrivate reset manifest exists. Connector-specific artifact checks must be attached before live release.\n',encoding='utf-8'); return 0
if __name__=='__main__': raise SystemExit(main())
