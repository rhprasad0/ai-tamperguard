from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))
import argparse, json
from pathlib import Path
from ai_tamperguard_v1 import DATASET_BUILD_ID, SCHEMA_VERSION

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--events',required=True); p.add_argument('--scenarios',required=True); p.add_argument('--derived',required=True); p.add_argument('--output',required=True)
    a=p.parse_args(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    manifest={'dataset_build_id':DATASET_BUILD_ID,'schema_version':SCHEMA_VERSION,'scenario_catalog_version':'v1-subset-20260525','source_batch_ids':['fixture_smoke_batch_001'],'release_status':'fixture_smoke_only_not_release_candidate','live_run_requirement':'not satisfied by checked-in fixture; run live capture before release'}
    (out/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (out/'README.md').write_text('# V1 Public Sample Fixture\n\nThis checked-in sample is public-safe and trainable for pipeline smoke tests, but it is marked `fixture_smoke_only_not_release_candidate`. A release candidate must replace or supplement these rows with authorized live Splunk lab runs and preserve the same public/private boundary. Labels mean tamper-congruent or needs-review behavior under scenario rules, not malicious intent.\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
