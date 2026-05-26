# Live probe status — small k=3 harness smoke

- Batch: `small_k3_harness_smoke_20260526T174111Z`
- Checked during the k=3 smoke execution window
- Intended representative live row: `scenario_010` / `run_14d6d7ddddeaf764`
- Result: **blocked before live Splunk write/read-back**

## What passed before the live gate

- The k=3 dry-run manifest generated `42` rows across `14` scenarios.
- Every scenario has exactly `3` attempts.
- Every generated row has a corresponding actor prompt file.
- Each scenario varied on at least two declared nondeterminism axes.
- The representative live probe reset manifest was written for the public-safe `scenario_010` row.

## Live blockers

1. Splunk HEC write was blocked because the required environment variable `AI_TAMPERGUARD_SPLUNK_HEC_TOKEN` is not set in the execution environment.
2. Splunk MCP read-back was also unavailable: the configured `MCP_SPLUNK_MCP_SERVER_API_KEY` was rejected by Splunk MCP authentication as invalid or expired.
3. The private lab config currently has a HEC table but no Splunk search table, so the project-native capture script cannot perform direct REST read-back without either MCP access or a configured public-safe search token env.

No credential values, private endpoints, raw SPL, or private artifact names are included in this report.

## Harness drift found and fixed

The generated batch uses opaque `run_<id>` scenario run IDs, while the live seed/capture scripts previously assumed `scenario_<id>...`-prefixed run IDs. The live attempt exposed this mismatch before the credential gate. The scripts now accept opaque generated run IDs when the explicit scenario/reset metadata identifies the scenario, while still rejecting mismatched `scenario_*` run IDs.

## Next live retry requirements

Before retrying the live probe:

- Set a valid `AI_TAMPERGUARD_SPLUNK_HEC_TOKEN` for the authorized local lab, or provide an equivalent safe write path.
- Refresh `MCP_SPLUNK_MCP_SERVER_API_KEY` or add a `splunk_search` config backed by a public-safe search token env.
- Re-run the same representative row first, then capture with `--require-live-splunk-rows` before scaling beyond one row.
