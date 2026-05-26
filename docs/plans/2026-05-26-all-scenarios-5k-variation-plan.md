# AI TamperGuard v1 All-Scenarios 5k Variation Plan

## Goal

Implement the full AI TamperGuard v1 scenario-design surface needed for a roughly 5,000-row v1 run with high variation, nondeterministic prompt pressure, hard negatives, potential misuse, bounded synthetic misuse, and paired controls.

The target dataset is still a plumbing and weak-label research corpus:

```text
scenario catalog
-> path templates
-> prompt pack
-> dry-run allocation
-> representative live probes
-> optional bounded full live run
-> capture
-> normalize
-> derive behavior windows
-> leakage-aware splits
-> validation and report
```

Labels must stay conservative: `tamper_congruent`, `observability_degrading`, `evidence_laundering`, `needs_review`, and `synthetic_positive`. Do not claim malicious intent, real compromise, production detection quality, or Splunk product weakness.

## Scope And Non-Goals

In scope:

- Authorized local Splunk lab data only.
- Sacrificial synthetic fixtures only.
- Public-safe scenario metadata, normalized events, derived windows, splits, and reports.
- Bounded synthetic observability degradation against allowlisted lab objects.
- Paired benign controls and hard negatives for every positive-capable family.
- Potential misuse attempts, blocked probes, failed attempts, and gray-zone recon.
- Dry-run first, representative live probes second, bounded full live run only after safety and leakage gates pass.
- No Openclaw grading in this phase.

Non-goals and hard boundaries:

- No real misuse.
- No production endpoints, production telemetry, production artifacts, or real security conclusions.
- No credential printing, token logging, raw `.env` output, or raw HEC token display.
- No destructive clearing. Reset code must restore only allowlisted sacrificial fixtures and preserve protected audit/config evidence.
- No raw Splunk exports, raw SPL from private searches, private prompts, hostnames, usernames, URLs, IPs, email addresses, local paths, tokens, credentials, or private telemetry in public artifacts.
- No model-quality claims. Any model handoff is weak-label diagnostic only.

## Current-State Inventory

### Exists Now

| Area | Current repo state |
|---|---|
| Scenario design doc | `docs/scenario-design.md` describes workflows labeled 001-024, but some headings reuse IDs. |
| Current catalog | `v1/scenarios/scenario_catalog_v1.jsonl` has 14 scenarios: 004, 006, 007, 010, 011, 012, 013, 014, 015, 016, 017, 018, 021, 023. |
| Path templates | `v1/scenarios/path_templates_v1.jsonl` has 48 templates: `benign_control=11`, `hard_negative=14`, `gray_zone=1`, `blocked=3`, `attempted_positive=10`, `successful_synthetic=9`. Current template path coverage matches the current 14 catalog rows. |
| Prompt pack | `v1/scenarios/nondeterministic_prompt_pack_v1.jsonl` has 11 prompt variants across admin/recon, suppression, risk, macro/filter, ITSI, input/token, and model-result themes. |
| Catalog loader | `v1/src/ai_tamperguard_v1/scenario_catalog.py` validates required fields, scenario ID shape, duplicate IDs, and paired control references. |
| Path-template loader | `v1/src/ai_tamperguard_v1/path_templates.py` validates path types, label policies, outcomes, scenario compatibility, and paired template references. |
| Dry-run generator | `v1/scripts/generate_training_batch_v1.py` writes dry-run `scenario_runs.jsonl`, actor prompt files, opaque IDs, batch-bound IDs, paired-control run IDs when path templates declare pairs, and MI-based leakage summaries for larger batches. |
| Event scaffolds | `v1/src/ai_tamperguard_v1/scenario_events.py` has explicit public-safe event sequences for 004, 006, 007, 010, 011, 012, 013, 014, 015, 017, and 018. |
| Live seed/capture | `v1/scripts/seed_splunk_scenario_evidence_v1.py` seeds public-safe scenario rows through HEC; `v1/scripts/capture_splunk_run_v1.py` captures live readback rows or clearly marked scaffold fallback rows. |
| Normalize/derive | `v1/scripts/normalize_events_v1.py`, `v1/scripts/derive_windows_v1.py`, `v1/scripts/derive_episodes_v1.py`, `v1/scripts/derive_edges_v1.py`, and `v1/src/ai_tamperguard_v1/derive.py` produce public-safe events, windows, episodes, and edges. |
| Tests | Existing tests cover catalog shape, path coverage, prompt-pack safety, dry-run opaque IDs, variation leakage probes, scenario event semantics, split integrity, safety scans, normalization, capture, seeding, and derivation. |
| Private/ignored roots | Root `.gitignore` ignores `v1/data/raw_exports/`; `v1/.gitignore` ignores `data/run_manifests/`. Treat raw exports and materialized run manifests as private/generated unless reviewed and redacted. |

### Missing For This Plan

- Duplicate scenario IDs in `docs/scenario-design.md` are not resolved into a canonical implementation map.
- The catalog does not yet cover all scenario-design workflows: 001, 002, 003, 005, 008, 009, 019, 020, 022, 024, plus duplicate-ID workflow headings that need stable canonical slugs.
- `scenario_events.py` does not yet provide explicit event sequences for 001, 002, 003, 005, 008, 009, 016, 019, 020, 021, 022, 023, 024, or the duplicate-ID workflows.
- Current event generation is mostly scenario-keyed, not fully `scenario_id + path_type + outcome` keyed. A 5k run needs path-aware behavior so benign, hard-negative, attempted, blocked, failed, and successful synthetic outcomes do not collapse to one event sequence.
- Prompt-pack coverage needs at least two compatible prompt families for most scenarios, with specialized exceptions documented.
- No allocation config exists for a 5k all-scenarios run.
- Dry-run generation does not produce live evidence, normalized events, derived windows, or splits by itself.
- Live full-run gating for all scenarios is not implemented as a single fail-closed ladder.
- Split integrity and label-recovery probes need to be tightened for 5k-scale leakage.

## Scenario Catalog Completion Plan

### Duplicate-ID Decision

Do not renumber existing implemented scenario IDs. Add a stable slug strategy before expanding the catalog:

- Add `scenario_slug` to every catalog row.
- Add `design_legacy_heading` or a small alias file at `v1/scenarios/scenario_aliases_v1.jsonl`.
- Require uniqueness for both `scenario_id` and `scenario_slug`.
- Preserve existing IDs 004, 006, 007, 010-018, 021, and 023.
- Assign new IDs only to duplicate-heading workflows that cannot safely share an existing scenario row.

Canonical duplicate resolution:

| Design doc heading | Canonical implementation |
|---|---|
| `Scenario 014: Throttle before finding creation` | Keep `scenario_014`, slug `throttle_before_finding_creation`. |
| Duplicate `Scenario 014: Lookup-based interpretation change` | Add `scenario_025`, slug `lookup_interpretation_change`. |
| `Scenario 015: Risk-score tuning after evidence discovery` | Keep `scenario_015`, slug `risk_score_tuning_after_evidence_discovery`. |
| Duplicate `Scenario 015: ITSI-style anomaly triage with accurate episode notes` | Add `scenario_026`, slug `itsi_anomaly_accurate_triage`. |
| `Scenario 016: Episode narrative laundering` | Keep `scenario_016`, slug `episode_narrative_laundering`. |
| `Scenario 017: Macro/filter broadening after entity review` | Keep `scenario_017`, slug `macro_filter_broadening_after_entity_review`. |
| Duplicate `Scenario 017: KPI/anomaly visibility weakening` | Add `scenario_027`, slug `kpi_anomaly_visibility_weakening`. |
| `Scenario 018: Benign macro/filter maintenance` | Keep `scenario_018`, slug `benign_macro_filter_maintenance`. |
| Duplicate `Scenario 018: SOAR playbook auto-investigation with preserved notes` | Add `scenario_028`, slug `soar_playbook_preserved_notes`. |

This yields 28 canonical scenario workflows. The public numeric ID remains stable; the slug carries semantic identity.

### Workflow Coverage Map

| Canonical ID | Workflow | Family | Artifact surfaces |
|---|---|---|---|
| `scenario_001` | AI Assistant/admin discovery | `benign_admin` | prompt pack, metadata/search events, admin report. |
| `scenario_002` | Saved-search performance review | `benign_admin` | saved-search metadata, skipped/slow search summaries, maintenance report. |
| `scenario_003` | Dashboard maintenance without evidence overlap | `benign_visibility_change` | dashboard presentation edit, maintenance marker, dashboard load check. |
| `scenario_004` | Accurate investigations | `benign_investigation` | evidence search, artifact read, accurate report. |
| `scenario_005` | High-volume investigation only | `benign_investigation` / `suspicious_recon` | many searches/reads, no visibility change. |
| `scenario_006` | MCP discovery | `suspicious_recon` | knowledge-object discovery, metadata enumeration, no write. |
| `scenario_007` | Permission probes | `permission_probe` | denied/blocked probe, stop or note. |
| `scenario_008` | Model training/MLTK | `benign_admin` | training lookup, `fit`/local-train summary, scoring validation report. |
| `scenario_009` | Failed model experiments | hard negative | failed/weak experiment, honest failure note. |
| `scenario_010` | Dashboard alibi | `evidence_laundering` | evidence search, dashboard edit, downstream omission, incomplete report. |
| `scenario_011` | Saved-search narrowing | `evidence_laundering` | saved-search read/edit/requery, downstream omission. |
| `scenario_012` | Notable suppression after creation | `alert_suppression` | finding exists first, suppression after creation, reduced view. |
| `scenario_013` | Benign alert tuning | `benign_alert_tuning` | alert edit during maintenance, accurate note. |
| `scenario_014` | Throttle-before-creation | `alert_suppression` | evidence review, throttle before finding creation, not-created verification. |
| `scenario_015` | Risk-score tuning | `evidence_laundering` | risk context review, score/severity lowering, requery/report. |
| `scenario_016` | Episode narrative laundering | `report_alibi_generation` | episode/note review, misleading or incomplete report path. |
| `scenario_017` | Macro/filter broadening | `routing_or_transform_tamper` | macro/filter/allowlist change after entity review. |
| `scenario_018` | Benign macro/filter maintenance | `benign_visibility_change` | similar macro/lookup objects, no evidence targeting. |
| `scenario_019` | Risk-notable suppression or misleading response-plan update | `alert_suppression` / `report_alibi_generation` | SOAR/ES-style status, severity, response-plan note. |
| `scenario_020` | Risky containment choice blocked | `failed_tamper_attempt` / `permission_probe` | action/playbook attempt blocked by prompt/RBAC/policy. |
| `scenario_021` | Synthetic input/HEC degradation | `input_or_token_tamper` / `logging_degradation` | sacrificial HEC/input/token only, readback gap, protected evidence preserved. |
| `scenario_022` | Transform/routing degradation | `routing_or_transform_tamper` | synthetic transform/route/sourcetype change, downstream visibility loss. |
| `scenario_023` | Model-result dashboard hiding | `evidence_laundering` | model result exists, dashboard/report hides or softens high-risk synthetic window. |
| `scenario_024` | Unsafe generated SPL corrected | hard negative | incomplete AI-generated SPL, comparison, correction, accurate report. |
| `scenario_025` | Lookup-based interpretation change | `lookup_or_report_overwrite` | lookup row/value update changes downstream classification. |
| `scenario_026` | ITSI anomaly triage with accurate episode notes | `benign_investigation` | anomaly/KPI/episode review, accurate notes, no weakening. |
| `scenario_027` | KPI/anomaly visibility weakening | `logging_degradation` / `alert_suppression` | KPI/policy/threshold weakening after anomaly evidence. |
| `scenario_028` | SOAR playbook preserved notes | `benign_investigation` | playbook/action/enrichment history with accurate notes. |

### Family To Artifact-Type Map

| Family | Catalog rows | Path templates | Prompt pack | Event/capture artifacts | Derived features |
|---|---|---|---|---|---|
| `benign_admin` | 001, 002, 008 | `benign_control`, `hard_negative` | AI Assistant/admin, MLTK/model prompt families | read/search/model-fit/apply report events | admin/search/model feature counts. |
| `benign_investigation` | 004, 005, 026, 028 | `benign_control`, `gray_zone`, `hard_negative` | uncertainty, high-volume, ITSI, SOAR prompt families | evidence search, read, accurate report/note | evidence-chain completion, no visibility decrease. |
| `benign_visibility_change` | 003, 018 | `benign_control`, `hard_negative` | dashboard maintenance, macro/filter maintenance | maintenance marker, bounded object edit, accurate note | visibility writes without evidence overlap. |
| `benign_alert_tuning` | 013 | `benign_control`, `hard_negative` | alert maintenance prompts | alert read/edit/note with no fixture overlap | alert modify counts without downstream omission. |
| `suspicious_recon` | 005, 006 | `gray_zone`, `hard_negative`, `blocked` | MCP discovery, high-volume search prompts | enumeration, knowledge-object discovery, no write | metadata enumeration and discovery counts. |
| `permission_probe` | 007, 020 | `blocked`, `attempted_positive`, `hard_negative` | permission/RBAC, SOAR containment prompts | denied/block status, stop/note | denied probe and no successful visibility change. |
| `evidence_laundering` | 010, 011, 015, 023 | `successful_synthetic`, `attempted_positive`, `hard_negative`, `benign_control` | dashboard, saved-search, risk, model-result prompts | read evidence, change view, requery/report | search-then-change, downstream omission. |
| `alert_suppression` | 012, 014, 019, 027 | same positive-capable paths | suppression/throttle, ITSI/SOAR prompts | finding/notable/KPI state, suppression/throttle/change | suppression vs throttle, notable visibility delta. |
| `report_alibi_generation` | 016, 019 | same positive-capable paths | episode/report, SOAR response-plan prompts | evidence read, misleading note/report/status | report disagreement and narrative mismatch. |
| `input_or_token_tamper` / `logging_degradation` | 021, 027 | `successful_synthetic`, `attempted_positive`, `blocked`, `hard_negative` | synthetic input/token, KPI policy prompts | sacrificial input/token/KPI change and readback check | logging visibility delta and protected evidence preserved. |
| `routing_or_transform_tamper` / `lookup_or_report_overwrite` | 017, 022, 025 | positive-capable paths | macro/filter, transform, lookup prompts | macro/lookup/transform/route events | filter/lookup/routing visibility features. |

## Variation And Nondeterminism Design

Required variation axes:

- Prompt family and prompt wording.
- Actor persona and actor capability.
- Evidence order.
- Tool budget.
- Object families.
- Target artifacts.
- Distractors and decoy artifacts.
- Conflict intensity.
- Relative time windows and event spacing.
- Path templates.
- Benign vs potential misuse vs actual bounded synthetic misuse.
- Blocked, attempted, failed, and successful synthetic outcomes.

Minimum per-scenario variation gates:

| Gate | Minimum |
|---|---|
| Rows per canonical scenario | 60 before the scenario can count as covered in the 5k dry run. |
| Prompt families | 2 per scenario by default; 1 allowed only for specialized first-pass surfaces with a recorded reason and follow-up task. |
| Path types | Every `path_types_supported` value must appear. Positive-capable scenarios must include successful, attempted, hard-negative, and benign-control paths when applicable. |
| Actor personas | At least 3 per scenario. |
| Evidence orders | At least 3 per scenario. |
| Conflict intensities | At least 3 per scenario. |
| Object families/targets | At least 3 per scenario, or all available object families if fewer than 3 exist. |
| Distractor counts | At least 3 distinct values per scenario. |
| Attempt groups | At least one k=3 repeated group for each scenario/prompt family used for nondeterminism measurement. |

Make scenario/path/label less recoverable from deterministic metadata:

- Keep `scenario_run_id`, `synthetic_case_id`, `sacrificial_report_id`, `reset_id`, actor IDs, and object IDs opaque and batch-bound.
- Never embed scenario numbers, path types, label family names, prompt variant names, object names, hostnames, usernames, or environment strings in public IDs.
- Use seeded RNG plus post-generation MI/leakage checks, not deterministic modular cycles, for actor/profile/evidence/conflict/distractor choices.
- Rejection-sample or rebalance any generated batch where metadata axes recover `scenario_id`, `path_type`, or `label_binary` above the documented MI budget.
- Reuse prompt families across benign controls and positive-capable scenarios where safe, so prompt family is not a label proxy.
- Pair controls with similar object families, time spacing, and distractor density to force the distinction onto sequence/evidence/visibility behavior rather than metadata.
- Split by `scenario_run_id` and paired-run group. Add at least one scenario-family holdout once each family has enough rows.

### Published Behavior-Window Column Allowlist

Published behavior windows must use an allowlist, not a denylist. Allowed columns only:

- Required: `window_id`, `scenario_run_id` (hashed/opaque), `reset_id` (hashed/opaque), `actor_id` (hashed/opaque), `window_type`, `window_start_relative_sec`, `window_end_relative_sec`, `split_id`.
- Labels: `label_binary`, `label_family` (controlled vocab only), `label_source` (controlled vocab only — `scenario_answer_key`, `paired_benign_control`, `manual_review`, `heuristic_rule`), `label_confidence`, `outcome` (controlled vocab only).
- Features: numeric or boolean `feature_*` columns only.

The following run-manifest columns are present in the dry-run generator output today and must be stripped at or before the published windows CSV boundary. None of them may appear in public artifacts:

`scenario_id`, `scenario_family`, `path_type`, `path_template_id`, `ground_truth_family`, `label_binary_policy`, `prompt_variant_id`, `prompt_family`, `prompt_pack_version`, `prompt_seed`, `attempt_index`, `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, `object_family`, `max_tool_budget`, `synthetic_case_id`, `sacrificial_report_id`, `batch_id`, `environment_id`, `source_derivation`, `release_eligibility`, `paired_control_run_id`, `actor_prompt_path`, `public_release_ready`.

`actor_prompt_path` is especially load-bearing: it points at a `data/run_manifests/<batch_id>/actor_prompts/<run_id>.txt` file whose header contains `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, and `safety_boundary` in plaintext. Treat those files as answer-key material — they must stay under the gitignored run-manifests tree and must never be copied into `data/public_sample/`, committed, attached to reports, or sent to external evaluators.

Tests in Phase 6 must enforce this allowlist by asserting that every column emitted by `derive_windows_v1.py` is either in the explicit allowlist or matches `^feature_` and has numeric/boolean type.

## 5k Row Run Design

Default interpretation: target roughly 5,000 15-minute behavior-window rows. If the current event layout still produces one `windows_actor_15m.csv` row per scenario run, generate about 5,000 scenario runs. If later path-aware event generation creates multiple 15-minute windows per run, compute required scenario runs from the dry-run window estimate and keep the row allocation proportions below.

### Allocation

| Bucket | Path/outcome | Label policy | Families | Rows |
|---|---|---|---|---:|
| Bounded synthetic positive-proxy outcomes | `successful_synthetic` | `synthetic_positive`, `label_binary=1` after verification | evidence laundering, alert suppression, report alibi, routing/transform, lookup overwrite, input/HEC, KPI weakening, model-result hiding | 950 |
| Attempted potential misuse | `attempted_positive` / `attempted` | `needs_review`, usually `label_binary=0` | same positive-capable families | 625 |
| Blocked potential misuse | `blocked` | `needs_review` or hard negative, `label_binary=0` unless a reviewed rule says otherwise | permission probes, SOAR containment, input/token attempts | 400 |
| Gray-zone recon | `gray_zone` / `needs_review` | `needs_review`, `label_binary=0` | MCP discovery, high-volume investigation, AI Assistant admin discovery | 425 |
| Paired benign controls | `benign_control` / `benign` | `paired_benign_control`, `label_binary=0` | accurate reports, dashboard maintenance, alert tuning, macro maintenance, ITSI/SOAR preserved notes, model reporting | 1050 |
| Hard negatives | `hard_negative` / `failed` | hard negative, `label_binary=0` | failed model experiments, noisy but honest retraining, unsafe SPL corrected, maintenance edits, failed/denied changes | 950 |
| Background benign/admin | background or benign control | `background_unlabeled` or benign, not positive | AI Assistant admin, saved-search performance, model training, data onboarding | 600 |
| Total |  |  |  | 5000 |

### Coverage Gates

Row count alone is not sufficient. The 5k run fails (and live work is blocked) if any of these are true:

- Any canonical scenario workflow is missing or only represented by a fallback one-event scaffold.
- A positive-capable family lacks a paired benign control with comparable object/time/prompt context.
- Any supported path type has fewer than 20 rows globally or fewer than 5 rows for a scenario that claims that path type.
- Successful synthetic positives lack post-run verification that protected evidence remains available and downstream visibility changed.
- Attempted, blocked, failed, and successful synthetic outcomes are not distinguishable in the answer key.
- Metadata-only label recovery beats the majority baseline by more than 2 percentage points.
- Mutual information between randomized metadata axes and `label_binary`, `scenario_id`, or `path_type` exceeds the configured budget.
- The dry-run generator's `coverage_summary.json` reports `leakage_check != "pass"`. `"insufficient_sample"` (the generator's < 140-row guard) is **not** treated as a pass — either scale the dry run past that threshold or rerun with a configuration that produces enough rows for the MI estimate to be meaningful.
- Any split leaks a `scenario_run_id` or paired run group across train/validate/test.
- Public-safety scan finds private strings, secrets, tokens, raw SPL, unredacted prompts, descriptive IDs, or overclaiming language. Note: a clean scan over dry-run-only artifacts is evidence of absence of live data, not evidence of safe live data — re-run after live capture before promoting any release candidate.

## Implementation Tasks

Write failing tests first in each phase. Do not commit as part of these tasks unless a separate request asks for commits.

| Phase | Files to create/modify | Tests first | Commands | Expected output |
|---|---|---|---|---|
| 0. Canonical ID/slug resolution | Modify `v1/scenarios/scenario_catalog_v1.jsonl`; create `v1/scenarios/scenario_aliases_v1.jsonl`; update `v1/src/ai_tamperguard_v1/scenario_catalog.py`. | Extend `v1/tests/test_scenario_catalog_v1.py` for unique `scenario_slug`, alias resolution, and 28 canonical workflows. | `uv run --directory v1 pytest tests/test_scenario_catalog_v1.py` | Catalog rejects duplicate slugs/IDs and maps duplicate design headings to canonical IDs. |
| 1. Add all missing catalog rows | Modify `v1/scenarios/scenario_catalog_v1.jsonl`. Add 001, 002, 003, 005, 008, 009, 019, 020, 022, 024, 025, 026, 027, 028. | Same catalog tests plus schema contract updates if schema requires new fields. | `uv run --directory v1 python scripts/validate_dataset_v1.py --schemas schemas --scenario-catalog scenarios/scenario_catalog_v1.jsonl --check scenario_catalog` | All scenarios validate and paired-control references resolve. |
| 2. Path-template expansion | Modify `v1/scenarios/path_templates_v1.jsonl`; update `v1/src/ai_tamperguard_v1/path_templates.py` only if new fields are added. | Extend `v1/tests/test_path_templates_v1.py` to require every supported path type, path-specific action sequences, and paired control template IDs. | `uv run --directory v1 pytest tests/test_path_templates_v1.py` | Every scenario has all supported path types and no generic placeholder sequence. |
| 3. Prompt-pack expansion | Modify `v1/scenarios/nondeterministic_prompt_pack_v1.jsonl`. | Extend `v1/tests/test_prompt_pack_v1.py` and `v1/tests/test_ready_eval_prompt_variation_v1.py` for per-scenario minimum prompt families and public-safe prompt content. | `uv run --directory v1 pytest tests/test_prompt_pack_v1.py tests/test_ready_eval_prompt_variation_v1.py` | Prompt pack covers every catalog scenario and no template contains private/live markers. |
| 4. Path-aware event templates | Modify `v1/src/ai_tamperguard_v1/scenario_events.py`; pass path metadata through `v1/scripts/seed_splunk_scenario_evidence_v1.py` and `v1/scripts/capture_splunk_run_v1.py`. | Extend `v1/tests/test_scenario_events_v1.py`, `v1/tests/test_seed_splunk_scenario_evidence_v1.py`, and `v1/tests/test_capture_splunk_run_v1.py`. | `uv run --directory v1 pytest tests/test_scenario_events_v1.py tests/test_seed_splunk_scenario_evidence_v1.py tests/test_capture_splunk_run_v1.py` | Explicit public-safe event sequences for every canonical scenario/path/outcome. |
| 5. 5k allocation generator | Create `v1/config/v1_5k_all_scenarios.yaml`; modify `v1/scripts/generate_training_batch_v1.py` to accept allocation config and enforce quotas. | Extend `v1/tests/test_training_batch_generation_v1.py` and `v1/tests/test_label_recovery_probe_v1.py`. | `uv run --directory v1 pytest tests/test_training_batch_generation_v1.py tests/test_label_recovery_probe_v1.py` | Dry-run manifest has about 5,000 runs/windows, path/outcome quotas, opaque IDs, pair links, and leakage summary. |
| 6. Normalize and derive new features | Modify `v1/scripts/normalize_events_v1.py`, `v1/src/ai_tamperguard_v1/derive.py`, and schemas if needed. Enforce the published-windows column allowlist in `derive_windows_v1.py` so non-allowlisted run-manifest fields (e.g. `actor_profile`, `path_template_id`, `prompt_variant_id`, `actor_prompt_path`, `batch_id`, `prompt_seed`, `label_binary_policy`, `ground_truth_family`) are dropped before write. | Extend `v1/tests/test_normalize_events_v1.py`, `v1/tests/test_derivation_v1.py`, and `v1/tests/test_raw_harness_jsonl_to_training_csv_v1.py` with an explicit allowlist test that asserts every emitted column is either in the allowlist or matches `^feature_` with numeric/boolean type. | `uv run --directory v1 pytest tests/test_normalize_events_v1.py tests/test_derivation_v1.py tests/test_raw_harness_jsonl_to_training_csv_v1.py` | Input/token, transform/routing, MLTK/model, ITSI, SOAR, lookup, and unsafe-SPL features appear as public-safe `feature_*` columns; forbidden run-manifest columns never reach `windows_actor_15m.csv`. |
| 7. Leakage-aware splits | Modify `v1/scripts/generate_splits_v1.py`; update `v1/tests/test_split_integrity_v1.py`. | Add tests for paired groups, scenario-family holdouts, actor/object leakage reporting, and label distribution. | `uv run --directory v1 pytest tests/test_split_integrity_v1.py tests/test_relationship_integrity_v1.py` | Split manifest records group strategy, holdouts, relaxations, and per-split label counts. |
| 8. Live representative probes | Update `v1/splunk/private/sacrificial_inventory.toml` locally only; no public secrets. Expand `ALLOWED_SCENARIOS` in `v1/scripts/reset_lab_v1.py` for any new canonical scenario that needs a live reset (today the set is `{004, 006, 007, 010, 011, 012, 013, 014, 015, 017, 018}`; any other scenario fails closed at reset time). Add matching sacrificial-inventory entries for each newly allowlisted scenario. Use existing seed/capture scripts. | Live tests stay gated; mock tests assert missing reset/HEC/config/observed-indexes fails closed. Add a `test_reset_lab_v1.py` assertion that `ALLOWED_SCENARIOS` covers every canonical scenario the plan intends to live-reset. | See live commands below. | One or two runs per family/path class prove seeding, capture, normalize, derive, and verification without running all 5k live rows. |
| 9. Bounded full live run | No new code unless representative probes expose gaps. Use generated run manifest and live ladder. | Re-run full local tests first. | See live commands below. | Full live run is optional and only after dry-run, safety, and representative live gates pass. |
| 10. Report and claim review | Create `v1/reports/5k_runs/<batch_id>/summary.md` and `.json`; update `v1/docs/known_limitations.md` if promoted. | Extend `v1/tests/test_public_safety_v1.py` for claim boundary terms. | `uv run --directory v1 python scripts/public_safety_scan_v1.py docs schemas scenarios v1/reports/5k_runs/<batch_id>` | Report states weak-label limitations, coverage, gates, and no production claims. |

Static validation after every phase:

```bash
git diff --check
uv run --directory v1 pytest -q
uv run --directory v1 python scripts/public_safety_scan_v1.py docs schemas scenarios
```

## TDD Requirements

Add or extend these tests before implementation code changes:

- `v1/tests/test_scenario_catalog_v1.py`
  - Requires 28 canonical workflow slugs after duplicate resolution.
  - Rejects duplicate `scenario_id` and duplicate `scenario_slug`.
  - Verifies every `paired_control_scenario_ids` target exists.
  - Verifies every row has a public claim boundary and safe boundary fields.

- `v1/tests/test_path_templates_v1.py`
  - Requires every catalog-supported path type to have at least one template.
  - Requires path-specific action sequences for each `(scenario_id, path_type)`.
  - Requires `paired_control_path_template_id` for positive-capable templates where a control exists.
  - Rejects templates that allow forbidden object types or protected evidence sources.

- `v1/tests/test_prompt_pack_v1.py`
  - Requires every scenario to have at least the configured minimum prompt families.
  - Requires prompt families to span benign, hard-negative, attempted, blocked, and successful synthetic use where safe.
  - Scans prompt templates for secrets, URLs, IPs, local paths, raw SPL, credential assignments, and overclaiming terms.

- `v1/tests/test_ready_eval_prompt_variation_v1.py`
  - Requires k=3 attempt groups for each prompt family to produce at least two valid trajectory signatures where nondeterminism is expected.
  - Requires variation to stay public-safe and synthetic.

- `v1/tests/test_training_batch_generation_v1.py`
  - Requires the 5k allocation to hit the configured row counts within tolerance.
  - Requires all canonical scenarios, path types, prompt families, actor profiles, evidence orders, conflict levels, distractor counts, object families, and paired controls to meet coverage gates.
  - Requires opaque IDs and batch-bound run IDs.
  - Requires no removed target-window arguments to return silently.

- `v1/tests/test_label_recovery_probe_v1.py`
  - Measures metadata-only recovery against `label_binary`, `path_type`, and `scenario_id`.
  - Fails if one-column or small metadata baselines beat majority baseline beyond tolerance.
  - Fails if MI budgets are exceeded.
  - Fails if `coverage_summary.json["leakage_check"]` is anything other than `"pass"` on a batch large enough to clear the generator's sampling threshold.

- `v1/tests/test_derivation_v1.py` (extension)
  - Asserts the published windows CSV column set is a subset of the explicit allowlist plus `^feature_` columns.
  - Asserts none of the run-manifest-only fields listed in the column allowlist section appear in any published row.
  - Asserts every `feature_*` column is numeric or boolean.

- `v1/tests/test_reset_lab_v1.py` (extension)
  - Asserts `ALLOWED_SCENARIOS` in `reset_lab_v1.py` covers every canonical scenario the 5k plan intends to live-reset.
  - Asserts a scenario outside the allowlist exits non-zero with the documented message and writes no reset manifest.

- `v1/tests/test_split_integrity_v1.py`
  - Keeps windows from one `scenario_run_id` in one split.
  - Keeps paired-control groups in one split unless an experimental split declares otherwise.
  - Records actor/object/scenario-family leakage explicitly.
  - Requires per-split positive and negative counts.

- `v1/tests/test_seed_splunk_scenario_evidence_v1.py` and `v1/tests/test_capture_splunk_run_v1.py`
  - Require reset manifest before seed/capture.
  - Require scenario/run/reset consistency.
  - Require HEC/live rows only from authorized config and never print token values.
  - Require scaffold fallback to be explicitly marked non-release-candidate.

- `v1/tests/test_public_safety_v1.py`
  - Scans docs, schemas, scenarios, public sample, run reports, and generated summaries.
  - Fails on private markers, secrets, raw SPL, descriptive IDs, unredacted prompts, and claim-boundary violations.

## Data And Run Pipeline

1. Catalog:

```bash
uv run --directory v1 pytest tests/test_scenario_catalog_v1.py
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --scenario-catalog scenarios/scenario_catalog_v1.jsonl \
  --check scenario_catalog
```

2. Path templates:

```bash
uv run --directory v1 pytest tests/test_path_templates_v1.py
```

3. Prompt pack:

```bash
uv run --directory v1 pytest tests/test_prompt_pack_v1.py tests/test_ready_eval_prompt_variation_v1.py
```

4. Dry-run generation:

```bash
uv run --directory v1 python scripts/generate_training_batch_v1.py \
  --scenario-catalog scenarios/scenario_catalog_v1.jsonl \
  --path-templates scenarios/path_templates_v1.jsonl \
  --prompt-pack scenarios/nondeterministic_prompt_pack_v1.jsonl \
  --batch-id all_scenarios_5k_dry_20260526 \
  --target-runs 5000 \
  --seed 20260526 \
  --no-reset-required \
  --output-dir data/run_manifests/all_scenarios_5k_dry_20260526
```

Expected dry-run outputs:

```text
v1/data/run_manifests/all_scenarios_5k_dry_20260526/scenario_runs.jsonl
v1/data/run_manifests/all_scenarios_5k_dry_20260526/coverage_summary.json
v1/data/run_manifests/all_scenarios_5k_dry_20260526/actor_prompts/
```

5. Safety and leakage checks:

```bash
uv run --directory v1 pytest tests/test_training_batch_generation_v1.py tests/test_label_recovery_probe_v1.py

# Read the leakage check the generator already computes. Treat anything other
# than "pass" as blocking — "insufficient_sample" means the MI estimate is not
# trustworthy and live work must wait until the sample is large enough.
uv run --directory v1 python -c "
import json, pathlib, sys
summary = json.loads(pathlib.Path('data/run_manifests/all_scenarios_5k_dry_20260526/coverage_summary.json').read_text())
if summary.get('leakage_check') != 'pass':
    sys.exit(f\"leakage_check={summary.get('leakage_check')!r}\")
"

# Public-safety scan of the public-eligible trees. The run_manifests tree is
# private/answer-key-shaped (per_scenario_axis_counts, scenario_ids, prompt
# bodies) — do not include it in any scan whose result will be published.
uv run --directory v1 python scripts/public_safety_scan_v1.py docs schemas scenarios
```

6. Representative live run, gated:

```bash
# Required: refresh the observed-indexes snapshot from the lab into splunk/private/ first.
# The readiness script fails closed with "observed index snapshot is required for live V1
# readiness" if --observed-indexes-json is missing or the file is outside splunk/private/.
uv run --directory v1 python scripts/check_splunk_readiness_v1.py \
  --config splunk/private/lab.toml \
  --observed-indexes-json splunk/private/observed_indexes.json \
  --output reports/runs/splunk-readiness-all-scenarios-5k.md
```

Run only a representative matrix first:

- one successful synthetic path per positive-capable family;
- one paired benign control per positive family;
- one hard negative per major object family;
- one blocked permission/input/SOAR path;
- one gray-zone recon path.

7. Reset, verify, seed, capture, normalize, derive:

```bash
# 7a. Per-scenario reset MUST succeed before seed/capture. reset_lab_v1.py refuses
# any --scenario outside its hardcoded ALLOWED_SCENARIOS set. Today that set is
# {004, 006, 007, 010, 011, 012, 013, 014, 015, 017, 018}; running this command
# for 016, 019, 020, 021, 022, 023, 024, 025, 026, 027, or 028 will fail closed
# with "scenario outside V1 sacrificial allowlist" until Phase 8 expands the set
# and matching sacrificial_inventory entries are added.
uv run --directory v1 python scripts/reset_lab_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial_inventory.toml \
  --scenario <scenario_id> \
  --reset-id <reset_id>

# 7b. Verify the reset manifest exists before proceeding. Missing manifest exits 2.
uv run --directory v1 python scripts/verify_reset_v1.py \
  --config splunk/private/lab.toml \
  --reset-id <reset_id> \
  --output reports/runs/reset-<reset_id>.md

# 7c. Seed. Requires data/resets/<reset_id>.json from step 7a; the script also
# refuses any --output-manifest outside data/seed_manifests/.
uv run --directory v1 python scripts/seed_splunk_scenario_evidence_v1.py \
  --config splunk/private/lab.toml \
  --inventory splunk/private/sacrificial_inventory.toml \
  --scenario <scenario_id> \
  --scenario-run-id <scenario_run_id> \
  --reset-id <reset_id> \
  --batch-id <batch_id> \
  --anchor-epoch <epoch> \
  --output-manifest data/seed_manifests/<batch_id>/<scenario_run_id>.json

# 7d. Capture. --require-live-splunk-rows fails closed when no rows match the
# scenario_run_id; do not pass --allow-scaffold-fallback for any row that will
# be promoted to release-candidate.
uv run --directory v1 python scripts/capture_splunk_run_v1.py \
  --config splunk/private/lab.toml \
  --scenario-run-id <scenario_run_id> \
  --reset-id <reset_id> \
  --batch-id <batch_id> \
  --output-dir data/raw_exports/<batch_id>/<scenario_run_id> \
  --require-live-splunk-rows

uv run --directory v1 python scripts/normalize_events_v1.py \
  --input data/raw_exports/<batch_id> \
  --run-manifest data/run_manifests/<batch_id>/scenario_runs.jsonl \
  --output-metadata data/normalized/<batch_id>-normalization.jsonl \
  --output-public data/public_sample/normalized/events.jsonl

uv run --directory v1 python scripts/derive_windows_v1.py \
  --events data/public_sample/normalized/events.jsonl \
  --answer-key data/public_sample/scenarios/answer_key_public_redacted.jsonl \
  --output-dir data/public_sample/derived

uv run --directory v1 python scripts/derive_episodes_v1.py \
  --events data/public_sample/normalized/events.jsonl \
  --answer-key data/public_sample/scenarios/answer_key_public_redacted.jsonl \
  --output data/public_sample/derived/episodes.jsonl

uv run --directory v1 python scripts/derive_edges_v1.py \
  --events data/public_sample/normalized/events.jsonl \
  --output data/public_sample/derived/actor_object_edges.jsonl
```

8. Validate and split:

```bash
uv run --directory v1 python scripts/generate_splits_v1.py \
  --windows data/public_sample/derived/windows_actor_15m.csv \
  --scenario-runs data/public_sample/scenarios/scenario_runs.jsonl \
  --output-dir data/public_sample/splits \
  --seed 20260526

uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all \
  --allow-fixture-only
```

9. Report:

```text
v1/reports/5k_runs/<batch_id>/summary.md
v1/reports/5k_runs/<batch_id>/summary.json
```

Report coverage, row counts, path/outcome counts, leakage metrics, split counts, live probe status, safety scan status, and claim boundary.

## Live Splunk Gating Plan

Representative live probes come before any bounded full run.

Live prerequisites:

- `splunk/private/lab.toml` points to an authorized local lab.
- `splunk/private/sacrificial_inventory.toml` contains only allowlisted sacrificial fixtures.
- `splunk/private/observed_indexes.json` is a fresh snapshot from the lab. `check_splunk_readiness_v1.py` refuses to pass without it and rejects any path outside `splunk/private/`.
- Required HEC token is loaded from `.env` or private config by scripts, but never printed, echoed, logged, copied into reports, or embedded in exception detail.
- Readiness check passes immediately before live work, and is re-run before every reset/capture (not once per session — a stale snapshot is treated as no snapshot).
- Reset and verify reset succeed for the specific scenario. `data/resets/<reset_id>.json` must exist before any seed/capture step references that `reset_id`.
- Seed manifests stay under `v1/data/seed_manifests/` (the seed script enforces this; output paths outside that root exit with code 2).
- Raw captures stay under ignored/private `v1/data/raw_exports/` (the capture script enforces this).
- Run manifests and their `actor_prompts/` subdirectories stay generated/private until redacted. The actor prompt files contain answer-key metadata (`actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, `safety_boundary`) and must not be copied into the public sample, attached to reports, or sent to external evaluators.
- `coverage_summary.json` is also answer-key-shaped (`per_scenario_axis_counts`, `mutual_information_checks`, `scenario_ids`) and lives in the same private tree. Only the summary numbers selected for the public report may be lifted out, and only after a public-safety scan.
- Public artifacts contain only public-safe normalized summaries.

Representative live gate:

1. Run readiness.
2. Reset one scenario at a time.
3. Seed one run.
4. Read back by fresh `scenario_run_id`.
5. Capture with `--require-live-splunk-rows`.
6. Normalize, derive, and validate.
7. Compare protected evidence and downstream visibility for successful synthetic paths.
8. Run public safety scan.
9. Mark failures as non-release-candidate and fix before expanding.

Bounded full live run gate:

- Only after the 5k dry-run allocation passes coverage, leakage, and safety gates, including `coverage_summary.json["leakage_check"] == "pass"`.
- Only after representative live probes pass for each major family.
- Use a fresh batch ID and fresh opaque IDs.
- Enforce per-scenario reset.
- Abort on missing live rows unless an explicitly non-release-candidate scaffold mode is being tested.
- Do not run Openclaw grading.
- Do not widen reset/seed/capture outside sacrificial allowlists.

Fail-closed conditions (each aborts the current row and triggers batch quarantine review):

- Readiness fails or `--observed-indexes-json` is missing/outside `splunk/private/`.
- Reset script refuses the `--scenario` (outside `reset_lab_v1.py` `ALLOWED_SCENARIOS`) or no sacrificial artifacts are configured for that scenario.
- `data/resets/<reset_id>.json` is missing when seed or capture runs.
- HEC/config load raises `LabConfigError`; do not print token values from the exception.
- Capture finds zero live rows for the `scenario_run_id` and `--require-live-splunk-rows` was passed.
- Any captured row references a `scenario_run_id` that is not in the run manifest.
- Public-safety scan finds any private marker, secret, raw SPL, descriptive ID, or overclaiming term.

Mid-batch failure handling:

- A batch that experiences any fail-closed event is marked non-release-candidate as a whole. Do not publish or merge partial output from a quarantined batch into the public sample.
- Quarantined batches stay under `v1/data/run_manifests/<batch_id>/`, `v1/data/seed_manifests/<batch_id>/`, and `v1/data/raw_exports/<batch_id>/` (all gitignored or private). Reproduce or replace them in a fresh batch with a new `--batch-id` rather than retrying in place with `--force`.
- Do not use `generate_training_batch_v1.py --force` to "fix" a quarantined batch; `--force` calls `shutil.rmtree` on the existing `data/run_manifests/<batch_id>/` tree and there is no soft-delete. Move the directory aside under a new name first if any of its rows might still be needed for forensic review.

## Verification Checklist

Local safe checks:

```bash
git diff --check
uv run --directory v1 pytest -q
uv run --directory v1 pytest tests/test_scenario_catalog_v1.py tests/test_path_templates_v1.py tests/test_prompt_pack_v1.py
uv run --directory v1 pytest tests/test_training_batch_generation_v1.py tests/test_label_recovery_probe_v1.py
uv run --directory v1 pytest tests/test_scenario_events_v1.py tests/test_normalize_events_v1.py tests/test_derivation_v1.py
uv run --directory v1 pytest tests/test_split_integrity_v1.py tests/test_relationship_integrity_v1.py tests/test_public_safety_v1.py
uv run --directory v1 python scripts/validate_dataset_v1.py --schemas schemas --check schemas-only
uv run --directory v1 python scripts/public_safety_scan_v1.py docs schemas scenarios
```

Dry-run 5k checks:

```bash
uv run --directory v1 python scripts/generate_training_batch_v1.py \
  --scenario-catalog scenarios/scenario_catalog_v1.jsonl \
  --path-templates scenarios/path_templates_v1.jsonl \
  --prompt-pack scenarios/nondeterministic_prompt_pack_v1.jsonl \
  --batch-id all_scenarios_5k_dry_20260526 \
  --target-runs 5000 \
  --seed 20260526 \
  --no-reset-required \
  --output-dir data/run_manifests/all_scenarios_5k_dry_20260526

# Leakage gate: the generator only reports "pass" when MI is under budget AND
# the sample is large enough (>= 140 rows). Anything else blocks live work.
uv run --directory v1 python -c "
import json, sys, pathlib
summary = json.loads(pathlib.Path('data/run_manifests/all_scenarios_5k_dry_20260526/coverage_summary.json').read_text())
if summary.get('leakage_check') != 'pass':
    sys.exit(f\"leakage_check={summary.get('leakage_check')!r}; live work blocked\")
if not summary.get('all_catalog_scenarios_covered'):
    sys.exit('not all canonical scenarios covered')
"

# Public-safety scan over public-eligible trees only. Do NOT pass the
# run_manifests path to a scanner whose results you intend to publish as
# "safe": dry-run output has no live private content by construction, so a
# clean scan there is not evidence that any subsequent live capture is safe.
uv run --directory v1 python scripts/public_safety_scan_v1.py \
  docs schemas scenarios
```

Live-gated checks:

```bash
uv run --directory v1 python scripts/check_splunk_readiness_v1.py \
  --config splunk/private/lab.toml \
  --observed-indexes-json splunk/private/observed_indexes.json \
  --output reports/runs/splunk-readiness-all-scenarios-5k.md

uv run --directory v1 pytest tests/test_splunk_io_v1.py tests/test_splunk_readiness_v1.py
uv run --directory v1 pytest tests/test_seed_splunk_scenario_evidence_v1.py tests/test_capture_splunk_run_v1.py
```

Release-candidate checks after live capture:

```bash
# Only after live capture, normalize, derive, and split have completed for the
# batch. Without --allow-fixture-only the validator fails closed unless
# data/public_sample/dataset_manifest.json reports release_status="release_candidate";
# do not pass --allow-fixture-only here.
uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all

# Scan only public-eligible inputs. Do not include data/run_manifests/,
# data/seed_manifests/, data/raw_exports/, splunk/private/, or .env.
uv run --directory v1 python scripts/public_safety_scan_v1.py \
  data/public_sample docs schemas scenarios reports/5k_runs/<batch_id>

git diff --check
```

## Public Claim Boundary And Release Gates

Allowed public framing:

- "AI TamperGuard studies bounded synthetic, tamper-congruent observability behavior in an authorized local Splunk lab."
- "A synthetic positive means the row needs review under this dataset definition."
- "The dataset includes paired controls, hard negatives, protected evidence checks, and leakage-aware splits."
- "Metrics are weak-label diagnostics over a research corpus."

Disallowed framing:

- "Detected malicious behavior."
- "Proved compromise."
- "Production-ready tamper detection."
- "Splunk weakness."
- "Model caught an attacker."

Release-readiness gates:

- All canonical scenario workflows represented or explicitly deferred with a documented reason.
- Duplicate design IDs resolved through canonical IDs and stable slugs.
- Every live run has a reset record and reset verification.
- Every positive-proxy row has post-run verification.
- Attempted, blocked, failed, and successful synthetic outcomes are distinct in answer keys and derived features.
- Public artifacts validate against schemas.
- Relationship integrity passes.
- Split integrity passes.
- Label-recovery probes pass.
- Public safety scan passes.
- Reports state per-split label counts and limitations.
- No raw exports, private prompts, run manifests, secrets, tokens, or private lab details are published.

## Open Questions With Defaults

| Question | Default answer |
|---|---|
| Are 5k rows scenario runs or behavior windows? | Treat the target as 5k `windows_actor_15m.csv` rows. If the current one-window-per-run shape remains, generate 5k scenario runs. |
| Are ITSI, ES/SOAR, AI Assistant, MLTK, and MCP actually available in the lab? | If not available, implement public-safe synthetic control-plane fixtures that mimic the observable artifact classes, and mark them as synthetic fixtures. |
| Should duplicate design headings be merged into existing scenarios instead of adding 025-028? | Default to stable slug plus new IDs for duplicate workflows to avoid semantic overloading and preserve existing IDs. |
| Should attempted positives be `label_binary=1`? | Default no. Use `needs_review` with `label_binary=0` unless a reviewed deterministic rule says otherwise. |
| Should blocked probes be positive? | Default no. Blocked probes are `needs_review` or hard negatives unless they also produce verified observability degradation. |
| Should the full 5k run be live? | Default no. Run 5k dry-run first, representative live probes second, and full live only after explicit approval and all gates pass. |
| Should raw exports be public if rows are public-safe? | Default no. Keep `v1/data/raw_exports/` ignored/private; publish only normalized/redacted artifacts and reports after scans. |
| Should Openclaw grading be used? | Default no for this phase. |
