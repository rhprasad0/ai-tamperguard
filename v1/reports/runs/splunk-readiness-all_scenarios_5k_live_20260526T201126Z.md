# Splunk readiness passed

- Authorized lab marker: `ai_tamperguard_v1_authorized_local_lab`
- Target namespace: `ai_tamperguard_v1`
- Capture destination: `data/raw_exports`

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
- `object_000001`: report, scenarios=scenario_001
- `object_000002`: saved_search, scenarios=scenario_002
- `object_000003`: dashboard, scenarios=scenario_003
- `object_000005`: report, scenarios=scenario_005
- `object_000008`: report, scenarios=scenario_008
- `object_000009`: report, scenarios=scenario_009
- `object_000016`: report, scenarios=scenario_016
- `object_000019`: alert, scenarios=scenario_019
- `object_000020`: role, scenarios=scenario_020
- `object_000021`: index, scenarios=scenario_021
- `object_000022`: config, scenarios=scenario_022
- `object_000023`: dashboard, scenarios=scenario_023
- `object_000024`: saved_search, scenarios=scenario_024
- `object_000025`: lookup, scenarios=scenario_025
- `object_000026`: report, scenarios=scenario_026
- `object_000027`: alert, scenarios=scenario_027
- `object_000028`: report, scenarios=scenario_028

Readiness is public-safe: private artifact names and raw SPL are intentionally omitted from this report.
