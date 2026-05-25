# Splunk readiness passed

- Authorized lab marker: `ai_tamperguard_v1_authorized_local_lab`
- Target namespace: `ai_tamperguard_v1`
- Capture destination: `data/private/raw_exports`

## Required observed indexes

- `_audit`: present, disabled=0, totalEventCount=45933
- `_configtracker`: present, disabled=0, totalEventCount=902
- `openclaw_tamper_lab`: present, disabled=0, totalEventCount=648

## Optional observed indexes

- `agentops`: present

## Sacrificial inventory

- Namespace: `ai_tamperguard_v1`
- Synthetic index: `openclaw_tamper_lab`
- `object_000010`: dashboard, scenarios=scenario_004, scenario_010
- `object_000901`: report, scenarios=scenario_004
- `object_000007`: role, scenarios=scenario_007
- `object_000902`: saved_search, scenarios=scenario_007
- `object_000006`: report, scenarios=scenario_006
- `object_000906`: dashboard, scenarios=scenario_006
- `object_000012`: alert, scenarios=scenario_012
- `object_000013`: alert, scenarios=scenario_013
- `object_000904`: report, scenarios=scenario_013
- `object_000011`: saved_search, scenarios=scenario_011
- `object_000014`: alert, scenarios=scenario_014
- `object_000015`: saved_search, scenarios=scenario_015
- `object_000017`: macro, scenarios=scenario_017
- `object_000018`: macro, scenarios=scenario_018

Readiness is public-safe: private artifact names and raw SPL are intentionally omitted from this report.
