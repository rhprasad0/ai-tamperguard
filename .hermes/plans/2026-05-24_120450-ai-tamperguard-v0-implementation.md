# AI TamperGuard v0 Model Pipeline Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Enforce test-driven-development for behavior-bearing code: RED → GREEN → REFACTOR. Do not commit private Splunk data, generated model artifacts, rendered coefficient SPL, or generated reports.

**Goal:** Build the v0 smoke-test pipeline from authorized Splunk control-plane logs to local behavior-window extraction, local logistic-regression training, rendered no-ML-app SPL scoring, Splunk-side held-out fixture scoring, local-vs-Splunk equivalence verification, private report generation, and rollback.

**Architecture:** Keep public repo artifacts limited to code, schemas, templates, docs, and tests. Put generated/private runtime artifacts under ignored paths. Implement pure Python transformation/training/rendering/verification modules first, then add thin live adapters for Splunk MCP / approved deploy path. Treat Splunk-side scoring as a deterministic SPL `eval` renderer from one model artifact; the model artifact is the single source of truth for `feature_order`, coefficients, threshold, and `model_version`.

**Tech Stack:** Python 3, pandas, scikit-learn, pytest, jsonschema, Splunk Enterprise 10.2.3, Splunk MCP server, Context7 MCP for Splunk docs checks, SPL `inputlookup`, `eval`, `tonumber`, `exp`, app namespace `ai_tamperguard`.

---

## Current context / assumptions

- Working repo: `/home/ryan/projects/ai-tamperguard`.
- Current branch: `main`, currently one local docs commit ahead of `origin/main`.
- Specs already committed locally in `d8cea08`:
  - `docs/v0-model-pipeline-spec.md`
  - `docs/v0-model-pipeline-spec-adversarial.md`
  - `docs/v0-open-questions.md`
- Target Splunk environment from planning docs:
  - Splunk Enterprise `10.2.3`, build `4d61cf8a5c0c`, Linux `x86_64`.
  - No Splunk AI Toolkit or MLTK installed.
  - First path is no-ML-app logistic-regression scoring in SPL.
- First data sources:
  - `index=_audit sourcetype=audittrail`
  - `index=_configtracker sourcetype=splunk_configuration_change`
- First window: `actor_60m`.
- Positive label meaning: `working_model_positive_proxy` / `needs_review`, not malicious ground truth.
- Private/generated paths must remain untracked:
  - `data/private/`
  - `models/private/`
  - `reports/private/`
  - `splunk/private/`
- Context7 doc checks already confirmed key primitives: Splunk documents `exp()`, `tonumber()`, `inputlookup`, `outputlookup`, saved-search config, and `/servicesNS/{user}/{app}/...` namespace endpoints. Re-check before final SPL/deploy code.
- Splunk MCP is expected to be available for live read/search validation, but current `hermes mcp list` in this session only showed `context7`; first execution step must resolve this discrepancy before live Splunk work.

---

## Implementation strategy

1. **Offline/public code first.** Build schemas, pure feature extraction, deterministic split, training, SPL rendering, verification, and public-safety scanning with tests using synthetic in-memory fixtures.
2. **Live Splunk read-only probes second.** Use Splunk MCP to validate version, field availability, sourcetype volume, and the exact first weak-label rule. Store probe output only in `reports/private/`.
3. **Private run third.** Extract private windows, split holdout, train logistic regression, render private scoring artifacts, verify non-degeneracy locally.
4. **Deploy last.** Use exactly one approved write path. Default decision point: if no narrow MCP write tool exists, use app filesystem packaging / Splunk REST with scoped credentials and validate read-back through Splunk MCP.
5. **Rollback is part of pass.** A run is incomplete until the deployed artifacts are removable and MCP confirms removal.

---

## File map

### Create public code / config

- `pyproject.toml`
- `src/ai_tamperguard/__init__.py`
- `src/ai_tamperguard/schema.py`
- `src/ai_tamperguard/features.py`
- `src/ai_tamperguard/labels.py`
- `src/ai_tamperguard/split.py`
- `src/ai_tamperguard/train.py`
- `src/ai_tamperguard/render_spl.py`
- `src/ai_tamperguard/verify.py`
- `src/ai_tamperguard/public_safety.py`
- `src/ai_tamperguard/splunk_queries.py`
- `scripts/extract_windows_v0.py`
- `scripts/split_holdout_v0.py`
- `scripts/train_v0_logistic_regression.py`
- `scripts/render_splunk_scoring_artifact_v0.py`
- `scripts/verify_local_vs_splunk_v0.py`
- `scripts/public_safety_scan.py`
- `schemas/behavior_window_v0.schema.json`
- `schemas/model_artifact_v0.schema.json`
- `schemas/holdout_fixture_v0.schema.json`
- `splunk/searches/score_v0_logistic_regression_template.spl`
- `splunk/searches/validate_v0_scoring_template.spl`
- `reports/v0-smoke-test-template.md`

### Create tests

- `tests/test_schema_contracts.py`
- `tests/test_features.py`
- `tests/test_labels.py`
- `tests/test_split.py`
- `tests/test_train.py`
- `tests/test_render_spl.py`
- `tests/test_verify.py`
- `tests/test_public_safety.py`
- `tests/test_repo_hygiene.py`

### Modify

- `.gitignore`
- `README.md` only if the final command paths need a short usage section.
- Existing docs only if implementation reveals a spec mismatch.

---

## Phase 0 — Preflight and live-tool readiness

### Task 0.1: Resolve repo state before implementation

**Objective:** Avoid losing the existing local docs commit or mixing it with implementation accidentally.

**Files:** none.

**Steps:**
1. Run `git status --short --branch`.
2. Confirm branch is `main...origin/main [ahead 1]` or note any drift.
3. If Ryan wants public backup before implementation, push the existing docs commit before coding:
   ```bash
   git push origin main
   ```
4. If not pushing yet, proceed knowing the implementation commit will stack on top of `d8cea08`.

**Verification:** `git log --oneline -3` shows `d8cea08 docs: align tamperguard v0 spec` at HEAD before new changes.

---

### Task 0.2: Verify Context7 MCP documentation path

**Objective:** Ensure docs lookups remain available before relying on SPL syntax assumptions.

**Files:** none.

**Read-only commands:**
```bash
hermes mcp test context7
```

Then query Context7 for Splunk docs before writing SPL-rendering behavior:
- `eval exp tonumber Splunk Enterprise 10.2`
- `inputlookup outputlookup CSV lookup Splunk Enterprise 10.2`
- `/servicesNS/{user}/{app}/data/transforms/lookups Splunk Enterprise 10.2`
- `savedsearches.conf Splunk Enterprise 10.2`

**Verification:** Save only a short private note in `reports/private/context7-doc-check-v0.md` during execution, not in public docs unless the citations are generic public URLs and contain no local data.

---

### Task 0.3: Verify Splunk MCP availability and explain any config mismatch

**Objective:** Ensure Hermes can actually use Splunk MCP before writing live-operation steps.

**Files:** none unless a documented config fix is needed and Ryan explicitly approves it.

**Read-only commands:**
```bash
hermes mcp list
hermes mcp test splunk-mcp-server
```

If `hermes mcp list` does not show Splunk but config contains `splunk-mcp-server`, inspect the non-secret config shape:
```bash
python3 - <<'PY'
from pathlib import Path
s=Path('/home/ryan/.hermes/config.yaml').read_text().splitlines()
for i,line in enumerate(s,1):
    if 'mcp_servers' in line or 'splunk' in line.lower() or 'context7' in line.lower():
        safe=line
        if any(x in safe.upper() for x in ['TOKEN','KEY','AUTHORIZATION','SECRET']):
            safe=safe.split(':',1)[0]+': [REDACTED]'
        print(f'{i}: {safe}')
PY
```

**Expected:** Splunk MCP is discoverable or there is an actionable config/profile issue. Do not print tokens.

**Blocker rule:** Do not run live Splunk extraction/deploy until Splunk MCP read/search works again.

---

## Phase 1 — Python project scaffold and hygiene gates

### Task 1.1: Add Python packaging scaffold

**Objective:** Create a testable Python package instead of ad hoc scripts.

**Files:**
- Create: `pyproject.toml`
- Create: `src/ai_tamperguard/__init__.py`
- Create: `tests/`

**Step 1: Write failing metadata/import test**

Create `tests/test_repo_hygiene.py`:
```python
from pathlib import Path


def test_package_imports():
    import ai_tamperguard

    assert ai_tamperguard.__version__


def test_private_paths_are_gitignored():
    gitignore = Path('.gitignore').read_text()
    for path in ['data/private/', 'models/private/', 'reports/private/', 'splunk/private/']:
        assert path in gitignore
```

**Step 2: Verify RED**

Run:
```bash
pytest tests/test_repo_hygiene.py -q
```

Expected: FAIL because package/scaffold or gitignore entries are incomplete.

**Step 3: Implement minimal scaffold**

Create `pyproject.toml` with project metadata, dependencies, and pytest config. Minimum dependencies:
```toml
[project]
name = "ai-tamperguard"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pandas",
  "scikit-learn",
  "jsonschema",
]

[project.optional-dependencies]
dev = ["pytest"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `src/ai_tamperguard/__init__.py`:
```python
__version__ = "0.1.0"
```

Patch `.gitignore` to include private paths.

**Step 4: Verify GREEN**

Run:
```bash
pytest tests/test_repo_hygiene.py -q
```

Expected: PASS.

**Commit:**
```bash
git add pyproject.toml src/ai_tamperguard/__init__.py tests/test_repo_hygiene.py .gitignore
git commit -m "chore: add tamperguard python scaffold"
```

---

### Task 1.2: Add public-safety scanner skeleton

**Objective:** Create a scanner that blocks obvious private artifacts and forbidden public claims.

**Files:**
- Create: `src/ai_tamperguard/public_safety.py`
- Create: `scripts/public_safety_scan.py`
- Test: `tests/test_public_safety.py`

**Step 1: Write failing tests**

Test cases:
- Fails on tracked path under `data/private/`.
- Fails on `.csv`, `.pkl`, `.joblib`, `.onnx`, `.mlmodel` outside allowed schema exceptions.
- Fails on forbidden public claim phrases from adversarial spec §3.
- Does not require committing private denylist terms.

**Example test:**
```python
from ai_tamperguard.public_safety import scan_paths


def test_blocks_private_generated_paths():
    findings = scan_paths(['data/private/windows/foo.csv'])
    assert any('private generated path' in f.reason for f in findings)


def test_blocks_forbidden_claim_text(tmp_path):
    p = tmp_path / 'README.md'
    p.write_text('This detects malicious activity')
    findings = scan_paths([str(p)])
    assert any('forbidden claim' in f.reason for f in findings)
```

**Step 2: Verify RED**

Run:
```bash
pytest tests/test_public_safety.py -q
```

Expected: FAIL because scanner does not exist.

**Step 3: Implement minimal scanner**

Implement a pure `scan_paths(paths: list[str]) -> list[Finding]` API and CLI wrapper. Do not scan `.git/`. Treat missing paths as findings only when explicitly passed.

**Step 4: Verify GREEN**

Run:
```bash
pytest tests/test_public_safety.py -q
python scripts/public_safety_scan.py README.md docs/v0-model-pipeline-spec.md docs/v0-model-pipeline-spec-adversarial.md
```

Expected: tests PASS; scanner exits 0 on current public docs.

**Commit:**
```bash
git add src/ai_tamperguard/public_safety.py scripts/public_safety_scan.py tests/test_public_safety.py
git commit -m "test: add public safety scanner"
```

---

## Phase 2 — Schema contracts

### Task 2.1: Add behavior-window schema

**Objective:** Make `actor_60m` window rows machine-validatable.

**Files:**
- Create: `schemas/behavior_window_v0.schema.json`
- Create/modify: `src/ai_tamperguard/schema.py`
- Test: `tests/test_schema_contracts.py`

**Step 1: Write failing schema tests**

Tests should assert:
- Valid row with 8+ numeric/boolean `feature_*` fields passes.
- Null feature fails.
- String feature fails.
- Wrong `window_type` fails.
- Public row containing `actor_surrogate_private` fails when validating for public/export mode.

**Step 2: Verify RED**

Run:
```bash
pytest tests/test_schema_contracts.py::test_valid_behavior_window_passes -q
```

Expected: FAIL because schema helper/file does not exist.

**Step 3: Implement**

Add JSON Schema and helper functions:
```python
def load_schema(name: str) -> dict: ...
def validate_behavior_window(row: dict, *, public: bool = False) -> None: ...
```

**Step 4: Verify GREEN**

Run:
```bash
pytest tests/test_schema_contracts.py -q
```

Expected: PASS.

**Commit:**
```bash
git add schemas/behavior_window_v0.schema.json src/ai_tamperguard/schema.py tests/test_schema_contracts.py
git commit -m "feat: add behavior window schema"
```

---

### Task 2.2: Add model artifact and holdout fixture schemas

**Objective:** Encode the single-source-of-truth artifact contract and private/public fixture split.

**Files:**
- Create: `schemas/model_artifact_v0.schema.json`
- Create: `schemas/holdout_fixture_v0.schema.json`
- Modify: `src/ai_tamperguard/schema.py`
- Test: `tests/test_schema_contracts.py`

**Tests:**
- Valid artifact requires `model_version`, `feature_order`, `intercept`, `coefficients`, `threshold`, `label_rule_id`, `training_metadata`, `score_envelope`.
- Coefficient length must equal `feature_order` length.
- Threshold outside `[0, 1]` fails.
- Holdout fixture must include `window_id` plus all features.
- Private expected columns `score_local`, `probability_local`, `prediction_local` allowed only in private fixture validation.

**Verification:**
```bash
pytest tests/test_schema_contracts.py -q
```

**Commit:**
```bash
git add schemas/model_artifact_v0.schema.json schemas/holdout_fixture_v0.schema.json src/ai_tamperguard/schema.py tests/test_schema_contracts.py
git commit -m "feat: add v0 artifact schemas"
```

---

## Phase 3 — Feature extraction and weak labels

### Task 3.1: Implement row normalization for Splunk events

**Objective:** Convert heterogeneous `_audit` / `_configtracker` events into safe normalized inputs for window aggregation.

**Files:**
- Create: `src/ai_tamperguard/features.py`
- Test: `tests/test_features.py`

**Step 1: Write failing tests**

Use synthetic rows only. Tests should cover:
- `_audit` action/search/status fields normalize into controlled fields.
- `_configtracker` config-change rows increment config/admin counters.
- Raw usernames/object names are not copied into public feature fields.
- Missing fields become `unknown` or zero; no null feature values.

**Step 2: Verify RED**

Run:
```bash
pytest tests/test_features.py -q
```

Expected: FAIL.

**Step 3: Implement minimal normalization**

Suggested API:
```python
def normalize_event(raw: dict) -> dict: ...
def actor_surrogate(raw: dict, salt: str) -> str: ...
```

Do not include raw username in public output. Use salted hash for private grouping.

**Step 4: Verify GREEN**

Run:
```bash
pytest tests/test_features.py -q
```

Expected: PASS.

**Commit:**
```bash
git add src/ai_tamperguard/features.py tests/test_features.py
git commit -m "feat: normalize splunk control-plane events"
```

---

### Task 3.2: Implement `actor_60m` aggregation

**Objective:** Convert normalized events into behavior-window rows.

**Files:**
- Modify: `src/ai_tamperguard/features.py`
- Test: `tests/test_features.py`

**Tests:**
- Two events for same actor in same UTC hour produce one row.
- Events in different hours produce separate windows.
- Feature counts aggregate correctly.
- Boolean features are `0` / `1` ints.
- Feature set is stable and contains 8–20 `feature_*` columns.

**Suggested API:**
```python
def build_actor_60m_windows(events: list[dict], *, salt: str, source_dataset: str) -> list[dict]: ...
```

**Verification:**
```bash
pytest tests/test_features.py -q
```

**Commit:**
```bash
git add src/ai_tamperguard/features.py tests/test_features.py
git commit -m "feat: build actor 60m behavior windows"
```

---

### Task 3.3: Implement deterministic weak-label rule

**Objective:** Provide exactly one first-run proxy label rule.

**Files:**
- Create: `src/ai_tamperguard/labels.py`
- Test: `tests/test_labels.py`

**First-run label rule default:**
`label_binary = 1` if any of these are true:
- `feature_admin_action_count > 0`
- `feature_config_action_count > 0`
- `feature_token_or_rbac_action_count > 0`
- `feature_index_or_input_action_count > 0`
- `feature_after_hours_admin_activity == 1`

Otherwise `label_binary = 0`.

**Rationale:** This creates a `working_model_positive_proxy` class for admin/control-plane activity. It is not malicious.

**Tests:**
- Normal search-only window labels `0`.
- Admin/config/token/RBAC window labels `1`.
- Label output includes `label`, `label_binary`, `label_source`, and `label_confidence` or omits confidence consistently.
- `label_rule_id` and `label_rule_description` are stable strings.

**Verification:**
```bash
pytest tests/test_labels.py -q
```

**Commit:**
```bash
git add src/ai_tamperguard/labels.py tests/test_labels.py
git commit -m "feat: add v0 weak label rule"
```

---

### Task 3.4: Add extraction CLI for private exports

**Objective:** Create the reproducible private extraction entrypoint without requiring live Splunk in unit tests.

**Files:**
- Create: `scripts/extract_windows_v0.py`
- Modify: `src/ai_tamperguard/features.py`
- Test: `tests/test_features.py`

**CLI behavior:**
```bash
python scripts/extract_windows_v0.py \
  --input data/private/raw_exports/v0_raw_events.jsonl \
  --output data/private/windows/tamperguard_windows_v0.csv \
  --salt-file data/private/window_salt.txt
```

**Tests:**
- Use `tmp_path` JSONL fixture.
- Verify output CSV has no nulls.
- Verify no raw username/object/path columns appear.
- Verify schema validation passes.

**Verification:**
```bash
pytest tests/test_features.py -q
python scripts/extract_windows_v0.py --help
```

**Commit:**
```bash
git add scripts/extract_windows_v0.py src/ai_tamperguard/features.py tests/test_features.py
git commit -m "feat: add v0 window extraction cli"
```

---

## Phase 4 — Deterministic holdout split

### Task 4.1: Implement deterministic train/holdout split

**Objective:** Persist holdout before training and prevent training from reading holdout rows.

**Files:**
- Create: `src/ai_tamperguard/split.py`
- Create: `scripts/split_holdout_v0.py`
- Test: `tests/test_split.py`

**Tests:**
- Split is deterministic for same input and seed.
- Train and holdout `window_id` sets are disjoint.
- Stratified split preserves both classes when available.
- Fails loud if either class has zero rows.
- Writes split manifest with `random_seed`, counts, and file hashes.

**Suggested CLI:**
```bash
python scripts/split_holdout_v0.py \
  --input data/private/windows/tamperguard_windows_v0.csv \
  --train-output data/private/windows/tamperguard_windows_v0_train.csv \
  --holdout-output data/private/holdout/tamperguard_windows_holdout_proxy.csv \
  --manifest-output data/private/holdout/split_manifest_v0.json \
  --seed 20260524
```

**Verification:**
```bash
pytest tests/test_split.py -q
python scripts/split_holdout_v0.py --help
```

**Commit:**
```bash
git add src/ai_tamperguard/split.py scripts/split_holdout_v0.py tests/test_split.py
git commit -m "feat: add deterministic holdout split"
```

---

## Phase 5 — Local logistic regression training

### Task 5.1: Implement training artifact creation

**Objective:** Train logistic regression and emit the single source-of-truth artifact.

**Files:**
- Create: `src/ai_tamperguard/train.py`
- Create: `scripts/train_v0_logistic_regression.py`
- Test: `tests/test_train.py`

**Tests:**
- Training on synthetic separable rows emits artifact with required keys.
- `feature_order` equals the input feature manifest exactly.
- `coefficients` length equals `feature_order` length.
- `model_version` changes when feature data fingerprint changes.
- Artifact includes `label_rule_id`, `label_rule_description`, `training_metadata`, and `score_envelope`.
- G2 anti-degeneracy metrics are computed: nonzero coefficient count, holdout probability std, predicted-class distribution.

**Suggested CLI:**
```bash
python scripts/train_v0_logistic_regression.py \
  --train data/private/windows/tamperguard_windows_v0_train.csv \
  --holdout data/private/holdout/tamperguard_windows_holdout_proxy.csv \
  --artifact models/private/tamperguard_v0_model.json \
  --expected-holdout data/private/holdout/tamperguard_windows_holdout_proxy_expected.csv \
  --seed 20260524
```

**Verification:**
```bash
pytest tests/test_train.py -q
python scripts/train_v0_logistic_regression.py --help
```

**Commit:**
```bash
git add src/ai_tamperguard/train.py scripts/train_v0_logistic_regression.py tests/test_train.py
git commit -m "feat: train v0 logistic regression artifact"
```

---

### Task 5.2: Add local diagnostics report generation

**Objective:** Produce private plumbing diagnostics without overclaiming detection quality.

**Files:**
- Modify: `src/ai_tamperguard/train.py`
- Create: `reports/v0-smoke-test-template.md`
- Test: `tests/test_train.py`

**Tests:**
- Report includes heading `Plumbing diagnostics (not detection quality)`.
- Report includes explicit `this is not a tamper detector` disclaimer.
- Report includes G1/G2 numbers but no raw usernames/hostnames/SPL.

**Verification:**
```bash
pytest tests/test_train.py -q
```

**Commit:**
```bash
git add src/ai_tamperguard/train.py reports/v0-smoke-test-template.md tests/test_train.py
git commit -m "feat: add v0 private report template"
```

---

## Phase 6 — SPL scoring renderer

### Task 6.1: Render scoring SPL from model artifact

**Objective:** Generate SPL that uses explicit feature order and `tonumber()` conversions.

**Files:**
- Create: `src/ai_tamperguard/render_spl.py`
- Create: `scripts/render_splunk_scoring_artifact_v0.py`
- Create: `splunk/searches/score_v0_logistic_regression_template.spl`
- Test: `tests/test_render_spl.py`

**Context7 doc check before implementation:** Re-query docs for `eval exp`, `tonumber`, and `inputlookup` to confirm syntax.

**Tests:**
- Rendered SPL contains one `tonumber(<feature>)` conversion per feature.
- Rendered SPL contains `1 / (1 + exp(-score))`.
- Rendered SPL embeds `model_version` but no private hostname/user/path.
- Rendered SPL does not contain `fit`, `apply`, `score`, `onnx`, `.mlmodel`, or Python custom commands.
- Feature order in rendered SPL matches artifact order exactly.

**Suggested CLI:**
```bash
python scripts/render_splunk_scoring_artifact_v0.py \
  --artifact models/private/tamperguard_v0_model.json \
  --lookup tamperguard_windows_holdout_proxy.csv \
  --output splunk/private/score_tamperguard_v0_model.spl
```

**Verification:**
```bash
pytest tests/test_render_spl.py -q
python scripts/render_splunk_scoring_artifact_v0.py --help
```

**Commit:**
```bash
git add src/ai_tamperguard/render_spl.py scripts/render_splunk_scoring_artifact_v0.py splunk/searches/score_v0_logistic_regression_template.spl tests/test_render_spl.py
git commit -m "feat: render no-ml-app spl scoring"
```

---

### Task 6.2: Add synthetic SPL equivalence fixture

**Objective:** Validate Python and rendered SPL math shape before touching private data.

**Files:**
- Modify: `tests/test_render_spl.py`
- Modify: `src/ai_tamperguard/render_spl.py`

**Tests:**
- Given tiny artifact and fixture, expected score/probability are deterministic.
- Renderer and local scoring helper agree exactly for score and within tolerance for probability.
- Tolerance default is `1e-6`, but exposed as a named constant/config.

**Verification:**
```bash
pytest tests/test_render_spl.py -q
```

**Commit:**
```bash
git add src/ai_tamperguard/render_spl.py tests/test_render_spl.py
git commit -m "test: add synthetic scoring equivalence fixture"
```

---

## Phase 7 — Local-vs-Splunk verification harness

### Task 7.1: Implement comparison harness

**Objective:** Compare Splunk scoring output to private local expected values.

**Files:**
- Create: `src/ai_tamperguard/verify.py`
- Create: `scripts/verify_local_vs_splunk_v0.py`
- Test: `tests/test_verify.py`

**Tests:**
- Exact matching predictions pass.
- Probability residual above tolerance fails.
- Score residual above tolerance fails.
- `scored_at` is ignored.
- `model_version` must match as a string but is not numerically compared.
- Missing `window_id` on either side fails.

**Suggested CLI:**
```bash
python scripts/verify_local_vs_splunk_v0.py \
  --expected data/private/holdout/tamperguard_windows_holdout_proxy_expected.csv \
  --splunk-results data/private/holdout/tamperguard_windows_holdout_proxy_splunk_scored.csv \
  --artifact models/private/tamperguard_v0_model.json \
  --report reports/private/v0-smoke-test-<model_version>.md \
  --tolerance 1e-6
```

**Verification:**
```bash
pytest tests/test_verify.py -q
python scripts/verify_local_vs_splunk_v0.py --help
```

**Commit:**
```bash
git add src/ai_tamperguard/verify.py scripts/verify_local_vs_splunk_v0.py tests/test_verify.py
git commit -m "feat: verify local and splunk scoring equivalence"
```

---

## Phase 8 — Live Splunk read-only probes

### Task 8.1: Probe Splunk version and available sourcetypes through MCP

**Objective:** Confirm live Splunk still matches assumptions before extraction.

**Files:**
- Create private only during execution: `reports/private/splunk-readiness-v0.md`

**Splunk searches to run through MCP:**
```spl
| rest /services/server/info
| table version build os_name cpu_arch
```

```spl
| tstats count where index=_audit sourcetype=audittrail earliest=-30d@d latest=now by sourcetype
```

```spl
| tstats count where index=_configtracker sourcetype=splunk_configuration_change earliest=-30d@d latest=now by sourcetype
```

**Verification:**
- Version major.minor is `10.2`.
- `_audit/audittrail` exists and has nonzero count or explicit blocker noted.
- `_configtracker/splunk_configuration_change` exists and has nonzero count or explicit blocker noted.
- Output is private and not committed.

**Commit:** none; private report only.

---

### Task 8.2: Probe fields needed for extraction

**Objective:** Discover actual field names without exporting raw private data publicly.

**Splunk searches to run through MCP:**
```spl
search index=_audit sourcetype=audittrail earliest=-30d@d latest=now
| fields - _raw
| fieldsummary
| table field count distinct_count
```

```spl
search index=_configtracker sourcetype=splunk_configuration_change earliest=-30d@d latest=now
| fields - _raw
| fieldsummary
| table field count distinct_count
```

**Private output:** `reports/private/splunk-field-probe-v0.md`.

**Implementation follow-up:** If actual fields differ from assumptions, patch `src/ai_tamperguard/features.py` and tests before private extraction.

---

### Task 8.3: Probe `actor_60m` volume before training

**Objective:** Evaluate adversarial G1 before training.

**Splunk MCP search shape:**
```spl
search (index=_audit sourcetype=audittrail OR index=_configtracker sourcetype=splunk_configuration_change) earliest=-30d@d latest=now
| eval actor=coalesce(user, user_name, username, "unknown")
| bin _time span=60m
| stats count as feature_event_count by actor _time sourcetype
| stats count as window_count by actor _time
| stats count as total_windows
```

Then run a closer query if the proxy label can be approximated in SPL. Otherwise export private field-limited data and compute G1 in Python.

**Verification:**
- Record total windows and per-class counts in `reports/private/splunk-volume-probe-v0.md`.
- If `<200` total or `<20` in either class, stop and decide: widen time range/window or revise proxy rule. Do not silently lower thresholds.

---

## Phase 9 — Private run sequence

### Task 9.1: Export field-limited private raw rows

**Objective:** Create private input for the pure extractor.

**Output:** `data/private/raw_exports/v0_raw_events.jsonl`.

**Rules:**
- Exclude `_raw` unless absolutely needed for a private debugging pass.
- Export only fields required for features/labels plus timestamps/sourcetype/source markers.
- Do not commit output.

**Verification:**
```bash
git status --short -- data/private models/private reports/private splunk/private
```

Expected: no tracked files; generated files are ignored or untracked in ignored paths only.

---

### Task 9.2: Run private extraction/split/train/render locally

**Objective:** Produce the private model artifact, expected holdout, and private rendered SPL.

**Commands:**
```bash
python scripts/extract_windows_v0.py \
  --input data/private/raw_exports/v0_raw_events.jsonl \
  --output data/private/windows/tamperguard_windows_v0.csv \
  --salt-file data/private/window_salt.txt

python scripts/split_holdout_v0.py \
  --input data/private/windows/tamperguard_windows_v0.csv \
  --train-output data/private/windows/tamperguard_windows_v0_train.csv \
  --holdout-output data/private/holdout/tamperguard_windows_holdout_proxy.csv \
  --manifest-output data/private/holdout/split_manifest_v0.json \
  --seed 20260524

python scripts/train_v0_logistic_regression.py \
  --train data/private/windows/tamperguard_windows_v0_train.csv \
  --holdout data/private/holdout/tamperguard_windows_holdout_proxy.csv \
  --artifact models/private/tamperguard_v0_model.json \
  --expected-holdout data/private/holdout/tamperguard_windows_holdout_proxy_expected.csv \
  --seed 20260524

python scripts/render_splunk_scoring_artifact_v0.py \
  --artifact models/private/tamperguard_v0_model.json \
  --lookup tamperguard_windows_holdout_proxy.csv \
  --output splunk/private/score_tamperguard_v0_model.spl
```

**Verification:**
- G1 and G2 pass.
- Private expected holdout has `score_local`, `probability_local`, `prediction_local`.
- Rendered SPL contains no raw usernames/hostnames/private paths.
- No generated artifacts are tracked.

---

## Phase 10 — Deployment path and Splunk scoring

### Task 10.1: Choose exactly one approved write path

**Objective:** Avoid ad hoc deployment.

**Decision order:**
1. If Splunk MCP exposes a narrow app-scoped artifact write tool, use it.
2. Else if Splunk REST scoped credentials are available, use `/servicesNS/{user}/ai_tamperguard/...` endpoints with credentials outside repo.
3. Else use app filesystem packaging / `.spl` app bundle and install via documented Splunk CLI path.

**Context7 doc check:** Confirm the chosen endpoint or config-file path via Splunk docs before implementing deploy code.

**Private record:** `reports/private/deploy-path-decision-v0.md`.

---

### Task 10.2: Deploy held-out fixture and scoring artifact

**Objective:** Put exactly the required private runtime artifacts into `ai_tamperguard`.

**Deploy artifacts:**
- Held-out fixture lookup without local expected columns.
- Rendered scoring SPL or saved search.
- Model metadata lookup/artifact if needed for read-back audit.

**Audit log:** `reports/private/deploy-<model_version>.log` includes:
- timestamp
- operator
- write path used
- artifact names
- SHA-256 hashes
- MCP read-back confirmation

**Verification:** Use Splunk MCP read/search to confirm artifacts exist in the expected app namespace.

---

### Task 10.3: Run Splunk-side scoring and retrieve result

**Objective:** Generate Splunk-side scores for held-out rows.

**SPL shape:**
```spl
| inputlookup tamperguard_windows_holdout_proxy.csv
| eval feature_event_count = tonumber(feature_event_count)
| eval ...
| eval score = <intercept> + (<coef_1> * feature_1) + ...
| eval probability = 1 / (1 + exp(-score))
| eval prediction = if(probability >= <threshold>, 1, 0)
| eval model_version = "<model_version>", scored_at = now()
| table window_id score probability prediction model_version scored_at
```

**Output:** Save returned rows privately as `data/private/holdout/tamperguard_windows_holdout_proxy_splunk_scored.csv`.

**Verification:**
- Row count matches private holdout fixture.
- No unexpected NULL scores/probabilities.
- `model_version` matches artifact.

---

## Phase 11 — Equivalence, report, rollback

### Task 11.1: Run local-vs-Splunk verification

**Objective:** Enforce G6.

**Command:**
```bash
python scripts/verify_local_vs_splunk_v0.py \
  --expected data/private/holdout/tamperguard_windows_holdout_proxy_expected.csv \
  --splunk-results data/private/holdout/tamperguard_windows_holdout_proxy_splunk_scored.csv \
  --artifact models/private/tamperguard_v0_model.json \
  --report reports/private/v0-smoke-test-<model_version>.md \
  --tolerance 1e-6
```

**Pass criteria:**
- `abs(score_local - score_splunk) <= 1e-6` for every row, unless empirically revised in a documented follow-up.
- `abs(probability_local - probability_splunk) <= 1e-6` for every row, unless empirically revised.
- `prediction_local == prediction_splunk` for 100% of rows.

**If fail:** Do not tune blindly. Inspect feature ordering, `tonumber()` conversion, missing columns, coefficient precision, and score envelope.

---

### Task 11.2: Run public safety and repo hygiene checks

**Objective:** Prevent private artifact leakage.

**Commands:**
```bash
pytest tests/ -q
python scripts/public_safety_scan.py $(git ls-files)
git status --short -- data/private models/private reports/private splunk/private
```

**Expected:**
- Tests pass.
- Public-safety scan exits 0.
- No private/generated paths are tracked.

---

### Task 11.3: Exercise rollback

**Objective:** Prove deployed artifacts are removable.

**Steps:**
1. Use the same approved write path to remove deployed lookups/saved searches/artifacts for this `model_version`.
2. Re-read via Splunk MCP and confirm artifact names no longer resolve, except intentionally retained templates.
3. Append rollback record to `reports/private/deploy-<model_version>.log`.

**Verification:** G5 is incomplete until rollback is exercised.

---

## Phase 12 — Final public commit(s)

### Task 12.1: Commit only public implementation artifacts

**Objective:** Commit code/templates/schemas/tests, not private run outputs.

**Commands:**
```bash
git status --short
python scripts/public_safety_scan.py $(git ls-files)
pytest tests/ -q
git add pyproject.toml src scripts schemas splunk/searches tests reports/v0-smoke-test-template.md README.md .gitignore
git status --short
git commit -m "feat: implement tamperguard v0 scoring pipeline"
```

**Verification:**
```bash
git show --stat --oneline HEAD
git status --short --branch
```

Expected: no private paths in commit.

---

### Task 12.2: Optional push

**Objective:** Publish public-safe code after verification.

**Command:**
```bash
git push origin main
```

**Verification:**
```bash
git status --short --branch
```

Expected: branch clean and synced.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Splunk MCP not currently visible in `hermes mcp list` | Resolve config/profile issue before live tasks. Do not fake live verification. |
| Generic MCP `outputlookup` remains blocked | Treat as intended safety. Use narrow app-scoped MCP, scoped REST, or app packaging with audit. |
| `actor_60m` has too few rows | Stop after G1 probe; decide window/range/proxy change explicitly. |
| Weak labels overclaimed | Keep `working_model_positive_proxy` wording in artifact/report/SPL comments. Public-safety scanner blocks forbidden claims. |
| Local/Splunk numeric residual exceeds `1e-6` | Measure residual on synthetic fixture, document reason, revise tolerance explicitly. |
| Feature ordering drift | Model artifact `feature_order` is source of truth; renderer and verifier assert exact match. |
| Private data leak | Ignore private paths, public-safety scan, no sample data in v0, private scanner terms uncommitted. |
| All-green but meaningless model | Enforce G2: nonzero coefficients, probability std, both predicted classes, both true classes in holdout. Lobster side-eye mandatory. |

---

## Open questions before execution

1. Should I push the current docs commit `d8cea08` before starting implementation, or stack implementation locally first?
2. If Splunk MCP remains absent from `hermes mcp list`, should I repair the MCP config/profile as part of implementation, or pause for Ryan approval?
3. For deployment, should the first preference be a narrow MCP extension, scoped REST, or app filesystem packaging if all are technically possible?

Recommended defaults:
- Push the docs commit first for safety.
- Repair Splunk MCP read-only availability before implementation continues.
- Prefer narrow MCP extension; if not available quickly, use scoped REST or app packaging and validate through MCP.

---

## Execution handoff

Plan complete. When Ryan says to proceed, execute in small commits using strict TDD for code tasks. Start with Phase 0 preflight, then Phase 1 scaffold. Do not touch private Splunk extraction/deployment until unit tests, schema contracts, public-safety scan, Context7 doc checks, and Splunk MCP read-only readiness are green.
