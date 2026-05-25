# AI TamperGuard V1 other-ready k=3 nondeterminism goal summary

Run id: `live_goal_other_ready_20260525T221248Z`

## Phase status

ACCEPTED — focused live repeated-call evidence over ready scenario groups beyond `scenario_006` reached `18/18` nondeterministic groups (`1.0000`), with scenario rate `9/9` (`1.0000`).

## Scope

- Mode: live Splunk MCP read-back + `capture_splunk_run_v1.py --verified-live-rows-jsonl`
- k: 3 attempts per scenario/prompt-variant group
- Scenario scope: `scenario_004`, `scenario_007`, `scenario_010`, `scenario_012`, `scenario_013`, `scenario_014`, `scenario_015`, `scenario_017`, `scenario_018`
- Excluded: `scenario_006` because it was already evaluated in `live_goal_nondet50_20260525T214956Z`
- Openclaw grading: not run
- Remediation: not run

## Evidence boundary

This artifact is live repeated-call evidence for public-safe synthetic rows read back from Splunk. It is not a detector-quality claim, not production behavior evidence, and not a claim that dry-run/projection results were live.

## Artifact pointers

- Machine summary: `goal-summary.json`
- Analyzer acceptance: `analyzer-acceptance.json`
- Public-safe raw export root: `data/raw_exports/live_goal_other_ready_20260525T221248Z`
- Verified Splunk MCP rows: `data/raw_exports/live_goal_other_ready_20260525T221248Z/verified_live_rows_from_splunk_mcp.jsonl`
- Public-safe run manifest: `data/run_manifests/live_goal_other_ready_20260525T221248Z/scenario_runs.jsonl`
- Generated prompt pack: `scenarios/generated/live_goal_other_ready_20260525T221248Z/nondeterministic_prompt_pack_v1.generated.jsonl`
- Candidate config: `scenarios/generated/live_goal_other_ready_20260525T221248Z/candidate-config.json`

## Caveats

- This is a focused ready-scenario probe, not a full detector-quality evaluation.
- Dry-run/projection results were used only for candidate selection and are not counted as live evidence.
- Capture used MCP read-back because direct Splunk search config was absent from `splunk/private/lab.toml`.
