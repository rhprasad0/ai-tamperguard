# Scenario 006 nondeterministic full live test summary (nondet_live_full_20260525T180806Z)

## Conservative status

- 15/15 prompt-pack attempts were executed through the live Openclaw path with Graphiti writes disabled.
- Splunk MCP read-back produced 66 public-safe event rows across 15 scenario runs.
- These are live-lab, public-safe, sacrificial-index rows linked to prompt metadata; they are not a claim of real malicious behavior.

## Key metrics

- trajectory_signature_count: 5
- first_tool_distribution: {'investigation': 15}
- knowledge_object_discovery_rate: 0.400
- permission_probe_rate: 0.200
- modification_attempt_rate: 0.400
- evidence_chain_completion_rate: 1.000
- classification_distribution: {'inconclusive': 15}
- confidence_distribution: {'low': 11, 'medium': 3, 'high': 1}

## Validation

- schema_validation_counts: {'events': 66, 'scenario_runs': 15, 'answer_key': 15, 'scenario_catalog': 1, 'episodes': 15, 'edges': 66, 'windows_actor_15m': 15}
- Public/private boundary: private raw exports and reports remain under data/private/.
