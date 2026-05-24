# AGENTS.md

AI TamperGuard is an experimental AI/security engineering project.

The high-level goal is to prove a simple end-to-end loop:

```text
Splunk logs
→ behavior-window features
→ local model training
→ model artifact
→ Splunk-side scoring
→ verification that Splunk scoring matches local scoring
```

For now, keep the project focused on the plumbing:

- use authorized local Splunk lab data only
- keep private data and generated artifacts out of the public repo
- start with a small, understandable model before anything fancy
- treat labels as weak working-model proxies, not malicious ground truth
- verify the deployed scoring path instead of just saying “we trained a model”

v0 is not claiming production-ready tamper detection. It is a smoke test for whether the model pipeline can move from local training back into Splunk without silently breaking.
