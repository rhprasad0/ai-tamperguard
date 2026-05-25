from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse
from pathlib import Path
from ai_tamperguard_v1.derive import derive_episodes
from ai_tamperguard_v1.io import read_jsonl, write_jsonl

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--events',required=True); p.add_argument('--answer-key',required=True); p.add_argument('--output',required=True)
    a=p.parse_args(); write_jsonl(Path(a.output), derive_episodes(read_jsonl(Path(a.events)), read_jsonl(Path(a.answer_key))))
    return 0
if __name__=='__main__': raise SystemExit(main())
