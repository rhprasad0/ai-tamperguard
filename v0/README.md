# AI TamperGuard v0

v0 is the first end-to-end plumbing milestone for AI TamperGuard.

It is intentionally small: prove that a model can move from local feature extraction and training back into Splunk-side scoring, while keeping private Splunk data and generated artifacts out of the public repo. The lobster does not get a cape yet. The camera is plugged in first.

## What v0 accomplished

The v0 implementation added a reproducible local pipeline for behavior-window modeling:

1. **Behavior-window schema contracts**
   - `schemas/behavior_window_v0.schema.json`
   - `schemas/model_artifact_v0.schema.json`
   - `schemas/holdout_fixture_v0.schema.json`

2. **Feature extraction**
   - Converts authorized Splunk export rows into fixed-schema actor windows.
   - Supports `actor_60m` and `actor_15m` windows.
   - Normalizes private actor identity into a private surrogate field.
   - Keeps evidence fields separate from model features.

3. **Weak labeling**
   - Uses modest v0 labels for plumbing validation.
   - `label_binary = 1` means review-worthy or higher-risk administrative/control-plane activity, not malicious ground truth.

4. **Deterministic splitting**
   - Creates stable train/holdout splits from window IDs and a seed.
   - Avoids random split drift between runs.

5. **Local baseline training**
   - Trains a logistic-regression baseline with `scikit-learn`.
   - Emits a JSON model artifact with model metadata, feature order, coefficients, intercept, threshold, and diagnostics.
   - Writes private reports under ignored private paths.

6. **Splunk scoring artifact rendering**
   - Renders a Splunk SPL scoring template from the local model artifact.
   - Uses explicit coefficient math rather than relying on a private Python runtime inside Splunk.

7. **Local-vs-Splunk verification**
   - Compares local scores/probabilities/predictions against Splunk-scored holdout rows.
   - The private v0 run verified equivalence on 241 rows with zero prediction mismatches.

8. **Public-safety guardrails**
   - Adds a scanner for private generated paths, generated model/data extensions, and overclaim phrases.
   - Keeps private exports, model artifacts, reports, Splunk deployment material, and real lookup rows out of tracked public files.

## Blocker and workaround

The main blocker was Splunk-side deployment surface area, not local training.

The first imagined path was to hand Splunk a normal ML artifact and run it through an AI Toolkit / MLTK-style flow. That was too much moving surface for v0: ONNX / MLTK availability and permissions were unresolved, and the Splunk MCP safety guard correctly blocked generic `outputlookup` writes. That block is a feature, not a bug; relaxing it would have proven that the lab could bypass its own guardrails, which is exactly the kind of foot-gun this project is trying not to hand to the lobster.

The workaround was to shrink v0 to a narrower, auditable path:

1. Train the baseline model locally.
2. Export a public-safe JSON model artifact shape privately.
3. Render plain SPL that computes the logistic-regression score with explicit coefficient math.
4. Deploy only scoped private lookup/search artifacts into the `ai_tamperguard` app context.
5. Run Splunk-side scoring against held-out rows.
6. Export the scored result and verify it against the local expected scores.
7. Roll the app artifacts back and verify removal.

So v0 does **not** depend on Splunk AI Toolkit, MLTK, ONNX import, custom Python search commands, or broad MCP write permissions. The important proof is narrower: Splunk can reproduce the locally trained model's scoring math on held-out rows, and the deployment/rollback path can be audited.

## What v0 does not claim

v0 is **not** a production security model.

It does not claim field effectiveness, adversarial coverage, vendor comparison, or benchmark-quality labels. It proves that the downstream pipeline can work:

```text
authorized Splunk rows
→ behavior windows
→ local model artifact
→ rendered SPL scoring
→ Splunk-side holdout scoring
→ local-vs-Splunk equivalence report
```

## Directory map

```text
v0/
  docs/                         # v0 specs, open questions, adversarial review
  schemas/                      # public JSON schema contracts
  scripts/                      # CLI entry points for extraction, split, train, render, verify, scan
  splunk/searches/              # public-safe SPL template(s)
  src/ai_tamperguard/           # v0 Python package
  tests/                        # unit and hygiene tests
  reports/                      # public report template only
```

Private/generated paths are intentionally ignored:

```text
v0/data/private/
v0/models/private/
v0/reports/private/
v0/splunk/private/
```

## Run the v0 checks

From this directory:

```bash
uv run --extra dev pytest
```

Run the public-safety scanner against tracked v0 files from the repo root:

```bash
git ls-files -z v0 | xargs -0 uv run --directory v0 python scripts/public_safety_scan.py
```

## Key docs

- [`docs/v0-model-pipeline-spec.md`](docs/v0-model-pipeline-spec.md) — main v0 model pipeline spec
- [`docs/v0-model-pipeline-spec-adversarial.md`](docs/v0-model-pipeline-spec-adversarial.md) — adversarial review and anti-overclaim guardrails
- [`docs/v0-open-questions.md`](docs/v0-open-questions.md) — resolved and remaining implementation questions
- [`reports/v0-smoke-test-template.md`](reports/v0-smoke-test-template.md) — local report template

## Safety boundary

Use authorized local Splunk data only. Do not commit raw Splunk exports, private lookup rows, generated model artifacts, private reports, hostnames, usernames, tokens, private URLs, or lab-specific deployment material.
