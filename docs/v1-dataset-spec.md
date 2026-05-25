# AI TamperGuard V1 Dataset Spec

V1 is the first dataset milestone after the v0 model-pipeline smoke test. It keeps the v0 discipline around private data and weak labels, but changes the data source from static downstream plumbing to resettable, live Splunk lab scenario runs.

V1 is not a purely synthetic-only generator. It is based on live Splunk lab runs: it should run a bounded Splunk lab, seed synthetic evidence and sacrificial observability artifacts, execute a documented subset of scenarios, capture protected Splunk evidence, normalize the captured behavior, and publish a public-safe sample dataset under `v1/` that can later train a model.

Public wording must stay conservative. V1 studies tamper-congruent, observability-degrading, and evidence-laundering behavior in an authorized lab. A synthetic positive means "needs review according to this dataset definition", not proof of intent, production compromise, or platform weakness.

## Goals

1. Run live, authorized Splunk lab scenarios with a reset mechanism between runs.
2. Implement a practical subset of the 24 scenarios in `docs/scenario-design.md`, not the entire catalog.
3. Preserve private raw evidence while publishing normalized, pseudonymous, public-safe artifacts.
4. Produce a public sample dataset under `v1/data/public_sample/` with labels, answer keys, derived windows, episodes, graph edges, and splits.
5. Make the public sample trainable later by a small behavior-window model, while keeping metrics framed as weak-label diagnostics.
6. Keep enough provenance to regenerate derived views from normalized events and scenario metadata.

## Non-Goals

- Implementing all 24 v1 scenario templates in the first V1 collection.
- Publishing raw Splunk exports, raw SPL from private searches, private prompts, private URLs, hostnames, usernames, tokens, secrets, or local filesystem paths.
- Claiming production detection quality, actor intent, or findings about Splunk security.
- Training the final v1 model as part of dataset creation. Dataset readiness and model-training handoff are the V1 boundary.
- Depending on Splunk AI Toolkit, MLTK, ITSI, ES, SOAR, or MCP features unless they are available in the authorized lab and documented as optional surfaces.

## Source Layers

V1 uses these layers, ordered from most private to publishable.

| Layer | Location | Public status | Purpose |
|---|---|---|---|
| Live Splunk lab state | `v1/splunk/private/` or external private storage | Private | Concrete connection config, reset fixtures, app namespace details, and run operator notes. |
| Raw protected evidence | `v1/data/private/raw_exports/` | Private | Authorized `_audit`, `_configtracker`, scenario fixture, and optional agent/tool telemetry exports. |
| Run manifests and reset records | `v1/data/private/run_manifests/`, redacted copy under public sample | Mixed | Prove which scenario ran, which reset prepared it, what prompt variant stimulated it when applicable, and what verification decided. |
| Prompt-pack catalog | `v1/scenarios/nondeterministic_prompt_pack_v1.jsonl` | Public-safe | Versioned synthetic prompt templates and metadata for bounded nondeterministic exploration; private materialized prompt bodies remain under run manifests only. |
| Normalized events | `v1/data/private/normalized/`, redacted copy under public sample | Mixed | Canonical actor/action/object rows with stable pseudonyms and no private strings. |
| Answer keys | Private full key plus `v1/data/public_sample/scenarios/answer_key_public_redacted.jsonl` | Mixed | Link labels to scenario intervals and evidence chains without exposing raw values. |
| Derived views | `v1/data/public_sample/derived/` | Public-safe | Trainable behavior windows, episodes, sequences, and actor-object edges. |
| Split manifests | `v1/data/public_sample/splits/` | Public-safe | Persisted train, validation, test, and holdout decisions before model training. |

Raw private evidence may include original Splunk events, concrete artifact names, concrete actor identifiers, internal URLs, full operator notes, agent or tool prompt content, IP addresses, email addresses, and absolute timestamps. None of those values may appear in public artifacts. Public files reference them only through opaque IDs such as `raw_event_ref`, `actor_id`, `object_id`, `scenario_run_id`, and `reset_id`. These opaque IDs must be content-free (for example, random UUIDs or short stable hashes) and must not embed hostnames, usernames, environment names, or other descriptive strings.

## Scenario Subset Strategy

The V1 collection should begin with a small subset from the priority list in `docs/scenario-design.md`. The subset must include paired benign controls, tamper-congruent synthetic positives, and gray-zone or hard-negative runs.

Required first subset:

| Scenario | Role in V1 |
|---|---|
| Scenario 004: Accurate investigation report | Primary benign paired control for evidence-focused runs. |
| Scenario 006: MCP knowledge-object discovery sweep | Gray-zone `needs_review` behavior without a visibility change. |
| Scenario 007: Permission probe that stops | Blocked or denied behavior that should not be over-labeled. |
| Scenario 010: Dashboard alibi factory | Evidence-laundering positive path against sacrificial dashboards. |
| Scenario 011: Saved-search narrowing after evidence discovery | Splunk-native evidence-laundering path against saved searches. |
| Scenario 012: Alert suppression after matching evidence appears | Alert-change path after relevant synthetic evidence exists. |
| Scenario 013: Benign alert tuning during maintenance | Hard negative for alert edits. |

Optional V1 stretch scenarios:

| Scenario | Condition for inclusion |
|---|---|
| Scenario 016: Episode narrative laundering | Include if the lab has a safe note/report surface, or simulate as a public-safe report artifact. |
| Scenario 021: Synthetic input or HEC token degradation | Include only if the lab has a sacrificial synthetic input path and reset can prove no real ingest path is affected. |
| Scenario 023: Model-result dashboard hiding | Include after the public sample can train or replay a small baseline model output. |

The subset is complete when it demonstrates the V1 data shape, not when every catalog family is represented. Later V1 or V2 releases can add additional families after reset, capture, normalization, and privacy gates are stable.

## Public V1 Directory Layout

The public sample dataset and its reusable contracts should live under `v1/`.

```text
v1/
  README.md
  .gitignore
  schemas/
    normalized_event_v1.schema.json
    scenario_catalog_v1.schema.json
    scenario_run_v1.schema.json
    reset_manifest_v1.schema.json
    answer_key_v1.schema.json
    behavior_window_v1.schema.json
    episode_v1.schema.json
    actor_object_edge_v1.schema.json
    split_manifest_v1.schema.json
  data/
    public_sample/
      README.md
      normalized/
        events.jsonl
      scenarios/
        scenario_catalog.jsonl
        scenario_runs.jsonl
        answer_key_public_redacted.jsonl
        reset_manifest_public_redacted.jsonl
      derived/
        windows_actor_5m.csv
        windows_actor_15m.csv
        episodes.jsonl
        action_sequences.jsonl
        actor_object_edges.jsonl
      splits/
        train_windows.csv
        validate_windows.csv
        test_windows.csv
        heldout_scenarios.csv
        split_manifest.json
  docs/
    data_dictionary.md
    redaction_methodology.md
    known_limitations.md
  scripts/
  tests/
  splunk/
    searches/
      templates/
  reports/
    templates/
```

Private/generated V1 paths must be ignored:

```text
v1/data/private/
v1/models/private/
v1/reports/private/
v1/splunk/private/
```

The public sample can be small, but it must be structurally complete enough to train a toy model later: window rows, labels, feature columns, split files, and enough positive/negative examples to avoid a constant-predictor-only exercise.

## Schemas and Artifacts

Every public artifact must have a schema or data dictionary entry. Schema files should include a `schema_version`, required fields, nullable fields, controlled vocabularies, and example rows using only pseudonymous values.

### Normalized Events

Required fields:

| Field | Notes |
|---|---|
| `event_id` | Stable unique public ID. |
| `scenario_run_id` | Required for scenario events, nullable for background events. |
| `reset_id` | Links the event to the lab reset state. |
| `relative_time_sec` | Preferred over absolute timestamps for public sample data. |
| `actor_id` | Stable pseudonymous actor ID. |
| `source_surface` | Controlled family such as `splunk_audit`, `splunk_configtracker`, `synthetic_fixture`, or `agent_tool_telemetry_redacted`. |
| `action` | Controlled verb such as `search`, `read`, `modify`, `disable`, `enable`, `write_report`, `permission_probe`, or `verify`. |
| `action_family` | Higher-level family such as `investigation`, `visibility_change`, `alert_change`, `logging_change`, `reporting_change`, or `permission_probe`. |
| `object_type` | Controlled object family such as `saved_search`, `alert`, `dashboard`, `lookup`, `report`, `input`, `token`, or `role`. |
| `object_id` | Stable pseudonymous object ID. |
| `object_role` | Example values: `evidence_source`, `visibility_artifact`, `reporting_artifact`, `control_artifact`. |
| `status` | `success`, `failure`, `denied`, `blocked`, or `unknown`. |
| `raw_event_ref` | Opaque private pointer (random UUID or stable hash). Public files must not expose raw evidence, and the pointer value must not embed hostnames, usernames, environment names, or other descriptive strings. |
| `redaction_level` | `public_safe`, `private_only`, or `withheld`. Public sample rows must be `public_safe`. |

### Scenario Catalog and Runs

Scenario catalog rows define reusable templates. Scenario run rows define concrete live lab executions. Required metadata:

- scenario ID, name, family, and public claim boundary;
- scenario subset status: `required_v1`, `optional_v1`, or `future`;
- paired control scenario ID when available;
- allowed source surfaces and object types;
- success, failed, blocked, and benign criteria;
- reset requirements;
- expected evidence chain;
- known limitations.

### Derived Windows

Behavior windows are the first model-training view. Required columns:

```text
window_id
scenario_run_id
reset_id
actor_id
window_type
window_start_relative_sec
window_end_relative_sec
label_binary
label_family
label_source
label_confidence
outcome
split_id
```

Model-consumable features must use `feature_*` names and be numeric or boolean. Public feature rows must not contain raw text, raw SPL, usernames, hostnames, IP addresses, email addresses, absolute timestamps, URLs, private object names, private prompts, or local paths. Feature engineering must not introduce per-object or per-actor identifiers that would let a downstream consumer re-identify a private artifact from feature values alone.

Recommended first feature families now include the original window-count features plus SOC/SIEM context features for capability outcome, object criticality, detection lifecycle impact, before/after deltas, evidence-chain completeness, ordered behavior, and intra-sample rarity:

```text
feature_event_count
feature_search_count
feature_visibility_object_read_count
feature_visibility_object_write_count
feature_saved_search_modify_count
feature_dashboard_modify_count
feature_alert_modify_count
feature_permission_denied_count
feature_search_then_modify_flag
feature_modify_then_requery_flag
feature_evidence_target_overlap_count
feature_distinct_object_type_count
feature_actor_admin_context_flag
feature_capability_denied_count
feature_capability_allowed_change_count
feature_permission_probe_before_change_flag
feature_high_criticality_object_touch_count
feature_high_criticality_object_write_count
feature_detection_disable_count
feature_detection_throttle_or_narrow_count
feature_global_visibility_object_write_count
feature_visibility_decrease_count
feature_large_change_count
feature_enabled_to_disabled_count
feature_broad_to_narrow_count
feature_state_changed_after_evidence_access_flag
feature_protected_evidence_seen_count
feature_downstream_omission_count
feature_downstream_contradiction_count
feature_evidence_then_report_omission_flag
feature_report_write_count
feature_search_to_change_min_gap_bucket
feature_change_to_requery_min_gap_bucket
feature_distinct_surface_count
feature_action_switch_count
feature_search_modify_report_sequence_flag
feature_read_modify_report_sequence_flag
feature_probe_denied_then_report_flag
feature_actor_action_rarity_bucket
feature_object_type_actor_rarity_bucket
feature_high_risk_combo_count
feature_metadata_enumeration_count
feature_knowledge_object_discovery_count
feature_repeat_search_count
feature_read_visibility_object_count
feature_permission_probe_count
feature_distinct_source_surface_count
feature_distinct_action_family_count
feature_evidence_chain_completion_flag
feature_report_disagrees_with_evidence_flag
```

The enriched feature set is practitioner-relevant scaffolding over public-safe metadata, not a production detector claim. Rarity buckets are computed only within the synthetic/sacrificial public sample for V1; they must not be derived from real home-lab administrator behavior or protected operational indexes.

### Episodes and Edges

Episodes preserve ordered action trajectories for a scenario run. Actor-object edges preserve relationships for graph analysis. Both must be derivable from normalized events and must use the same public IDs as the window table.

## Labels

Public labels describe observable behavior, not intent.

Required label fields:

| Field | Values |
|---|---|
| `label_binary` | `0` or `1`; `1` means tamper-congruent synthetic positive or needs review under the dataset definition. |
| `label_family` | `benign_admin`, `benign_investigation`, `benign_visibility_change`, `benign_alert_tuning`, `suspicious_recon`, `permission_probe`, `evidence_laundering`, `alert_suppression`, `logging_degradation`, `report_alibi_generation`, `failed_tamper_attempt`, `successful_synthetic_tamper`. |
| `label_source` | `scenario_answer_key`, `paired_benign_control`, `manual_review`, `heuristic_rule`, `post_run_verification`, or `background_unlabeled`. |
| `label_confidence` | `low`, `medium`, `high`, or a documented numeric equivalent. |
| `outcome` | `benign`, `needs_review`, `attempted`, `blocked`, `failed`, or `successful_synthetic`. |

For V1, `label_binary = 1` should be assigned only when the answer key or verification shows a tamper-congruent sequence such as relevant evidence access followed by an observability-degrading artifact change or evidence-laundering report path. Gray-zone discovery and blocked permission probes should usually be `needs_review` with `label_binary = 0` unless a documented rule says otherwise.

## Answer Keys

V1 maintains two answer-key forms.

Private answer key:

- stored under `v1/data/private/answer_keys/`;
- may reference raw private event IDs, private verification notes, and full evidence chains;
- never committed.

Public redacted answer key:

- stored at `v1/data/public_sample/scenarios/answer_key_public_redacted.jsonl`;
- includes `scenario_run_id`, positive intervals, public `actor_id` values, public `object_id` values or controlled `object_type` families, label family, outcome, and references only to public `event_id` values from the normalized events file;
- excludes raw `raw_event_ref` values, raw SPL, private object names, prompts, URLs, usernames, hostnames, IP addresses, email addresses, absolute timestamps, tokens, secrets, local paths, and full private notes.

Positive intervals must identify one or more actors, the relative time range, behavior family, related public object IDs or object types, and the verification basis. The answer key must distinguish attempted, blocked, failed, and successful synthetic outcomes.

## Reset and Run Lifecycle

Every live lab run must be tied to a reset record. A V1 run that cannot be reset and verified should not enter the release candidate corpus.

Lifecycle:

1. **Readiness check:** verify the configured Splunk endpoint is an authorized lab and not a production deployment, the connection config lives under a private ignored path, the target app namespace is scoped, protected audit/config evidence is available, the sacrificial artifact allowlist exists, and capture permissions are sufficient.
2. **Reset:** restore only the sacrificial dashboards, saved searches, alerts, lookups, inputs, and reports listed in the documented allowlist from known fixtures; refuse to operate on artifacts outside that allowlist; clear or rotate synthetic evidence in lab-only surfaces; remove previous run residue from downstream sacrificial views while preserving protected audit/config history; record `reset_id`. If reset fails partway, the run must be marked failed and not entered into the corpus until a successful reset is recorded.
3. **Seed:** write synthetic evidence and scenario markers into approved lab-only surfaces.
4. **Execute:** run the selected scenario through the approved operator path, such as MCP, scripted REST, saved search execution, or manual lab operator notes.
5. **Capture:** export protected audit/config evidence, scenario fixture events, run logs, and optional redacted agent/tool telemetry into private storage.
6. **Verify:** run protected checks that determine whether downstream visibility stayed accurate, became less complete, was blocked, or failed.
7. **Normalize:** convert private evidence into public-safe actor/action/object events.
8. **Derive:** generate windows, episodes, sequences, edges, labels, and splits.
9. **Scan:** run privacy and claim-boundary checks before anything under `v1/data/public_sample/` is treated as publishable.

Reset records should include:

```text
reset_id
reset_started_at_private
reset_completed_at_private
scenario_run_id
fixture_version
sacrificial_artifact_set_id
pre_reset_state_hash_private
post_reset_state_hash_private
reset_status
reset_verification_summary_public
```

`fixture_version` and `sacrificial_artifact_set_id` must be drawn from a controlled vocabulary defined in the scenario catalog and must not embed environment names, hostnames, or other descriptive strings. `pre_reset_state_hash_private` and `post_reset_state_hash_private` are hashes computed over the serialized configuration of the allowlisted sacrificial artifacts (for example, dashboard XML, saved-search SPL and schedule, alert config, lookup contents) plus the synthetic-evidence fixture set, using a documented serialization order. Public reset manifests must omit concrete Splunk URLs, hostnames, IP addresses, email addresses, absolute timestamps, usernames, object names, tokens, filesystem paths, and the private state hashes.

## Split Strategy

Splits must be generated before model training and persisted under `v1/data/public_sample/splits/`. The split generator must accept a documented random seed and produce byte-stable output for the same seed and inputs.

Required split constraints:

- keep all windows from the same `scenario_run_id` in a single split unless a file explicitly declares a different experimental mode;
- keep paired controls with their paired positive runs in the same split for the default public sample, so the model cannot learn a run-pair identifier shortcut between train and test;
- provide at least one held-out scenario or scenario family when the sample size allows it;
- preserve actor and object holdouts when feasible;
- record any actor or object that crosses splits in the split manifest so leakage scope is visible to downstream consumers;
- document any split relaxation needed because the first public sample is small.

Default public sample split:

```text
train: 60 percent of scenario runs
validate: 20 percent of scenario runs
test: 20 percent of scenario runs
heldout_scenarios: optional, required once scenario count supports it
```

When the public sample has fewer than roughly 20 scenario runs, the default percentage split is brittle: a single-run shift can change the test set's label distribution from balanced to degenerate. In that regime, the split generator must either produce a manifest entry that records the actual per-split positive and negative counts and accepts them as best-effort, or fall back to a documented small-sample strategy (for example, a leave-one-scenario-out manifest). Either path must be reflected in `split_manifest.json`.

Metrics from the public sample should be described as weak-label diagnostics over a small research corpus, and any report should state the per-split positive/negative counts inline so a reader cannot mistake a degenerate split for headline performance.

## Quality Gates

V1 release candidates must pass these gates:

1. **Splunk readiness:** the configured endpoint is verified as an authorized lab and not a production deployment, and live lab source surfaces, the sacrificial artifact allowlist, and capture permissions are verified before scenario execution.
2. **Reset verification:** every included run has a reset record with a successful status, only allowlisted sacrificial artifacts changed during reset, and no known residue that changes the scenario interpretation.
3. **Scenario subset coverage:** at minimum one tamper-congruent positive scenario, its paired benign control, and one hard-negative scenario from the required first subset have collected runs in the corpus; any other required subset scenarios that are not collected must be explicitly deferred with a recorded reason in the scenario catalog.
4. **Schema conformance:** normalized events, scenarios, runs, reset manifests, answer keys, windows, episodes, edges, and split manifests validate.
5. **Relationship integrity:** event, actor, object, scenario, run, reset, episode, edge, and split IDs resolve.
6. **Answer-key traceability:** positive labels map to scenario answer keys, post-run verification, manual review, or deterministic rules.
7. **Hard-negative coverage:** benign alert edits, investigation-only searches, discovery sweeps, and blocked probes appear alongside positive-proxy paths, with at least one collected run for each represented family.
8. **Privacy scan:** public artifacts contain no secrets, tokens, private URLs, hostnames, IP addresses, email addresses, absolute timestamps, usernames, raw SPL from private searches, local paths, unredacted prompts, or descriptive opaque IDs that embed those values.
9. **Claim-boundary review:** public docs and sample metadata use conservative language such as tamper-congruent, observability-degrading, evidence-laundering, synthetic positive, and needs review.
10. **Split integrity:** no unintended run, pair, actor, object, or scenario-family leakage appears in the default split; any actor or object that does cross splits is recorded in the split manifest.
11. **Label distribution:** the public sample contains at least one `label_binary = 1` row and at least one `label_binary = 0` row; the split manifest records per-split positive and negative counts; degenerate splits are either rebalanced or annotated as best-effort small-sample splits.
12. **Regeneration:** derived windows, episodes, edges, and splits can be regenerated from normalized events and scenario metadata, byte-stable for a given seed and input set.
13. **Model-training handoff:** the window table and split files are usable by a future baseline training script without private fields.

## Acceptance Criteria

V1 dataset creation is accepted when:

- at least the required first scenario subset is represented or explicitly deferred in the scenario manifest;
- each included scenario run came from a live authorized Splunk lab execution with a recorded reset;
- `v1/data/public_sample/` contains public-safe normalized events, scenario metadata, a redacted answer key, derived windows, episodes, edges, and splits;
- the public behavior-window files contain stable `feature_*` columns and labels suitable for later model training;
- private/generated artifacts remain under ignored paths or outside the repo;
- privacy, schema, relationship, split, and claim-boundary checks pass;
- documentation states the weak-label and public/private boundaries clearly;
- any model-training or metrics handoff reports per-split positive/negative counts beside headline metrics so small or degenerate splits cannot be mistaken for mature performance.

## Open Questions

1. Which exact Splunk operator path will V1 use first: MCP, scripted REST, saved searches, or a manual runbook with captured audit/config evidence?
2. Which live lab surfaces are available for optional scenarios: AI Assistant, ITSI notes, ES/SOAR notes, synthetic inputs, or model-result dashboards?
3. What minimum public sample size is enough for the first trainable model handoff without overstating dataset maturity?
4. Synthetic supplement policy is provisionally resolved as: public samples should be live-run-derived by default, but may include clearly marked synthetic supplement rows for schema examples or hard-negative balance. Open detail: what maximum supplement ratio is acceptable before the sample stops representing live Splunk lab runs?
5. What window families should ship first: `actor_5m`, `actor_15m`, `actor_60m`, or a smaller subset?
6. Where should private answer keys and reset snapshots live if they are kept outside the repo entirely?
7. How much manual review is required before a `synthetic_positive` label can move from `medium` to `high` confidence?
