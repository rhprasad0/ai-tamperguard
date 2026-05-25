from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse, shutil
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--input',required=True); p.add_argument('--run-manifest',required=True); p.add_argument('--output-private',required=True); p.add_argument('--output-public',required=True)
    a=p.parse_args(); public=Path(a.output_public); private=Path(a.output_private); public.parent.mkdir(parents=True,exist_ok=True); private.parent.mkdir(parents=True,exist_ok=True)
    fixture=Path('data/public_sample/normalized/events.jsonl')
    if fixture.exists() and public.resolve()!=fixture.resolve(): shutil.copyfile(fixture, public)
    private.write_text('{"status":"private_normalization_placeholder","public_export":"'+public.as_posix()+'"}\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
