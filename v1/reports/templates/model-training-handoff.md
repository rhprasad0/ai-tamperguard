# V1 Model-Training Handoff

- Dataset build ID: `v1-public-fixture-20260525` until replaced by a live-run-derived build.
- Default window file: `data/public_sample/derived/windows_actor_15m.csv`.
- Split manifest: `data/public_sample/splits/split_manifest.json`.
- Label meaning: weak tamper-congruent / needs-review proxy, not malicious intent.
- Feature columns: include only `feature_*` numeric or boolean-like fields.
- Excluded private fields: raw SPL, prompts, hostnames, usernames, URLs, tokens, local paths, private evidence pointers, and private model outputs.
- First baseline: logistic regression or a small tree after live-run-derived rows exist.
- Required checks: non-constant predictor, split respected, no private columns, per-split counts reported beside metrics, and conservative public wording.
