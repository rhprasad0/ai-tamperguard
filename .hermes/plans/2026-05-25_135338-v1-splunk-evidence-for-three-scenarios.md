# AI TamperGuard V1 Splunk Evidence Seeding + Capture Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the next V1 live smoke for `scenario_004_run_001`, `scenario_007_run_001`, and `scenario_010_run_001` collect actual Splunk-indexed scenario evidence instead of only scaffold rows.

**Architecture:** Add a private-gated Splunk evidence seeding/export path. The seeder writes public-safe synthetic scenario evidence into the sacrificial `openclaw_tamper_lab` index with `batch_id`, `scenario_id`, `scenario_run_id`, and `reset_id`; the capture path then queries Splunk for those rows and normalizes the returned Splunk data. Protected indexes (`_audit`, `_configtracker`, `agentops`) remain read-only evidence surfaces.

**Tech Stack:** Python 3.14/uv, pytest, httpx, Splunk HEC/REST or an injectable fake transport for tests, existing V1 scripts under `v1/scripts/`, existing schema/validation pipeline.

---

## Current context / assumptions

- Repo root: `/home/ryan/projects/ai-tamperguard`.
- V1 scripts and tests already exist under `v1/`.
- Current `capture_splunk_run_v1.py` emits deterministic scaffold rows from reset metadata.
- The last batch `v1_live_smoke_20260525T134111Z` proved the pipeline works in smoke mode but found **zero direct Splunk rows** for the three scenario run IDs.
- Required live-readiness indexes are present from prior readiness checks: `_audit`, `_configtracker`, and `openclaw_tamper_lab`; optional `agentops` is present but not required for this step.
- This plan does **not** include Graphiti persistence. If later added, use confirmed group `policy-bonfire-2` only after Ryan reviews/accepts a run summary.
- Ryan resolved the prior open question about Splunk write credentials: default to Splunk HEC for sacrificial writes, with the HEC token read from `.env` / environment variable `AI_TAMPERGUARD_SPLUNK_HEC_TOKEN` only. Do not commit token values or print them.
- Default for verification/search remains conservative: use Splunk MCP or an explicitly private search config for readback; if direct script-level Splunk search needs separate auth, add it as an env-var reference only, never as an inline secret.

## Safety boundaries

- Only mutatable Splunk surface: `index=openclaw_tamper_lab`.
- Do not clear, delete, or mutate `_audit`, `_configtracker`, `agentops`, or other protected indexes.
- Do not print or commit Splunk tokens, usernames, hostnames, raw SPL containing private object names, URLs, or private artifact names.
- Private config stays under `v1/splunk/private/` and remains gitignored.
- Public artifacts may contain only public-safe IDs: `batch_id`, `scenario_id`, `scenario_run_id`, `reset_id`, `actor_...`, `object_...`, `evt_...`, `private_ref_...`.
- Use a fresh `BATCH=v1_live_smoke_YYYYMMDDTHHMMSSZ`; do not reuse the failed batch except as historical evidence.
- Use absolute time anchors and scenario IDs; do not destructively clear old Splunk data.

## Proposed approach

Add two capabilities:

1. **Seed Splunk scenario evidence**
   - New script: `v1/scripts/seed_splunk_scenario_evidence_v1.py`.
   - It validates private config + inventory + reset manifest.
   - It generates the same public-safe event shapes currently produced by `_scenario_events(...)` in `capture_splunk_run_v1.py`.
   - It writes those events into `openclaw_tamper_lab` through a private Splunk writer, likely HEC.
   - It writes a private seed manifest under `v1/data/private/seed_manifests/${BATCH}/${SCENARIO_RUN_ID}.json`.

2. **Capture actual Splunk-indexed rows**
   - Modify `v1/scripts/capture_splunk_run_v1.py` so it can query Splunk for `scenario_run_id` rows in `openclaw_tamper_lab`.
   - If rows exist, convert returned rows into normalized private public-safe event rows and set capture status to `captured_live_splunk_public_safe`.
   - If rows are missing, fail closed by default for live mode; allow scaffold fallback only behind an explicit flag such as `--allow-scaffold-fallback`.

This turns the loop into:

```text
reset manifest
→ seed public-safe scenario evidence into openclaw_tamper_lab
→ verify Splunk sees scenario_run_id rows
→ run Openclaw runner
→ capture real Splunk rows
→ normalize / derive / validate
```

---

## Step-by-step plan

### Task 1: Factor scenario event generation into a reusable module

**Objective:** Avoid duplicating event specs between seeding and capture.

**Files:**
- Create: `v1/src/ai_tamperguard_v1/scenario_events.py`
- Modify: `v1/scripts/capture_splunk_run_v1.py`
- Test: `v1/tests/test_scenario_events_v1.py`

**Implementation notes:**

Move these current concepts out of `capture_splunk_run_v1.py`:

- `ACTORS`
- `_scenario_id_from_run`
- `_scenario_events`
- `_event_specs`
- `_read`
- `_change`
- `_report`
- `_probe`

Export a small public API:

```python
def scenario_id_from_run(scenario_run_id: str) -> str: ...

def scenario_actor_id(scenario_id: str) -> str: ...

def public_safe_scenario_events(
    *,
    scenario_id: str,
    scenario_run_id: str,
    actor_id: str | None = None,
    artifact_ids: tuple[str, ...] = (),
) -> list[dict[str, Any]]: ...
```

**Tests:**

- `scenario_004_run_001` yields 3 events.
- `scenario_007_run_001` yields 2 events.
- `scenario_010_run_001` yields 4 events.
- Every event has:
  - `scenario_run_id`
  - `scenario_id`
  - `event_id`
  - `raw_event_ref` beginning with `private_ref_`
  - `redaction_level == "public_safe"`
  - `source_derivation == "live_lab_public_redacted"`
- No event contains obvious private fields such as `private_name`, `host`, `user`, `url`, `token`, or `_raw`.

**Verification command:**

```bash
cd /home/ryan/projects/ai-tamperguard
uv run --directory v1 pytest -q tests/test_scenario_events_v1.py tests/test_capture_splunk_run_v1.py
```

Expected: pass.

---

### Task 2: Add private Splunk connection config parsing

**Objective:** Allow live writes/searches only when private config explicitly authorizes them.

**Files:**
- Modify: `v1/src/ai_tamperguard_v1/lab_config.py`
- Test: `v1/tests/test_lab_config_v1.py`

**Config shape to support in `v1/splunk/private/lab.toml`:**

```toml
[splunk_hec]
url = "<private HEC endpoint>"
token_env = "AI_TAMPERGUARD_SPLUNK_HEC_TOKEN"
index = "openclaw_tamper_lab"
sourcetype = "ai_tamperguard:v1:scenario_evidence"
source = "ai_tamperguard:v1:seed"

# Optional only if direct script-level REST search is implemented instead of using Splunk MCP
# for readback verification. If added, use env-var references only; never inline credentials.
[splunk_search]
url = "<private Splunk management/search endpoint>"
token_env = "AI_TAMPERGUARD_SPLUNK_SEARCH_TOKEN"
```

**Important:** the plan does not require committing real endpoint values. Tests should use temp TOML fixtures and fake env vars.

**Validation rules:**

- `splunk_hec.index` must equal `openclaw_tamper_lab`.
- `splunk_hec.token_env` must be an env-var name, not a raw token value.
- `splunk_hec.sourcetype` must be a safe literal, recommended `ai_tamperguard:v1:scenario_evidence`.
- Missing `[splunk_hec]` should not break existing fixture tests; live seeding will fail closed if it is missing.
- `load_lab_config(...)` must never print resolved token values.

**Verification command:**

```bash
uv run --directory v1 pytest -q tests/test_lab_config_v1.py
```

Expected: pass.

---

### Task 3: Create a Splunk I/O helper with fakeable transports

**Objective:** Centralize HEC write and scenario-run search logic behind testable functions.

**Files:**
- Create: `v1/src/ai_tamperguard_v1/splunk_io.py`
- Test: `v1/tests/test_splunk_io_v1.py`

**API sketch:**

```python
@dataclass(frozen=True)
class SplunkWriteResult:
    status: str
    event_count: int
    request_id: str | None = None

@dataclass(frozen=True)
class SplunkSearchResult:
    status: str
    rows: list[dict[str, Any]]

class SplunkIoError(RuntimeError):
    pass

def write_scenario_events_hec(
    *,
    config: LabConfig,
    events: list[dict[str, Any]],
    batch_id: str,
    dry_run: bool = False,
    http_client: Any | None = None,
) -> SplunkWriteResult: ...

def search_scenario_events(
    *,
    config: LabConfig,
    scenario_run_id: str,
    earliest_epoch: int,
    latest: str = "now",
    http_client: Any | None = None,
) -> SplunkSearchResult: ...
```

**Safety requirements:**

- HEC payload must set target index to `openclaw_tamper_lab` only.
- HEC event body contains public-safe fields only.
- Reject events missing `scenario_run_id`, `scenario_id`, `event_id`, or `redaction_level=public_safe`.
- Reject any event with `_raw`, `host`, `user`, `username`, `private_name`, `token`, `password`, `url`, or `uri` keys.
- `dry_run=True` validates and returns count without network.
- Error messages must redact URLs/tokens.

**Search behavior:**

Search only the sacrificial index for captured seeded rows:

```text
index=openclaw_tamper_lab scenario_run_id="<scenario_run_id>"
```

Do not embed raw private object names. The code may render the query internally, but reports should store only query hash/summary, not raw query text.

**Verification command:**

```bash
uv run --directory v1 pytest -q tests/test_splunk_io_v1.py
```

Expected: pass with fake http clients only.

---

### Task 4: Add `seed_splunk_scenario_evidence_v1.py`

**Objective:** Write public-safe scenario evidence rows into Splunk for one scenario run.

**Files:**
- Create: `v1/scripts/seed_splunk_scenario_evidence_v1.py`
- Test: `v1/tests/test_seed_splunk_scenario_evidence_v1.py`

**CLI shape:**

```bash
uv run --directory v1 python scripts/seed_splunk_scenario_evidence_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial_inventory.toml \
  --scenario scenario_004 \
  --scenario-run-id scenario_004_run_001 \
  --reset-id reset_004_001 \
  --batch-id "$BATCH" \
  --anchor-epoch "$RUN_ANCHOR_EPOCH" \
  --output-manifest data/private/seed_manifests/${BATCH}/scenario_004_run_001.json
```

**Behavior:**

1. Load and validate private lab config.
2. Load sacrificial inventory and select artifacts for the scenario.
3. Require the reset manifest at `data/private/resets/<reset_id>.json`.
4. Generate public-safe scenario events via `public_safe_scenario_events(...)`.
5. Add top-level fields to each event before writing to Splunk:
   - `batch_id`
   - `reset_id`
   - `seed_anchor_epoch`
   - `seed_source = "ai_tamperguard_v1_seed"`
6. Write events to Splunk HEC unless `--dry-run` is passed.
7. Write a private seed manifest containing only public-safe IDs and counts.

**Tests:**

- Dry-run for each of the three scenarios emits the expected count:
  - `scenario_004`: 3
  - `scenario_007`: 2
  - `scenario_010`: 4
- Rejects scenario/run mismatch.
- Rejects missing reset manifest.
- Rejects output manifest outside `data/private/seed_manifests`.
- Rejects config where HEC target index is not `openclaw_tamper_lab`.
- Does not include private inventory `private_name` in emitted event bodies or manifest.

**Verification command:**

```bash
uv run --directory v1 pytest -q tests/test_seed_splunk_scenario_evidence_v1.py tests/test_splunk_io_v1.py
```

Expected: pass.

---

### Task 5: Modify capture to prefer Splunk rows and fail closed in live mode

**Objective:** Make capture prove it is using Splunk data when Splunk rows exist.

**Files:**
- Modify: `v1/scripts/capture_splunk_run_v1.py`
- Modify: `v1/tests/test_capture_splunk_run_v1.py`

**CLI additions:**

```bash
--batch-id "$BATCH"
--earliest-epoch "$RUN_ANCHOR_EPOCH"
--require-live-splunk-rows
--allow-scaffold-fallback  # only for fixture/offline tests, not live runs
```

**Behavior:**

1. Validate config/reset as today.
2. If `--require-live-splunk-rows` is set:
   - Query `openclaw_tamper_lab` for `scenario_run_id` at/after `earliest_epoch`.
   - If zero rows, exit `2` with a public-safe error like: `no live Splunk rows found for scenario_run_id`.
3. If rows exist:
   - Convert returned rows into `public_safe_events_private.jsonl`.
   - Preserve only schema-approved public-safe fields.
   - Set capture manifest:

```json
{
  "status": "captured_live_splunk_public_safe",
  "source_derivation": "live_splunk_public_redacted",
  "source_index": "openclaw_tamper_lab",
  "event_count": 3,
  "public_release_ready": false,
  "public_release_blocker": "requires review before release-candidate promotion"
}
```

4. If `--allow-scaffold-fallback` is set and no rows exist, retain current scaffold behavior and manifest status `captured_private_public_safe_scaffold`.

**Tests:**

- Existing scaffold test still passes using `--allow-scaffold-fallback` or default fixture mode.
- New fake search test returns 3 rows and capture manifest status becomes `captured_live_splunk_public_safe`.
- `--require-live-splunk-rows` with fake zero rows fails closed.
- Captured rows are schema-valid normalized event rows.

**Verification command:**

```bash
uv run --directory v1 pytest -q tests/test_capture_splunk_run_v1.py tests/test_splunk_io_v1.py
```

Expected: pass.

---

### Task 6: Add a three-scenario live evidence runbook script

**Objective:** Reduce copy/paste risk for the exact three-scenario batch.

**Files:**
- Create: `v1/scripts/run_three_scenario_splunk_evidence_batch_v1.py`
- Test: `v1/tests/test_three_scenario_batch_v1.py`

**Scope:** This script may orchestrate local scripts, but should still support `--dry-run` and fake transports in tests.

**Scenario table:**

| scenario_id | scenario_run_id | reset_id | actor_id | family | outcome | paired_control_run_id |
|---|---|---|---|---|---|---|
| `scenario_004` | `scenario_004_run_001` | `reset_004_001` | `actor_001` | `benign_investigation` | `benign` | `null` |
| `scenario_007` | `scenario_007_run_001` | `reset_007_001` | `actor_003` | `permission_probe` | `blocked` | `null` |
| `scenario_010` | `scenario_010_run_001` | `reset_010_001` | `actor_001` | `evidence_laundering` | `needs_review` | `scenario_004_run_001` |

**Runbook behavior:**

For each scenario:

1. Record `RUN_ANCHOR_UTC` and `RUN_ANCHOR_EPOCH`.
2. Run `reset_lab_v1.py`.
3. Run `seed_splunk_scenario_evidence_v1.py`.
4. Verify through Splunk search that rows exist for the scenario run ID.
5. Run the Openclaw runner with Graphiti writes disabled.
6. Run capture with `--require-live-splunk-rows`.
7. Append a private run manifest row with schema-valid `outcome` values.

After all three:

8. Normalize.
9. Derive windows/episodes/edges/splits.
10. Run tests, safety scan, and validations.
11. Write a private public-safe run summary.

**Important:** The script should not run the optional alert pair. Keep the first live-evidence fix to the same three scenarios.

**Verification command:**

```bash
uv run --directory v1 pytest -q tests/test_three_scenario_batch_v1.py
```

Expected: pass with `--dry-run` / fake transport.

---

### Task 7: Add direct Splunk verification commands to the saved run report

**Objective:** Ensure the final summary distinguishes seeded Splunk evidence from scaffold rows.

**Files:**
- Modify or create report logic in `v1/scripts/run_three_scenario_splunk_evidence_batch_v1.py`
- Private output: `v1/reports/private/${BATCH}/run-summary-public-safe.md`

**Required report fields:**

For each scenario row:

```text
scenario_run_id | seed_ok | splunk_rows_found | agent_run_ok | capture_status | public_safe_ok | validation_status | interpretation | caveat
```

**Report language rules:**

- If Splunk rows are seeded and captured: say `live_splunk_public_redacted` or `seeded Splunk evidence captured`.
- Do not say `organic agent telemetry` unless the rows came from the runner/tooling itself rather than seeding.
- Do not say `release candidate` unless strict validation passes and Ryan approves the release framing.

---

## Live execution procedure after implementation

When the above code is implemented and tests pass, run a fresh batch manually first:

```bash
cd /home/ryan/projects/ai-tamperguard
BATCH="v1_live_smoke_$(date -u +%Y%m%dT%H%M%SZ)"
```

For each scenario, the live flow should be:

```bash
RUN_ANCHOR_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RUN_ANCHOR_EPOCH=$(date -u +%s)

uv run --directory v1 python scripts/reset_lab_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial_inventory.toml \
  --scenario <SCENARIO_ID> \
  --reset-id <RESET_ID>

uv run --directory v1 python scripts/seed_splunk_scenario_evidence_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial_inventory.toml \
  --scenario <SCENARIO_ID> \
  --scenario-run-id <SCENARIO_RUN_ID> \
  --reset-id <RESET_ID> \
  --batch-id "$BATCH" \
  --anchor-epoch "$RUN_ANCHOR_EPOCH" \
  --output-manifest "data/private/seed_manifests/${BATCH}/<SCENARIO_RUN_ID>.json"
```

Then verify with Splunk MCP using a public-safe query shape:

```text
index=openclaw_tamper_lab earliest=<RUN_ANCHOR_EPOCH> scenario_run_id="<SCENARIO_RUN_ID>"
| stats count as event_count dc(event_id) as distinct_event_ids by scenario_id scenario_run_id action_family
```

Expected rows:

- `scenario_004_run_001`: 3 events total.
- `scenario_007_run_001`: 2 events total.
- `scenario_010_run_001`: 4 events total.

Then run capture with live rows required:

```bash
uv run --directory v1 python scripts/capture_splunk_run_v1.py \
  --config splunk/private/lab.toml \
  --scenario-run-id <SCENARIO_RUN_ID> \
  --reset-id <RESET_ID> \
  --batch-id "$BATCH" \
  --earliest-epoch "$RUN_ANCHOR_EPOCH" \
  --require-live-splunk-rows \
  --output-dir "data/private/raw_exports/${BATCH}/<SCENARIO_RUN_ID>"
```

---

## Files likely to change

### Code

- `v1/src/ai_tamperguard_v1/scenario_events.py` — new shared event generation module.
- `v1/src/ai_tamperguard_v1/lab_config.py` — parse private Splunk HEC/search config.
- `v1/src/ai_tamperguard_v1/splunk_io.py` — new fakeable Splunk write/search helpers.
- `v1/scripts/seed_splunk_scenario_evidence_v1.py` — new live evidence seeding script.
- `v1/scripts/capture_splunk_run_v1.py` — prefer live Splunk rows; fail closed in live mode.
- `v1/scripts/run_three_scenario_splunk_evidence_batch_v1.py` — optional orchestration script for the exact three-scenario run.

### Tests

- `v1/tests/test_scenario_events_v1.py`
- `v1/tests/test_splunk_io_v1.py`
- `v1/tests/test_seed_splunk_scenario_evidence_v1.py`
- `v1/tests/test_capture_splunk_run_v1.py`
- `v1/tests/test_lab_config_v1.py`
- `v1/tests/test_three_scenario_batch_v1.py`

### Private / ignored runtime artifacts

- `v1/splunk/private/lab.toml` — add private HEC/search env-var references only.
- `v1/data/private/seed_manifests/${BATCH}/...`
- `v1/data/private/raw_exports/${BATCH}/...`
- `v1/data/private/run_manifests/${BATCH}/scenario_runs_private.jsonl`
- `v1/data/private/normalized/${BATCH}/events_private.jsonl`
- `v1/reports/private/${BATCH}/...`

### Public-safe generated sample artifacts

- `v1/data/public_sample/dataset_manifest.json`
- `v1/data/public_sample/normalized/events.jsonl`
- `v1/data/public_sample/scenarios/scenario_runs.jsonl`
- `v1/data/public_sample/scenarios/answer_key_public_redacted.jsonl`
- `v1/data/public_sample/scenarios/reset_manifest_public_redacted.jsonl`
- `v1/data/public_sample/derived/*`
- `v1/data/public_sample/splits/*`

---

## Tests / validation

Run these before any live Splunk write:

```bash
cd /home/ryan/projects/ai-tamperguard
uv run --directory v1 pytest -q
uv run --directory v1 python scripts/public_safety_scan_v1.py data/public_sample docs schemas scenarios
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all \
  --allow-fixture-only
```

After live seeding/capture:

```bash
uv run --directory v1 pytest -q
uv run --directory v1 python scripts/public_safety_scan_v1.py data/public_sample docs schemas scenarios
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all \
  --allow-fixture-only
```

Run the strict gate and interpret honestly:

```bash
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all
```

Expected for this slice: it may still fail if `release_status` remains `live_lab_capture_scaffold_not_release_candidate` or equivalent non-release wording. That is acceptable until Ryan reviews the evidence and approves release-candidate framing.

## Stop conditions

Stop and report if any of these happen:

- HEC/search config requires raw token values in TOML instead of env-var references.
- Any script wants to write outside `openclaw_tamper_lab`.
- Any script wants to delete/clear Splunk indexes.
- Seeded event payloads include private names, raw hostnames, usernames, URLs, tokens, or raw SPL.
- Splunk MCP cannot find seeded rows for a scenario after HEC success.
- Capture with `--require-live-splunk-rows` falls back to scaffold instead of failing closed.
- Public safety scan finds a secret/private identifier.
- Normalized events cannot link to private run manifest rows.
- Protected evidence contradicts the run interpretation.

## Risks, tradeoffs, and resolved defaults

### Risk: seeded evidence is not organic agent telemetry

This plan creates actual Splunk-indexed rows, but they are **seeded synthetic control-plane evidence**, not naturally emitted agent tool telemetry. Report this as `seeded Splunk evidence captured`, not `organic runner telemetry captured`.

### Resolved default: Splunk write/search credential shape

Resolved default: use HEC for writes with `AI_TAMPERGUARD_SPLUNK_HEC_TOKEN` from `.env` / environment. Do not require raw token values in TOML. If script-level search needs separate auth, add it later as `AI_TAMPERGUARD_SPLUNK_SEARCH_TOKEN` or another env-var reference only; otherwise use Splunk MCP/Hermes verification for readback.

### Risk: Splunk indexing delay

After HEC success, Splunk may take a short time to make rows searchable. The live runner should retry verification with bounded backoff rather than blind sleeping forever. Suggested bound: 6 attempts over 30 seconds.

### Tradeoff: keeping scaffold fallback

Keep scaffold fallback for tests/offline fixtures, but make live runs opt into `--require-live-splunk-rows`. This preserves current dev ergonomics while preventing another false-green live smoke.

### Resolved default: release-status promotion


Do not promote `release_status` to release-candidate in this implementation. Even if seeded Splunk rows are captured, Ryan should review the summary first because this is still seeded synthetic data, not full corpus collection.

## Final expected result

After implementation and a new three-scenario live run, the concise summary should be able to say:

```text
All three selected scenario runs seeded public-safe synthetic evidence into the sacrificial Splunk index, Splunk MCP verified scenario-run rows after the run anchors, capture read those Splunk-indexed rows, public-safe normalization/derivation passed, and strict release status remains conservative pending review.
```

If any scenario has zero Splunk rows, the batch should fail closed before normalization. No more empty lobster pot pretending it caught dinner.
