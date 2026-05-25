# AI TamperGuard V1 Dataset Workspace

This workspace contains the V1 dataset pipeline scaffold for a scenario-grounded Splunk observability-tamper corpus.

## Boundary

- Public artifacts under `data/public_sample/` are redacted and use stable pseudonyms.
- Private live-lab exports belong only under ignored paths: `data/private/`, `reports/private/`, `models/private/`, and `splunk/private/`.
- The checked-in public sample is a **synthetic fixture/smoke sample**, not a public release candidate. A release candidate must include authorized live Splunk lab runs and pass the validation gate without fixture-only relaxations.

## Useful commands

```bash
uv run --directory v1 pytest
uv run --directory v1 python scripts/validate_dataset_v1.py --schemas schemas --sample data/public_sample --check all --allow-fixture-only
uv run --directory v1 python scripts/public_safety_scan_v1.py data/public_sample docs schemas scenarios
```

Run live readiness only after creating an ignored private lab config:

```bash
uv run --directory v1 python scripts/check_splunk_readiness_v1.py --config splunk/private/lab.toml --output reports/private/splunk-readiness-local.md
```
