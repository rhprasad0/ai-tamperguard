# AI TamperGuard V1 Test Harness — Adversarial Review

**Reviewer:** Claude Opus 4.7 (max-effort adversarial pass)
**Date:** 2026-05-26
**Scope:** `v1/` harness scripts, tests, scenario catalogs, schemas; `docs/v1-dataset-spec.md`; `docs/v1-dataset-implementation-plan.md`.
**Mode:** Read-only. No source code, tests, or live services touched. Only this findings file is created.

## Coverage of this review

Files read end-to-end during this pass:
- `docs/v1-dataset-spec.md`
- `docs/v1-dataset-implementation-plan.md`
- `v1/scripts/generate_training_batch_v1.py`
- `v1/tests/test_training_batch_generation_v1.py`
- `v1/scenarios/scenario_catalog_v1.jsonl` (all 14 rows)
- `v1/scenarios/path_templates_v1.jsonl` (all 14 rows)
- Directory listings for `v1/scripts/`, `v1/tests/`, `v1/scenarios/`, `v1/schemas/`, `v1/data/`, `v1/config/`, and `docs/`

Files **not** opened during this pass but referenced from structure, naming, or the spec's contract. Findings that depend on these are flagged as "needs verification":
- `v1/scripts/normalize_events_v1.py`, `derive_windows_v1.py`, `derive_episodes_v1.py`, `derive_edges_v1.py`, `generate_splits_v1.py`
- `v1/scripts/capture_splunk_run_v1.py`, `materialize_prompt_pack_runs_v1.py`, `seed_splunk_scenario_evidence_v1.py`, `raw_harness_jsonl_to_training_csv_v1.py`
- `v1/scripts/validate_dataset_v1.py`, `public_safety_scan_v1.py`, `reset_lab_v1.py`, `verify_reset_v1.py`, `check_splunk_readiness_v1.py`
- `v1/scripts/optimize_nondeterminism_goal_v1.py`, `analyze_nondeterminism_goal_v1.py`, `build_public_sample_v1.py`
- The nine `v1/schemas/*.schema.json` files
- All `v1/tests/test_*.py` other than `test_training_batch_generation_v1.py`
- `v1/scenarios/nondeterministic_prompt_pack_v1.jsonl`, `scenario_subset_v1.jsonl`
- `v1/src/ai_tamperguard_v1/path_templates.py`, `prompt_pack.py`, `scenario_catalog.py`
- Run manifests under `v1/data/run_manifests/`

Where this review makes a claim that depends on an unread file, it is explicitly labeled (e.g. "**Needs verification**: …"). Where the claim is grounded in code or data I read, the file path and line range is given.

---

## 1. Executive verdict

**The current V1 harness can mint thousands of varied-looking rows quickly, but those rows would constitute a structurally trivial classification task with multiple, mutually reinforcing label-leakage channels.** The dataset shape declared in `docs/v1-dataset-spec.md` is sound; the *training-batch generation pipeline* (`generate_training_batch_v1.py` + the path-template / prompt-pack JSONL inputs) materially undercuts it.

Specifically, the dry-run training-batch generator I inspected:

1. **Has no live mode.** Its `--mode` argument only accepts `{"dry-run"}` (`v1/scripts/generate_training_batch_v1.py:31`). It writes prompt files and a manifest. It does not execute against Splunk, does not collect audit/configtracker events, and does not produce normalized events, windows, or labels. Tests that read green from this script *do not* attest that any V1 data shape has been produced.
2. **Bakes the label into the scenario identifier.** With exactly one path-template per scenario in `v1/scenarios/path_templates_v1.jsonl`, `scenario_id` → `label_family`/`outcome`/`label_binary_policy` is a one-to-one function. Every scenario's `path_types_supported` in the catalog declares 2–4 paths (e.g. `successful_synthetic`, `attempted_positive`, `hard_negative`, `benign_control`), but only one of those paths is ever instantiated.
3. **Pseudo-randomizes variation axes by modular arithmetic over `run_index`, `attempt_index`, and `seed`.** No actual RNG draws. The cycle is short and perfectly correlated with `scenario_id`. For the test's parameters (`target_runs=42`, `seed=260526`), each scenario sees exactly two of four `actor_profile` values, and which two is fully determined by `scenario_id mod 4`. Same for `distractor_count`. The dataset thus partitions cleanly by `actor_profile` alone.
4. **Repeatedly embeds the scenario_id into supposedly opaque public IDs.** `synthetic_case_id`, `sacrificial_report_id`, and `scenario_run_id` all literally contain the last three digits of `scenario_id` (or worse, the full `scenario_id` + `path_type`). These are not pseudonyms — they leak both the scenario family and the label by construction (`v1/scripts/generate_training_batch_v1.py:115-117`).
5. **Writes `ground_truth_family`, `outcome`, `label_source`, `path_type`, and the path-template ID directly into `scenario_runs.jsonl`** (`v1/scripts/generate_training_batch_v1.py:147-173`). Unless a downstream allow-list strips these before windows.csv, every training row carries explicit labels in non-`feature_*` columns.
6. **Generates zero windows from the dry-run path.** `--target-windows-min/max` are validated against each other but never consumed. The `test_training_batch_generation_v1.py:30-34` test asserts these are stored in the coverage summary; that assertion is a confidence trap — no windows are produced and the assertion still passes.
7. **Asserts variation by `distinct-value-count > 1`,** not by independence from the label, not by balance, not by content-level diversity. The test cannot fail when only two of four `actor_profile` values appear or when `actor_profile` perfectly predicts `scenario_id`.

The downstream live-capture / normalize / derive / split chain that the spec describes (`v1/scripts/capture_splunk_run_v1.py`, `normalize_events_v1.py`, `derive_*`, `generate_splits_v1.py`, `validate_dataset_v1.py`, `public_safety_scan_v1.py`) is **architecturally sound on paper** and the README, schemas, and spec do mention leakage and small-sample concerns. **But none of those defenses are reached by the training-batch generator I inspected, because that generator skips the live-run / normalize / derive chain entirely.** The risk is therefore not a bug in one file; it is that the *training-batch* path is a separate, lower-fidelity track that can produce "thousands of rows" without ever invoking the spec's quality gates.

**Recommendation, headline:** Do not publish, train on, or report metrics from a corpus built with the current `generate_training_batch_v1.py` until: (a) `scenario_run_id`, `synthetic_case_id`, `sacrificial_report_id`, `ground_truth_family`, `path_type`, `path_template_id`, `prompt_variant_id`, `attempt_index`, and the modular variation axes are either stripped at the windows.csv boundary or sanitized; (b) multiple `path_types` per scenario are actually instantiated; (c) variation axes are drawn by a real seeded RNG, not modular arithmetic on `run_index`; (d) the test suite asserts label-axis *independence*, not just distinct-value counts.

---

## 2. Highest-risk false-green paths

Each item below cites a specific code location (or, when the code wasn't read, the test or data file that should have caught it). "False green" = the test passes, but the underlying property the test is supposed to attest is not actually true.

### F1. `scenario_id` is the label (bijective leakage)

`v1/scenarios/path_templates_v1.jsonl` has exactly 14 rows — one per scenario. The training-batch generator selects a template by `scenario_templates[(attempt_index - 1) % len(scenario_templates)]` (`generate_training_batch_v1.py:109`). With one template per scenario, every attempt for `scenario_010` is `scenario_010_successful_synthetic_v1`; every attempt for `scenario_013` is `scenario_013_benign_control_v1`; etc.

Result: `label_family`, `outcome`, and `label_binary_policy` are constant per scenario. A classifier trained on any column from `scenario_runs.jsonl` that mentions `scenario_id`, `scenario_family`, `path_template_id`, `synthetic_case_id`, `sacrificial_report_id`, or `scenario_run_id` hits 100% by memorization.

The catalog (`v1/scenarios/scenario_catalog_v1.jsonl`) declares richer `path_types_supported` per scenario — e.g. `scenario_010` supports `["successful_synthetic","attempted_positive","hard_negative","benign_control"]` — so the bug surface is "we promised four paths and shipped one," not "we never planned for variation."

**Test that should have caught this and does not:** `test_training_batch_generation_v1.py` only asserts `coverage["scenario_count"] == 14` and that all scenarios are covered. It never asserts that each scenario has been observed under at least 2 distinct `path_type` values, nor that any scenario has both a benign-control and a positive-proxy row.

### F2. Modular-arithmetic axes create scenario-stratified partitions

In `generate_training_batch_v1.py:111-114`:

```python
actor_profile = actor_profiles[(run_index + seed) % len(actor_profiles)]
evidence_order = evidence_orders[(attempt_index + seed) % len(evidence_orders)]
conflict_intensity = conflict_levels[(run_index + attempt_index + seed) % len(conflict_levels)]
distractor_count = distractor_counts[(run_index + seed) % len(distractor_counts)]
```

Because `run_index` advances 1, 2, 3, … and `scenario = scenarios[(run_index - 1) % 14]`, **`run_index mod 14` determines `scenario_id`** for the whole batch. Then:

- `actor_profile_index = (run_index + seed) % 4` — modulus 4 vs. scenario period 14. `gcd(14, 4) = 2`, so each scenario sees only `14 / gcd(14, 4) … / 4 = 7 / 2` distinct indices? Concretely, since `run_index` for scenario_k advances by 14 each cycle and `14 mod 4 = 2`, `actor_profile_index` for that scenario alternates between exactly two values: `(k + seed) mod 4` and `(k + seed + 2) mod 4`. **Each scenario sees only 2 of 4 actor profiles.** Same construction for `distractor_count`.
- `evidence_order_index = (attempt_index + seed) % 4` — attempt_index is just `1, 2, 3, …` *within* a scenario, so this *does* cycle through all 4 values. But it cycles in **perfect lockstep** within every scenario, so the position of an attempt inside a scenario fully predicts `evidence_order`. Combined with `attempt_index` also being a manifest column, this is another short-circuit.
- `conflict_intensity_index = (run_index + attempt_index + seed) % 3` — `gcd(14, 3) = 1`, so within a scenario this does walk all three values, but again deterministically.

Net effect: **`actor_profile` alone partitions the dataset into pairs of scenarios.** Even after stripping `scenario_id`, `actor_profile` plus `evidence_order` plus `conflict_intensity` reconstructs `(run_index mod 14, attempt_index mod 12)`, which reconstructs `scenario_id`.

**Test that should have caught this and does not:** `test_training_batch_generation_v1.py:68-70` asserts only `len({row["actor_profile"] for row in rows}) > 1`. With `target_runs=42`, the test sees 4 distinct `actor_profile` values across scenarios (it cycles 1→3, 2→0, 3→1, 4→2, 5→3, …), so the assertion passes. It does not partition by scenario and check independence.

### F3. Public IDs literally contain the scenario_id

```python
run_id = f"{scenario.scenario_id}_{path_template.path_type}_{prompt_variant.prompt_variant_id}_attempt_{attempt_index:03d}"
synthetic_case_id = f"synthetic_case_{scenario.scenario_id[-3:]}_{seed}_{attempt_index:03d}"
sacrificial_report_id = f"report_{scenario.scenario_id[-3:]}_{attempt_index:03d}"
```
(`v1/scripts/generate_training_batch_v1.py:115-117`)

- `scenario_run_id` contains both `scenario_id` and `path_type`. `path_type` is literally one of `{benign_control, gray_zone, blocked, successful_synthetic, attempted_positive, hard_negative}` — the public-facing label vocabulary.
- `synthetic_case_id` includes the last three digits of `scenario_id`. Since `scenario_id ∈ {scenario_004, scenario_006, …}` the last three digits *are* the entire informational content of `scenario_id`.
- `sacrificial_report_id` carries the same three digits.

The spec is explicit (`docs/v1-dataset-spec.md:41`): "*These opaque IDs must be content-free (for example, random UUIDs or short stable hashes) and must not embed hostnames, usernames, environment names, or other descriptive strings.*" The current generator embeds the scenario identifier, which **is** a descriptive string for label purposes. Any window row that ships `synthetic_case_id`, `sacrificial_report_id`, or `scenario_run_id` ships the label.

### F4. `ground_truth_family` written into the run manifest

`v1/scripts/generate_training_batch_v1.py:154-156`:
```python
"ground_truth_family": path_template.label_family,
"outcome": path_template.outcome,
"label_source": path_template.label_binary_policy,
```

`label_source` here is being filled with `path_template.label_binary_policy` (values like `"benign"`, `"positive_proxy"`, `"needs_review"`) rather than with the controlled `label_source` vocabulary from the spec (`scenario_answer_key`, `paired_benign_control`, `manual_review`, `heuristic_rule`, …). That is both a schema-fidelity bug and a leakage hazard: a downstream consumer that pulls `label_source` as a feature gets the label directly.

**Needs verification:** does `v1/schemas/scenario_run_v1.schema.json` enforce the `label_source` controlled vocabulary? If yes, this manifest probably fails validation today. If no, the schema is permissive and the leak ships.

### F5. `--target-windows-min/max` are vestigial; the test still asserts them

`generate_training_batch_v1.py:72-73` validates `min <= max` and `:182-183` echoes them into the coverage summary. **The script never emits windows.** No `windows_actor_5m.csv` or equivalent is produced.

`test_training_batch_generation_v1.py:32-34, 61-62` passes `--target-windows-min 5000 --target-windows-max 5500` and asserts `coverage["target_windows_min"] == 5000`. The test name (`test_generate_training_batch_writes_all_scenario_dry_run_manifest`) is honest, but a reader scanning the coverage summary plus the assertion sees "5000 windows" with no signal that zero were actually written.

### F6. Round-robin scheduling guarantees exact per-class balance

`scenario = scenarios[(run_index - 1) % len(scenarios)]` (`generate_training_batch_v1.py:101`). For `target_runs = N`, every scenario gets `floor(N/14)` or `ceil(N/14)` attempts. Class balance is structurally exact, which:

1. Makes per-class accuracy a meaningless metric (no realistic class skew).
2. Lets any model that overfits to a single per-scenario feature recover both class accuracy *and* per-class balance.
3. Will look excellent in `coverage["family_counts"]` even when the underlying signal is degenerate.

### F7. `scenario_run_id` does not include `batch_id`

`run_id = f"{scenario.scenario_id}_{path_template.path_type}_{prompt_variant.prompt_variant_id}_attempt_{attempt_index:03d}"` (`generate_training_batch_v1.py:115`).

Two batches with the same `--seed` (or any two batches whose attempt counters align) will mint identical `scenario_run_id` values. Any downstream consumer that:

- de-duplicates by `scenario_run_id` (per the spec, splits must group by it), or
- joins multiple batches' manifests into one corpus,

will either silently drop rows, silently overwrite, or — worse — pair benign and positive batches under the same ID, corrupting paired-control logic.

**Test that should have caught this and does not:** there is no cross-batch uniqueness test among the inspected tests. The generation test exercises one batch.

### F8. `--force` calls `shutil.rmtree` with no second confirmation

`generate_training_batch_v1.py:78-80`:
```python
if normalized_output.exists():
    if not force:
        raise SystemExit(f"output directory already exists; pass --force to replace: {normalized_output}")
    shutil.rmtree(normalized_output)
```

`_is_under_run_manifests` bounds the deletion to `data/run_manifests/<...>`, so the blast radius is the run-manifests tree. Still: a user mistyping `--batch-id` and re-running with `--force` to "fix" the error will silently wipe a real batch whose manifest is their only audit record of which lab runs produced which evidence. No backup, no soft-delete, no log line preserving the wiped manifest.

### F9. Dry-run actor prompts inhabit the same tracked tree as the manifest

`prompt_dir = normalized_output / "actor_prompts"` (`generate_training_batch_v1.py:81`). The prompt file content includes (lines 132-141): `scenario_run_id`, `prompt_variant_id`, `path_template_id`, `path_type`, `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, `safety_boundary`. Several of these are public-safety markers (good); several are *answer-key markers* (bad if these prompts are ever shipped to a model evaluator or committed to the public sample).

`v1/.gitignore` is 47 bytes — too small to cover `data/run_manifests/`. **Needs verification:** if `data/run_manifests/` is tracked (default per the implementation plan), then any committed dry-run batch publishes the answer key in plaintext prompt files. The spec's redaction methodology covers normalized events; it does not obviously cover these prompts.

### F10. `prompt_variant`, `path_template`, and `object_family` selection is round-robin, not seeded

```python
prompt_variant = prompt_variants[(attempt_index - 1) % len(prompt_variants)]
path_template = scenario_templates[(attempt_index - 1) % len(scenario_templates)]
object_family = scenario.allowed_object_types[(attempt_index - 1) % len(scenario.allowed_object_types)]
```
(`generate_training_batch_v1.py:107-110`)

Three round-robins keyed off the same counter. They are guaranteed to align cyclically: `attempt_index = 1` always picks the first prompt variant, the first (and only) path template, and the first object_family. For any model attempting to learn an interaction between these axes, the interactions are degenerate.

### F11. Test asserts only first-order distinct-counts; never independence

`test_training_batch_generation_v1.py:68-70`:
```python
assert len({row["actor_profile"] for row in rows}) > 1
assert len({row["evidence_order"] for row in rows}) > 1
assert len({row["conflict_intensity"] for row in rows}) > 1
```

These three assertions are simultaneously the strongest variation guarantees in the test suite I inspected, and they prove almost nothing. A dataset that always sets `actor_profile = scenario_id` would pass all three. The test never checks:

- mutual independence of `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count` from `scenario_id`,
- balance of `path_type`, `object_family`, `prompt_variant_id` within each scenario,
- absence of perfect collinearity between `attempt_index` and `evidence_order`,
- that two distinct `--seed` values produce *qualitatively different* (not merely rotated) coverage.

### F12. **Needs verification** — likely false-green: validate_dataset / public_safety_scan over dry-run output

The implementation plan promises (`docs/v1-dataset-implementation-plan.md:721-732`) that `public_safety_scan_v1.py` and `validate_dataset_v1.py` run against `data/raw_exports`, `data/run_manifests`, `data/public_sample`, etc. **Risk:** the scanner is documented as "fail closed for matches in public paths." If it is configured to scan `data/run_manifests/<batch>/` for hostnames, IPs, tokens, etc., it will find none — *because the dry-run generator never produced any private content*. A scanner pass on a dry-run batch is therefore evidence of absence-of-real-data, not evidence of safe data. This is a false green if anyone later reads "public_safety_scan: PASS" as "this corpus is safe to publish."

**Recommendation for verifying:** read `v1/scripts/public_safety_scan_v1.py` and `v1/tests/test_public_safety_v1.py`. Confirm the scanner distinguishes "scanned and found nothing dangerous" from "scanned trivial dry-run content."

### F13. **Needs verification** — split-leakage and feature-leakage gates

Spec (`docs/v1-dataset-spec.md:325-330`) and plan (`:649-652`) require that splits group by `scenario_run_id`, that paired controls stay together, and that the split manifest record cross-split actors/objects. Tests `test_split_integrity_v1.py` (832 bytes — very small) and `test_relationship_integrity_v1.py` (772 bytes — very small) are too short to plausibly enforce the full set of invariants the spec requires. **Risk:** these tests likely check schema shape, not adversarial split integrity. Verify before trusting any "split-integrity: PASS" report.

### F14. **Needs verification** — feature column allowlist enforcement

The spec lists ~50 `feature_*` column names (`docs/v1-dataset-spec.md:194-244`) and says "Model-consumable features must use `feature_*` names and be numeric or boolean." It does not — at least not in the prose I read — say that *non-`feature_*`* columns must be absent from `windows_actor_15m.csv`. If `derive_windows_v1.py` ends up adopting passthrough columns like `scenario_run_id`, `actor_id`, `path_type`, `label_source`, that's exactly what enables the leakage of F1–F4 into the final training set.

---

## 3. Coverage gaps for extending deliberate nondeterminism + attack paths to all scenarios

### G1. Each scenario has one path template; the catalog promises multiple

| Scenario | `path_types_supported` (catalog) | Templates in `path_templates_v1.jsonl` |
|---|---|---|
| `scenario_004` | `benign_control, hard_negative` | only `benign_control` |
| `scenario_006` | `gray_zone, hard_negative, blocked` | only `gray_zone` |
| `scenario_007` | `blocked, attempted_positive, hard_negative` | only `blocked` |
| `scenario_010` | `successful_synthetic, attempted_positive, hard_negative, benign_control` | only `successful_synthetic` |
| `scenario_011` | same 4 | only `successful_synthetic` |
| `scenario_012` | same 4 | only `successful_synthetic` |
| `scenario_013` | `benign_control, hard_negative` | only `benign_control` |
| `scenario_014` | same 4 as 010 | only `successful_synthetic` |
| `scenario_015` | same 4 | only `successful_synthetic` |
| `scenario_016` (optional) | same 4 | only `successful_synthetic` |
| `scenario_017` | same 4 | only `successful_synthetic` |
| `scenario_018` | `benign_control, hard_negative` | only `benign_control` |
| `scenario_021` (future) | `successful_synthetic, attempted_positive, blocked, hard_negative` | only `attempted_positive` |
| `scenario_023` (future) | same 4 as 010 | only `successful_synthetic` |

This is the dominant coverage gap. Attempted-positive and hard-negative variants are *the* hard cases for a tamper detector — they are where a model has to disambiguate "intent expressed but blocked" from "intent succeeded" and "looks like tamper but is maintenance." None of those are present.

### G2. All path templates share the identical `expected_action_sequence`

Every row in `v1/scenarios/path_templates_v1.jsonl` carries:
```
"expected_action_sequence":["read synthetic case context","inspect authorized public-safe telemetry summary","record bounded outcome without touching protected evidence"]
```

This phrase is the *benign-control* trajectory. It is wrong as the canonical sequence for:

- `scenario_010_successful_synthetic_v1` (dashboard alibi factory — should include `read protected evidence, modify sacrificial dashboard, requery to confirm hidden`),
- `scenario_011_successful_synthetic_v1` (saved-search narrowing — should include `search evidence, modify saved search, requery to confirm narrowed result`),
- `scenario_012_successful_synthetic_v1` (alert suppression),
- `scenario_014_successful_synthetic_v1` (throttle-before-creation),
- `scenario_015_successful_synthetic_v1` (risk-score tuning),
- `scenario_017_successful_synthetic_v1` (macro broadening),

…and so on for almost every non-benign template. The action sequence is the most natural place to encode the tamper trajectory; today it is a static placeholder that contradicts the positive_condition of the scenario it belongs to.

### G3. Variation axes declared but not exercised

Each scenario row declares `variation_axes_supported` including `tool_budget`, `prompt_family`, and `outcome_target`. The generator varies `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, `object_family`, `prompt_variant_id` (round-robin), and nothing else.

`tool_budget` is consumed via `prompt_variant.max_tool_budget` (`generate_training_batch_v1.py:126, 167`), so it is *carried* but not *varied independently* of the chosen prompt variant. `outcome_target` is entirely absent.

### G4. No multi-actor / delegation / adversarial-retry paths

The catalog implicitly assumes one actor per run (`actor_profile` is a single string, the run manifest has one `actor_id`). Real evidence-laundering trajectories include:

- one actor reading evidence, a different actor making the visibility change;
- an actor probing permissions, getting blocked, retrying via a different surface;
- a benign maintenance window during which an adversarial change is made;
- a successful tamper followed by an alibi report by the same actor;
- audit-log rotation or HEC-token cycling that obscures the chain.

None of these are present. The current trajectories are linear single-actor sequences with one verification.

### G5. No deliberate signal-degradation / noise scenarios

There is no equivalent of:

- timing jitter that shifts the `feature_search_to_change_min_gap_bucket`,
- decoy reads against unrelated objects to dilute `feature_evidence_target_overlap_count`,
- intentional collisions in `actor_id` across runs to stress actor-leakage tests,
- rare-but-benign sequences that look positive-shaped (read-then-modify by an admin during incident response).

Without these, a model can lean on coarse counts and still hit 1.0 AUC on this corpus.

### G6. Prompt-pack variation is asserted but content variation is not measured

The training-batch test asserts that `prompt_variant_id` distinct count is > 1, but no test inspects the rendered prompt content (`prompt_variant.render(...)`, `generate_training_batch_v1.py:119-130`) to check that different variants emit materially different stimuli. `test_ready_eval_prompt_variation_v1.py` (2,542 bytes) exists — **needs verification** that it does this. If it only checks template metadata diversity, the corpus could ship hundreds of "variants" that all expand to near-identical text.

### G7. Reset records and run manifests are independent of training-batch generation

The training-batch generator does not call into `reset_lab_v1.py` or `capture_splunk_run_v1.py`. The manifests it writes carry no `reset_id`. Yet the spec's quality-gate language (`docs/v1-dataset-spec.md:350-352`) requires every included run to have a reset record. **Risk:** if the training-batch manifest is ever fed into the public-sample build, the sample may contain rows whose `reset_id` is null or fabricated. There is no test asserting `reset_id` linkage across the training-batch boundary.

### G8. `paired_control_scenario_ids` are declared but not enforced at generation time

`scenario_010` is paired with `scenario_004`; `scenario_012` paired with `scenario_013`; `scenario_017` paired with `scenario_018`; etc. The training-batch generator does not co-schedule pairs into the same split-eligible bucket. The split generator (per spec) keeps pairs together by `scenario_run_id`, but only *if* the manifest carries a `paired_run_id` linkage. The training-batch manifest does not (`generate_training_batch_v1.py:147-173`).

### G9. The `nondeterminism goal harness` is decoupled from the training-batch path

`v1/scripts/optimize_nondeterminism_goal_v1.py` (12.9 KB), `analyze_nondeterminism_goal_v1.py`, and `v1/config/nondeterminism_goal_defaults.yaml` exist as a parallel track. **Needs verification:** is the nondeterminism budget actually consumed by `generate_training_batch_v1.py`? It does not appear to be (no import of `nondeterminism_goal` modules in the generator I read). If the budget exists only as a measurement after the fact, it cannot *steer* generation toward un-leaky variation.

---

## 4. Risks for generating a few-thousand-row training set

Suppose a user runs:
```
generate_training_batch_v1.py --target-runs 2800 --seed 12345 --mode dry-run
```

That is 200 attempts per scenario. The resulting manifest will have **2800 rows of apparent variation** that suffer from:

1. **Perfect bijection scenario_id ↔ label.** 14 scenario_ids, 14 (label_family, outcome) pairs, one of each per scenario. AUC ≥ 0.999 from `scenario_id` alone.
2. **Three additional perfect leakage channels** — `scenario_run_id`, `synthetic_case_id`, `sacrificial_report_id`, `path_template_id` — each independently recovers the label.
3. **A fifth, less obvious leakage channel** — `(actor_profile, distractor_count)` partitions scenarios into 7 pairs, so the joint distribution recovers `scenario_id mod 2` exactly and `scenario_id` with one bit of ambiguity.
4. **Per-class balance of ~200/200/200/…** which kills any meaningful precision/recall reporting and lets a constant-predictor with the right per-class bias look strong.
5. **Two distinct `--seed` runs at the same `--target-runs` produce identical row-by-row labels and a *rotation* of the variation axes,** so cross-seed diversity is illusory.
6. **No `reset_id`, no `paired_run_id`, no live-Splunk evidence backing any row** — so the split manifest's "live-run-derived" attestation (`docs/v1-dataset-spec.md:672-677`) cannot be honestly produced for this corpus.
7. **Combinatorial reach of variation axes is ≤ 192** (4 actor × 4 evidence × 3 conflict × 4 distractor) before any axis interacts with `scenario_id` or `attempt_index`, and the modular arithmetic only ever visits a deterministic ≤ 14-sized rotation of those 192 combinations per scenario. Asking for 2,800 rows yields ≤ 192 *unique* (scenario, axis-tuple) signatures, each repeated ~14× — far short of the "lots of variation" implied by the row count.
8. **Cross-batch ID collision** (F7) means the second 2,800-row batch *cannot be safely merged* with the first.
9. **Prompt-pack content is rendered once per `(scenario, prompt_variant, attempt-modulo-N)`,** so over 2,800 rows there are at most `14 * |prompt_variants|` unique prompt bodies. The remainder are exact textual duplicates.
10. **No path through this generator touches `normalize_events_v1.py`, `derive_*`, `generate_splits_v1.py`, or `validate_dataset_v1.py`,** so none of the quality gates fire.

**Conservative cap on usefulness:** the current generator can mint a few thousand rows fast, but treat the output as a *catalog smoke test*, not a training corpus. Reporting any model metric on this corpus would over-state what V1 has actually achieved.

---

## 5. Concrete recommended fixes (priority-ordered)

Severity codes: **P0** = block any training-corpus publication or model-metric reporting; **P1** = fix before the next cross-batch merge or external review; **P2** = strengthens defenses but not strictly blocking.

### P0 — block-publication fixes

#### P0-1. Sanitize manifest IDs so they do not encode the label

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:115-117`.
- **Change:** replace
  ```python
  run_id = f"{scenario.scenario_id}_{path_template.path_type}_{prompt_variant.prompt_variant_id}_attempt_{attempt_index:03d}"
  synthetic_case_id = f"synthetic_case_{scenario.scenario_id[-3:]}_{seed}_{attempt_index:03d}"
  sacrificial_report_id = f"report_{scenario.scenario_id[-3:]}_{attempt_index:03d}"
  ```
  with random / hash-based opaque IDs derived from `(batch_id, scenario_id, attempt_index, seed)` using a stable HMAC. Keep the descriptive name for *private* logs only.
- **Test to add:** `v1/tests/test_training_batch_generation_v1.py` — assert that no row's `synthetic_case_id`, `sacrificial_report_id`, or `scenario_run_id` contains any substring of `scenario_id`, `scenario_family`, `path_type`, `outcome`, or any value drawn from the `label_family` controlled vocab.

#### P0-2. Bind label allowlist at the windows.csv / public-sample boundary

- **Files to change (likely):** `v1/scripts/derive_windows_v1.py`, `v1/scripts/build_public_sample_v1.py`, `v1/schemas/behavior_window_v1.schema.json`. (Read these files; this fix is partially inferred from spec.)
- **Change:** explicitly allow-list columns in the published windows CSV to `{ window_id, scenario_run_id (hashed, see P0-1), reset_id (hashed), actor_id (hashed), window_type, window_start_relative_sec, window_end_relative_sec, label_binary, label_family, label_source, label_confidence, outcome, split_id, feature_* }`. Reject any other column at validate time.
- **Test to add:** `v1/tests/test_derivation_v1.py` (already 9.2 KB — should extend) — assert that no published row contains `synthetic_case_id`, `sacrificial_report_id`, `path_template_id`, `path_type`, `ground_truth_family`, `prompt_variant_id`, `attempt_index`, `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, `object_family`, `batch_id`, or `prompt_seed`.

#### P0-3. Add multiple path templates per scenario

- **Files to change:** `v1/scenarios/path_templates_v1.jsonl` (data file, expand from 14 → ~40 rows so every scenario gets at least the path_types its catalog row declares).
- **Test to add:** `v1/tests/test_path_templates_v1.py` (already 3 KB) — assert that for every catalog row, the set of `path_templates` it has matches the catalog's `path_types_supported`.
- **Generator change:** `v1/scripts/generate_training_batch_v1.py:108-109` — replace `(attempt_index - 1) % len(scenario_templates)` with a per-attempt draw that *balances* across the supported `path_types` (e.g. round-robin over `path_type` first, then over templates within that type). When the catalog lists `successful_synthetic, attempted_positive, hard_negative, benign_control`, the batch should over time emit close to equal counts of each *per scenario*.

#### P0-4. Replace modular-arithmetic variation with a seeded RNG and reject correlated tuples

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:111-114` and the variation-axis constants `:96-99`.
- **Change:** instantiate `random.Random(seed_for_run)` and draw `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, `object_family`, `prompt_variant`, `path_template` independently. After the full batch is drawn, run an independence check vs. `scenario_id` and re-roll any axis whose χ² (or mutual-information) vs. `scenario_id` exceeds a threshold. Persist the seed used per row so reproducibility is preserved.
- **Test to add:** `v1/tests/test_training_batch_generation_v1.py` — for a batch of ≥ 280 runs (20 per scenario), assert that the mutual information between `scenario_id` and each of `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count` is below some explicit budget (e.g. `< 0.1 * H(scenario_id)`).

#### P0-5. Put `batch_id` into `scenario_run_id`

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:115`.
- **Change:** include a deterministic hash of `batch_id` in the run_id, so two batches cannot collide.
- **Test to add:** `v1/tests/test_training_batch_generation_v1.py` — run the generator twice with different `--batch-id` and the same other args; assert intersection of `scenario_run_id` sets is empty.

#### P0-6. Make `--target-windows-min/max` either functional or remove them

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:27-29, 71-73, 182-183`; `v1/tests/test_training_batch_generation_v1.py:32-34, 61-62`.
- **Change (preferred):** remove the args. Dry-run generation does not produce windows; the coverage summary should report `scenario_run_count` and `actor_prompt_count` only.
- **Change (alternative):** add a `--produce-windows` mode that calls into the derive chain on synthetic fixtures and produces an actual windows CSV. In that case keep min/max as a budget and *assert in tests* that the produced count is in range.

### P1 — pre-merge / pre-review fixes

#### P1-1. Make the training-batch generator carry `reset_id` and `paired_run_id`

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:147-173`.
- **Change:** require the generator to consume a `reset_manifest` path (or a `--no-reset-required` flag for clearly-marked dry runs) and to look up each scenario's `paired_control_scenario_ids` from the catalog and emit `paired_run_id` for the row that will pair with it.
- **Test to add:** `v1/tests/test_training_batch_generation_v1.py` — assert that for every paired scenario in the catalog, the manifest has at least one row with a non-null `paired_run_id`, and the pair partner exists in the same manifest.

#### P1-2. Replace the test's distinct-count assertions with independence assertions

- **Files to change:** `v1/tests/test_training_batch_generation_v1.py:68-70`.
- **Change:** assert per-scenario diversity, not global diversity. For each `scenario_id`, the test should:
  - count distinct `actor_profile`, `evidence_order`, `conflict_intensity`, `distractor_count`, `path_type`, `prompt_variant_id`, `object_family` values;
  - require each per-scenario distinct count be ≥ a documented minimum (e.g. `actor_profile ≥ 3`, `path_type ≥ 2` once P0-3 ships);
  - assert each axis's joint distribution with `scenario_id` has entropy below a documented mutual-information budget.

#### P1-3. Enforce `label_source` vocabulary

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:156`; `v1/schemas/scenario_run_v1.schema.json` and `answer_key_v1.schema.json`.
- **Change:** stop using `label_binary_policy` (values like `"benign"`, `"positive_proxy"`) as `label_source`. Use the spec's vocabulary (`scenario_answer_key`, `paired_benign_control`, `manual_review`, …).
- **Test to add:** `v1/tests/test_schema_contracts_v1.py` (already 9.1 KB) — enforce the controlled vocabulary by reading `enum:` from the schema and asserting every manifest value is in the enum.

#### P1-4. Differentiate per-template `expected_action_sequence`

- **Files to change:** `v1/scenarios/path_templates_v1.jsonl`; `v1/tests/test_path_templates_v1.py`.
- **Change:** give each template a scenario-and-path-type-specific action sequence. Add a test that asserts unique action sequences per `(scenario_id, path_type)` so the corpus does not collapse to one trajectory.

#### P1-5. Cover `data/run_manifests/` in `.gitignore` or harden the dry-run artifacts

- **Files to change:** `v1/.gitignore` (47 bytes today — confirm what it actually contains).
- **Change:** either (a) add `v1/data/run_manifests/` to `.gitignore` and document that batches must be regenerated, or (b) sanitize the actor-prompt files (`generate_training_batch_v1.py:131-145`) to drop the answer-key-revealing metadata before writing. **Verify** which is correct given the data-dictionary policy on run manifests.

#### P1-6. Tie nondeterminism budget to the generator

- **Files to change:** `v1/scripts/generate_training_batch_v1.py`; `v1/config/nondeterminism_goal_defaults.yaml`; `v1/scripts/optimize_nondeterminism_goal_v1.py`.
- **Change:** load the nondeterminism budget at the top of the generator and *fail loud* if the produced batch's mutual information with the label exceeds the budget. Today the budget is decoupled.

#### P1-7. Coverage summary should expose the leakage tests, not just counts

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:178-196`.
- **Change:** in `coverage_summary.json`, in addition to `family_counts`, `path_type_counts`, `label_source_counts`, add:
  - per-scenario `actor_profile_counts`, `evidence_order_counts`, `conflict_intensity_counts`, `distractor_count_counts`, `object_family_counts`;
  - global mutual-information estimates between `scenario_id` and each variation axis (with a documented sample-size caveat);
  - the leakage assertions from P1-2 as a `leakage_check: pass|fail|insufficient_sample`.
- **Test:** assert these new fields exist and that `leakage_check` is computed (without locking in a specific numeric).

### P2 — defense-in-depth

#### P2-1. Add adversarial path variants to the catalog

- **Files to change:** `v1/scenarios/path_templates_v1.jsonl`.
- **Change:** add multi-actor, retry-after-block, alibi-after-success, and partial-failure path types. None of these change the public claim boundary; they just stress the model.

#### P2-2. Add a "live-mode" path or remove the `--mode` plumbing

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:31`.
- **Change:** either implement `--mode live` that dispatches to `capture_splunk_run_v1.py` per row (with readiness/reset gating) or drop the `--mode` argument so the script's purpose ("dry-run catalog smoke") is unambiguous. Today `choices={"dry-run"}` reads as a stub.

#### P2-3. Cross-batch dedup test for the public sample build

- **Files to change (likely):** `v1/scripts/build_public_sample_v1.py`; add a new test or extend `test_public_safety_v1.py`.
- **Change:** when assembling the public sample, fail closed on duplicate `scenario_run_id` across input batches and also on duplicate `synthetic_case_id` or `sacrificial_report_id`.

#### P2-4. Strengthen `_normalize_relative_output_dir` semantics

- **Files to change:** `v1/scripts/generate_training_batch_v1.py:207-213`.
- **Change:** require the user to be in the `v1/` directory explicitly (e.g. by detecting a `pyproject.toml`/`README.md` marker in cwd) instead of using `Path.cwd()` blindly. Today running from the wrong directory either silently writes to the wrong place or raises a hard-to-diagnose `relative_to` error.

#### P2-5. Schema-level rejection of `feature_*` that aren't numeric/boolean

- **Files to change:** `v1/schemas/behavior_window_v1.schema.json`.
- **Change:** enforce the spec's "must be numeric or boolean" requirement at the schema layer with `"type": ["number", "boolean", "integer"]` patternProperties on `^feature_`.

#### P2-6. Add a "label-recovery probe" CI step

- **Files to change:** add `v1/tests/test_label_recovery_probe_v1.py`.
- **Change:** train a trivially-small logistic regression on the variation-axis columns (everything that is *not* a `feature_*` column except `label_binary`) against `label_binary` in the dry-run batch. Assert that AUC is ≤ some documented threshold close to 0.5. This is the strongest single guard against future regressions in F1–F4.

---

## 6. Suggested validation commands

Commands are split into **safe local** (no Splunk, no network outbound) and **live/Splunk-gated** (require lab credentials, a real Splunk endpoint, and a successful readiness check). Run only the safe set unprompted.

### Safe local

These should be executable on any developer laptop without touching Splunk:

```bash
# Schema and structural contracts
uv run --directory v1 pytest tests/test_schema_contracts_v1.py
uv run --directory v1 pytest tests/test_relationship_integrity_v1.py
uv run --directory v1 pytest tests/test_split_integrity_v1.py
uv run --directory v1 pytest tests/test_public_safety_v1.py

# Catalog / path-template / prompt-pack data files
uv run --directory v1 pytest tests/test_scenario_catalog_v1.py
uv run --directory v1 pytest tests/test_path_templates_v1.py
uv run --directory v1 pytest tests/test_prompt_pack_v1.py
uv run --directory v1 pytest tests/test_ready_eval_prompt_variation_v1.py

# Dry-run training-batch generator (the script reviewed here)
uv run --directory v1 pytest tests/test_training_batch_generation_v1.py

# Derivation / normalization / harness CSV (no Splunk required if these read fixtures)
uv run --directory v1 pytest tests/test_derivation_v1.py
uv run --directory v1 pytest tests/test_normalize_events_v1.py
uv run --directory v1 pytest tests/test_raw_harness_jsonl_to_training_csv_v1.py
uv run --directory v1 pytest tests/test_scenario_events_v1.py

# Whole local pytest sweep (excludes any live-marked tests)
uv run --directory v1 pytest -k 'not splunk and not live'

# Schema-only validation
uv run --directory v1 python scripts/validate_dataset_v1.py --schemas schemas --check schemas-only

# Public-safety scan against documentation and tracked scenario / schema dirs
uv run --directory v1 python scripts/public_safety_scan_v1.py docs schemas scenarios

# Smallest possible smoke of the generator (14 runs = one per scenario)
uv run --directory v1 python scripts/generate_training_batch_v1.py \
  --scenario-catalog scenarios/scenario_catalog_v1.jsonl \
  --path-templates scenarios/path_templates_v1.jsonl \
  --prompt-pack scenarios/nondeterministic_prompt_pack_v1.jsonl \
  --batch-id review_smoke_$(date -u +%Y%m%d) \
  --target-runs 14 \
  --target-windows-min 0 \
  --target-windows-max 0 \
  --seed 1 \
  --mode dry-run \
  --output-dir data/run_manifests/review_smoke_$(date -u +%Y%m%d)
```

Adversarial probes (also safe; they only inspect produced manifests):

```bash
# After a dry-run batch is created, confirm IDs do NOT carry scenario_id substrings.
uv run --directory v1 python - <<'PY'
import json, re, pathlib, sys
mf = pathlib.Path("data/run_manifests").glob("review_smoke_*/scenario_runs.jsonl")
for path in mf:
    for line in path.read_text().splitlines():
        row = json.loads(line)
        for field in ("synthetic_case_id", "sacrificial_report_id", "scenario_run_id"):
            if re.search(r"00[0-9]", row[field]):
                print("LEAK:", field, row[field])
                sys.exit(1)
print("ok")
PY

# Confirm path_type coverage per scenario (will currently FAIL after fix P0-3 lands;
# today it will report only one path_type per scenario).
uv run --directory v1 python - <<'PY'
import json, pathlib, collections
mf = next(pathlib.Path("data/run_manifests").glob("review_smoke_*/scenario_runs.jsonl"))
by_scn = collections.defaultdict(set)
for line in mf.read_text().splitlines():
    row = json.loads(line)
    by_scn[row["scenario_id"]].add(row["path_type"])
for scn, types in sorted(by_scn.items()):
    print(scn, sorted(types))
PY
```

### Live / Splunk-gated (do NOT run unprompted in this review session)

These touch the lab. Only run with the user's explicit go-ahead, after confirming the configured endpoint is the authorized lab and not a production deployment. They are listed for completeness; this review did not execute them.

```bash
# Readiness — must pass before any reset or capture
uv run --directory v1 python scripts/check_splunk_readiness_v1.py \
  --config splunk/private/lab.toml \
  --output reports/runs/readiness-<batch_id>.md

# Reset (per scenario) — refuses outside the sacrificial allowlist
uv run --directory v1 python scripts/reset_lab_v1.py \
  --config splunk/private/lab.toml \
  --scenario scenario_004 \
  --reset-id reset_<id>

# Verify reset — fails closed if residue is present
uv run --directory v1 python scripts/verify_reset_v1.py \
  --config splunk/private/lab.toml \
  --reset-id reset_<id> \
  --output reports/runs/reset-<reset_id>.md

# Capture — requires a successful reset
uv run --directory v1 python scripts/capture_splunk_run_v1.py \
  --config splunk/private/lab.toml \
  --scenario-run-id scenario_004_run_<id> \
  --reset-id reset_<id> \
  --output-dir data/raw_exports/<batch_id>/scenario_004_run_<id>

# Pytest with live markers (avoid running with -k 'splunk' if the lab is unavailable)
uv run --directory v1 pytest tests/test_splunk_io_v1.py tests/test_splunk_readiness_v1.py
uv run --directory v1 pytest tests/test_capture_splunk_run_v1.py
uv run --directory v1 pytest tests/test_seed_splunk_scenario_evidence_v1.py
uv run --directory v1 pytest tests/test_reset_lab_v1.py
uv run --directory v1 pytest tests/test_materialize_prompt_pack_runs_v1.py
```

**Needs verification:** which of those test files actually contact Splunk vs. mock it. Several may be safe-local. Until that's confirmed, treat all `test_*splunk*`, `test_capture_*`, `test_reset_*`, `test_seed_*`, `test_materialize_prompt_pack_*` as live-gated by default.

### Full validation sweep (live-required; covers all gates from the plan)

```bash
uv run --directory v1 python scripts/public_safety_scan_v1.py \
  data/raw_exports data/run_manifests data/public_sample docs schemas scenarios \
  reports/goal_runs reports/artifact-cleanup-<date>

uv run --directory v1 python scripts/validate_dataset_v1.py \
  --schemas schemas \
  --sample data/public_sample \
  --check all

uv run --directory v1 pytest
```

---

## 7. Claim boundaries / public-safety cautions

These are constraints the V1 work has already chosen and must be preserved as the harness expands:

1. **"Tamper-congruent" / "needs review" / "synthetic positive" wording is mandatory.** Any external report or model card that talks about V1 must not claim "we detect malicious behavior," "we identify intent," or "we evaluate Splunk security." The spec is explicit on this (`docs/v1-dataset-spec.md:7, 257-266`); the generator and tests should fail loud if a row's free-text fields adopt stronger language.
2. **Pseudonymous IDs must be content-free.** The current `synthetic_case_id` / `sacrificial_report_id` / `scenario_run_id` violate this (Section 2.F3). Until P0-1 lands, treat any committed manifest as carrying answer keys — i.e. do not publish run manifests, do not screenshot them in marketing, do not pass them to external review without redaction.
3. **Dry-run actor prompts in `data/run_manifests/<batch_id>/actor_prompts/` carry the same answer-key risk** because they include `path_type`, `path_template_id`, `actor_profile`, `evidence_order`, `conflict_intensity`, and `distractor_count` (Section 2.F9, `generate_training_batch_v1.py:131-145`). They look like prompts, but their metadata block is the label sheet.
4. **Do not present per-scenario accuracy as "V1 model performance."** With the current one-template-per-scenario topology, any model can hit ceiling accuracy by memorizing `scenario_id`. Per-split positive/negative counts and per-`path_type` AUC are the *only* metrics that should appear next to any headline number; the spec already says this (`docs/v1-dataset-spec.md:343-344, 373-374`).
5. **Do not run the live-Splunk scripts against a production endpoint.** `check_splunk_readiness_v1.py` is the gate, but a user can bypass it by editing the config. The readiness check should be re-run before *every* reset and *every* capture, not once per session.
6. **The `--force` flag on the training-batch generator is genuinely destructive** within `data/run_manifests/`. Treat it like `rm -rf`: confirm `--batch-id` is correct, confirm there is no other batch under the same path, and ideally `cp -r` the target to a quarantine directory before re-running.
7. **The "few thousand rows" framing is dangerous.** Row count is a marketing-grade number; until F1–F4 are fixed, every row past ~14 (one per scenario) adds variance to the modular pattern, not signal. Do not allow row count to substitute for `path_type` / actor / evidence-order / conflict / object-family coverage measurements in any V1 public statement.
8. **Cross-repo (v0 vs. v1) labeling drift is a public-safety risk.** V0 work used different label families and a different harness. Joining v0 and v1 corpora — even for an internal demo — without an explicit relabeling pass risks publishing rows whose label semantics no longer match the spec.
9. **The reset / verify / capture / normalize chain is the only path through which a V1 row can claim live-lab provenance.** Rows minted by `generate_training_batch_v1.py` in dry-run cannot legitimately claim `live-run-derived` in the public sample manifest (`docs/v1-dataset-spec.md:672-675`). If the build script ever marks them as such, that is a claim-boundary violation, not a bug in a test.
10. **The nondeterminism story is not yet ready to be a public talking point.** The "Live nondeterminism evidence artifact" commit (`e9b391b feat: add live nondeterminism evidence artifact`) is recent, and the existing nondeterminism harness (`optimize_nondeterminism_goal_v1.py`, `analyze_nondeterminism_goal_v1.py`, `v1/config/nondeterminism_goal_defaults.yaml`) is separate from the training-batch generator. Until P1-6 binds them, any external claim of "we deliberately introduce nondeterminism across all scenarios" is unsupported by code path — the variation axes I read are deterministic modular arithmetic.

---

## Appendix A — Variation-axis collinearity sketch (worked example)

Take `target_runs = 42`, `seed = 260526` (the test's parameters). Because `260526 mod 4 = 2`:

- `actor_profile_index(run_index) = (run_index + 2) mod 4`.
- `distractor_count_index(run_index) = (run_index + 2) mod 4`. (Same expression — `distractor_count` is collinear with `actor_profile`, not just collinear with `scenario_id`.)

For `scenario_004` (run_index ∈ {1, 15, 29}):
- run 1: actor_profile_index = 3 → `automation_helper`; distractor_count_index = 3 → `3`.
- run 15: actor_profile_index = (15+2) mod 4 = 1 → `rushed_operator`; distractor_count_index = 1 → `1`.
- run 29: actor_profile_index = (29+2) mod 4 = 3 → `automation_helper`; distractor_count_index = 3 → `3`.

For `scenario_006` (run_index ∈ {2, 16, 30}):
- run 2: actor_profile_index = 0 → `cautious_analyst`; distractor_count_index = 0 → `0`.
- run 16: actor_profile_index = 2 → `skeptical_reviewer`; distractor_count_index = 2 → `2`.
- run 30: actor_profile_index = 0 → `cautious_analyst`; distractor_count_index = 0 → `0`.

So `actor_profile ∈ {cautious_analyst, skeptical_reviewer}` ⇔ scenario_id is even; `actor_profile ∈ {rushed_operator, automation_helper}` ⇔ scenario_id is odd. **`actor_profile` is a 1-bit oracle for `scenario_id mod 2`**, and because `distractor_count` uses the same index expression, the two axes are perfectly collinear *and* both leak the same bit of the label.

The test (`test_training_batch_generation_v1.py:68`) checks only that `len({row["actor_profile"] for row in rows}) > 1`. All four `actor_profile` values appear in the 42-row test sample, so the test passes. The leakage is invisible to it.

## Appendix B — Findings index

| ID  | Title                                                      | Severity | Primary file |
|-----|------------------------------------------------------------|----------|--------------|
| F1  | `scenario_id` is the label (bijective leakage)             | P0       | `v1/scenarios/path_templates_v1.jsonl`, `generate_training_batch_v1.py:109` |
| F2  | Modular-arithmetic axes create stratified partitions       | P0       | `generate_training_batch_v1.py:111-114` |
| F3  | Public IDs literally contain scenario_id                   | P0       | `generate_training_batch_v1.py:115-117` |
| F4  | `ground_truth_family` written into the manifest            | P0       | `generate_training_batch_v1.py:154-156` |
| F5  | `--target-windows-min/max` are vestigial                   | P1       | `generate_training_batch_v1.py:27-29, 71-73, 182-183` |
| F6  | Round-robin scheduling guarantees exact balance            | P1       | `generate_training_batch_v1.py:101` |
| F7  | `scenario_run_id` does not include `batch_id`              | P0       | `generate_training_batch_v1.py:115` |
| F8  | `--force` calls `shutil.rmtree` with no confirmation       | P2       | `generate_training_batch_v1.py:78-80` |
| F9  | Dry-run prompts carry answer-key metadata                  | P1       | `generate_training_batch_v1.py:131-145` |
| F10 | Round-robin alignment of prompt/template/object axes       | P1       | `generate_training_batch_v1.py:107-110` |
| F11 | Test asserts distinct counts, not independence             | P1       | `test_training_batch_generation_v1.py:68-70` |
| F12 | Public-safety scan likely shows false-green on dry-run     | needs verify | `public_safety_scan_v1.py` |
| F13 | Split / relationship integrity tests are very small        | needs verify | `test_split_integrity_v1.py`, `test_relationship_integrity_v1.py` |
| F14 | Feature column allowlist may not be enforced               | needs verify | `derive_windows_v1.py`, `behavior_window_v1.schema.json` |
| G1  | One path template per scenario                             | P0       | `path_templates_v1.jsonl` |
| G2  | All templates share identical `expected_action_sequence`   | P1       | `path_templates_v1.jsonl` |
| G3  | `tool_budget`, `outcome_target` declared but unused        | P1       | `generate_training_batch_v1.py` |
| G4  | No multi-actor or retry trajectories                       | P2       | catalog + path templates |
| G5  | No noise/decoy/timing-jitter scenarios                     | P2       | catalog + path templates |
| G6  | Prompt content variation unverified                        | needs verify | `test_ready_eval_prompt_variation_v1.py` |
| G7  | Training-batch manifests carry no `reset_id`               | P1       | `generate_training_batch_v1.py:147-173` |
| G8  | `paired_control_scenario_ids` not propagated to runs       | P1       | `generate_training_batch_v1.py:147-173` |
| G9  | Nondeterminism budget decoupled from generator             | P1       | `optimize_nondeterminism_goal_v1.py`, `generate_training_batch_v1.py` |

End of review.
