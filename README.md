# AI TamperGuard

AI TamperGuard is an experimental defensive dataset and detection prototype for identifying when AI agents or automated operators try to weaken monitoring, auditability, or alerting controls inside an authorized Splunk lab.

The goal is to create a Splunk-native benchmark for **monitoring-control-plane tampering**: not just raw logs, but labeled behavior windows that can be used to train, evaluate, and demo tamper detection with Splunk AI Toolkit / MLTK.

## What we are trying to build

This project will produce a synthetic, public-safe dataset with:

- synthetic Splunk control-plane, audit, search, config, and alert-change events
- benign admin activity and detection tuning examples
- suspicious gray-zone behavior that should not automatically be treated as malicious
- malicious tamper scenarios such as disabled alerts, weakened searches, reduced risk scoring, hidden evidence, or degraded telemetry
- windowed feature tables designed for Splunk `fit`, `apply`, and `score` workflows
- sample Splunk searches for training and evaluating baseline models

The intended architecture is:

```text
synthetic Splunk events
→ behavior windows
→ feature_* table rows
→ classifier risk score
→ optional LLM/AI analyst summary for high-risk windows
```

## Why this exists

Existing public security datasets are useful, but they generally focus on endpoint, network, or attack telemetry. AI TamperGuard focuses on a narrower gap: detecting attempts to modify the monitoring and detection layer itself.

The core question is:

> Can we detect when an AI agent is trying to make the security camera blink?

Tiny cyber-noir crab-walk, but make it benchmarkable.

## Design principles

- **Defensive and authorized only**: generated in an isolated lab, not against third-party systems.
- **Synthetic and redacted**: no real customer data, secrets, home telemetry, or private infrastructure details.
- **Splunk-native**: shaped for lookup-based model training and inference with Splunk AI Toolkit / MLTK.
- **Window-first**: models train on behavior windows, not individual raw events.
- **Explainable baseline first**: start with logistic regression / random forest / gradient boosting before heavier models.
- **LLM second, classifier first**: AI summaries should explain flagged evidence, not be the primary detector over raw logs.

## Planned dataset artifacts

```text
data/
  raw_events/
  windows/
    tamperguard_windows_train.csv
    tamperguard_windows_validate.csv
    tamperguard_windows_test.csv
    tamperguard_realistic_eval.csv

splunk/
  searches/
    train_random_forest.spl
    apply_and_score.spl
    apply_onnx_model.spl

schemas/
  synthetic_event.schema.json
  behavior_window.schema.json
```

## Status

v0 is now organized as a self-contained milestone under [`v0/`](v0/). It proves the downstream training/deployment loop using authorized Splunk lab data: local feature extraction, deterministic splitting, local baseline training, SPL scoring artifact rendering, Splunk-side holdout scoring, local-vs-Splunk equivalence verification, and public-safety checks.

Start with [`v0/README.md`](v0/README.md), then see [`v0/docs/v0-model-pipeline-spec.md`](v0/docs/v0-model-pipeline-spec.md).

For finished-corpus planning, see [`docs/finished-dataset-requirements.md`](docs/finished-dataset-requirements.md) and the v1 scenario library in [`docs/scenario-design.md`](docs/scenario-design.md).

## Safety note

This project is about defending observability systems from tampering. It should not be used to attack real Splunk deployments, bypass monitoring in third-party environments, or publish operational abuse recipes.
