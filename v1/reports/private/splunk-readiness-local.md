# Splunk readiness passed

- Authorized lab marker: `ai_tamperguard_v1_lab`
- Target namespace: `ai_tamperguard_v1`
- Capture destination: `data/private/raw_exports`

## Required observed indexes

- `_audit`: present, disabled=0, totalEventCount=44166
- `_configtracker`: present, disabled=0, totalEventCount=901
- `openclaw_tamper_lab`: present, disabled=0, totalEventCount=25

## Optional observed indexes

- `agentops`: present

## Sacrificial inventory

- Namespace: `ai_tamperguard_v1`
- Synthetic index: `openclaw_tamper_lab`
- `object_000010`: dashboard, scenarios=scenario_010
- `object_000011`: saved_search, scenarios=scenario_011
- `object_000012`: alert, scenarios=scenario_012, scenario_013
- `object_000013`: report, scenarios=scenario_004
- `object_000014`: saved_search, scenarios=scenario_007

Readiness is public-safe: private artifact names and raw SPL are intentionally omitted from this report.
