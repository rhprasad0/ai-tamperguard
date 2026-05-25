from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse
from pathlib import Path
from ai_tamperguard_v1.derive import derive_windows
from ai_tamperguard_v1.io import read_jsonl, write_csv_rows

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--events', required=True)
    p.add_argument('--answer-key', required=True)
    p.add_argument('--output-dir', required=True)
    args=p.parse_args()
    events=read_jsonl(Path(args.events)); answer=read_jsonl(Path(args.answer_key))
    out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    for size,name in [(300,'windows_actor_5m.csv'),(900,'windows_actor_15m.csv'),(3600,'windows_actor_60m.csv')]:
        rows=derive_windows(events, answer, size_sec=size)
        write_csv_rows(out/name, rows)
    return 0
if __name__=='__main__': raise SystemExit(main())
