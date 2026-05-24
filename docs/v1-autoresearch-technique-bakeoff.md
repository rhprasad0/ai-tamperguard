# AI TamperGuard v1 AutoResearch + Technique Bakeoff Notes

## Purpose

This note captures the current research findings and design direction for applying a Karpathy-style AutoResearch loop to AI TamperGuard after v0 proves the local-training-to-Splunk-scoring pipe.

The short version:

> v0 proves that a small model can move from local training into Splunk-side scoring without silently breaking. v1 should ask which simple technique earns the right to replace the v0 logistic-regression baseline.

This is **technique selection**, not open-ended hyperparameter fishing.

## Background: Karpathy's AutoResearch pattern

Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch) is a minimal autonomous ML research loop for single-GPU `nanochat` training. The project gives an agent a small real training setup and lets it repeatedly:

1. modify the editable training code;
2. run a fixed-budget experiment;
3. evaluate one objective metric;
4. keep the change if it improves;
5. discard or reset if it does not;
6. continue until manually stopped.

Important design ideas from the repo:

- **Human edits the research program, not every experiment.** The human writes or improves `program.md`; the agent edits the allowed code surface.
- **One editable surface.** In Karpathy's setup, the agent edits `train.py` while the data/evaluation file stays fixed.
- **Fixed experiment budget.** Runs are comparable because each experiment uses the same time budget.
- **Objective metric.** The loop only works when the result can be automatically evaluated.
- **Keep/discard log.** Experiments produce an audit trail of what was tried, what improved, what crashed, and what was discarded.

A useful rule of thumb from the surrounding AutoResearch discussion is:

> If you cannot evaluate it automatically, you cannot AutoResearch it.

For AI TamperGuard, that means v1 should avoid vague claims like "better tamper detection" and instead optimize bounded, measurable outcomes under fixed gates.

## Has AutoResearch been used to train neural networks from scratch?

Yes, with one important nuance: the public examples usually do **not** ask an agent to invent a neural network from an empty directory. They give the agent a real training scaffold, a fixed evaluator, and a constrained editable surface. Each candidate run then trains a model from scratch, measures it, and keeps or discards the code or recipe change.

That is exactly the framing AI TamperGuard should copy:

> Each candidate model is trained fresh under a fixed budget. The agent proposes bounded recipe/code changes, and the evaluator promotes only candidates that pass fixed leakage, privacy, schema, deployment, and metric gates.

### Public examples

| Example | What was trained from scratch | AutoResearch pattern | Why it matters here |
|---|---|---|---|
| [Karpathy `autoresearch`](https://github.com/karpathy/autoresearch) | Small GPT-style `nanochat` language model | Agent edits `train.py`, runs fixed 5-minute experiments, optimizes validation bits per byte (`val_bpb`), keeps/discards changes | Canonical reference for a minimal autonomous neural-network training-recipe loop |
| [Karpathy session #32](https://github.com/karpathy/autoresearch/discussions/32) | Same GPT-style setup | 89 H100 experiments improved `val_bpb` from `0.997900` to `0.977287` | Shows the loop can produce an auditable sequence of kept/discarded recipe improvements |
| [Karpathy session #43](https://github.com/karpathy/autoresearch/discussions/43) | Same GPT-style setup | 126 experiments over ~10.5 hours improved `val_bpb` from `0.997900` to `0.969686` | Useful template for a session report: total trials, kept/discarded/crashed counts, biggest wins, final recipe |
| [`autoresearch-connect4`](https://github.com/alessoh/autoresearch-connect4) | Connect Four neural policy/value model from random weights | Agent edits CNN/RL `train.py`, trains via self-play for 5 minutes, evaluates against fixed opponents | Best non-LLM example: each run starts from random weights and the evaluator is a game-performance harness |
| [HF `mishig/autoresearch-results`](https://huggingface.co/buckets/mishig/autoresearch-results) | LLM pretraining recipe on A100 using Hugging Face Jobs | Agent reads papers, edits `train.py`, submits jobs, evaluates, keeps/discards | Shows the pattern can run on hosted infrastructure and preserve public artifacts like `results.tsv`, `best_train.py`, and `progress.png` |
| [VectorNomad `autoresearch-540m`](https://huggingface.co/VectorNomad/autoresearch-540m) | 540M-parameter Arabic-first GPT-style model | Nanochat/AutoResearch-adjacent from-scratch training effort | Good evidence that the surrounding ecosystem is using these scaffolds for real from-scratch model training, though the card is less explicit about a full closed-loop trace |

### Academic and benchmark follow-ons

Recent research is also formalizing the pattern:

- [Auto Research with Specialist Agents Develops Effective and Non-Trivial Training Recipes](https://arxiv.org/html/2605.05724) defines auto research as a closed empirical loop of hypotheses, executable code edits, evaluator-owned outcomes, and lineage feedback. It reports autonomous improvements on Parameter Golf, NanoChat-D12, and CIFAR-10 Airbench96.
- [Can LLMs Beat Classical Hyperparameter Optimization Algorithms? A Study on `autoresearch`](https://arxiv.org/html/2603.24647v3) uses Karpathy's setup as a benchmark and finds that classical HPO is strong in fixed hyperparameter spaces, while LLM code-editing is more competitive when it can make broader source-level recipe changes.

The second point is important for AI TamperGuard: do not use an LLM agent as a worse Optuna. If the search space is just numeric knobs, a classical optimizer or deterministic grid is a better baseline. The agent earns its keep when it can propose structured recipe changes, repair failures, summarize lineage, and generate auditable reports.

### Implication for AI TamperGuard

The honest claim is not:

> The agent discovered tamper detection.

The stronger, safer claim is:

> AI TamperGuard uses a Karpathy-style AutoResearch loop to train candidate behavior-window models from scratch under fixed privacy, leakage, schema, scoring, and deployment-equivalence gates.

That gives a recruiter-readable AI systems story without claiming production-grade detection quality. Tiny lab coat, real clipboard.

## Why logistic regression is first in v0

Logistic regression remains the correct v0 starting point because v0 is proving the pipe, not winning a model leaderboard.

It is useful because it is:

- **Splunk-scoreable with plain SPL.** The score is an intercept plus coefficient-weighted feature sum, followed by a logistic transform and threshold.
- **Auditable.** The artifact is just feature order, coefficients, intercept, threshold, model version, and metadata.
- **CPU-safe.** It does not require GPU inference, MLTK, AI Toolkit, or ONNX.
- **Good at exposing pipeline bugs.** Feature-order drift, null coercion, string/numeric mismatch, constant predictors, and local-vs-Splunk score differences become obvious.
- **Honest.** A boring model reinforces that v0 is a weak-proxy smoke test, not a validated malicious-tamper detector.

v0 should still end with a simple, high-confidence proof:

```text
authorized Splunk control-plane logs
→ private behavior-window feature table
→ local logistic-regression training
→ exported artifact
→ SPL eval scoring in ai_tamperguard
→ local-vs-Splunk numeric equivalence check
```

## v1 direction: constrained technique bakeoff

For v1, build a harness that tries several model/feature techniques while keeping hyperparameter tuning minimal.

The goal is not to exhaustively optimize every model. The goal is to determine which family of simple techniques works best under AI TamperGuard's constraints.

Recommended framing:

> Given the same behavior-window table, labels, splits, feature schema, and deployment gates, which technique improves the weak-proxy objective enough to justify its complexity?

This makes v1 a controlled bakeoff:

```text
fixed dataset
fixed train/validation/test splits
fixed feature schema
fixed evaluator
fixed public/private boundaries
minimal technique recipes
→ compare model families
→ promote the simplest candidate that genuinely wins
```

## Candidate techniques

Start with tabular methods that make sense for behavior-window features.

### Tier 1: boring but valuable baselines

| Technique | Why try it | Deployment notes |
|---|---|---|
| Logistic regression | v0 baseline; interpretable; directly SPL-scoreable | Already supported path |
| Linear SVM / SGD classifier | Tests whether margin-based linear learning helps | Potentially exportable as linear weights, but probability calibration needs care |
| Naive Bayes | Sometimes strong for count-heavy features; very lightweight | SPL export may be possible but should be explicitly implemented and gated |
| Shallow decision tree | Captures simple nonlinear rules | Could be rendered as SPL `case()` if tree is small |
| Small random forest | Stronger nonlinear baseline for tabular data | Harder to deploy directly; likely private/offline comparison first |
| Gradient boosting / histogram boosting | Often strong for tabular data | Higher deployment complexity; should not be first promotion path unless export/scoring is solved |

### Tier 2: later ideas

Consider these only after the Tier 1 harness is stable:

- calibrated classifiers;
- feature-selection wrappers;
- actor-heldout or time-heldout model variants;
- sequence or graph-derived features;
- richer models for private/offline analysis, with SPL-compatible distillation if needed.

## Keep hyperparameter tuning deliberately small

v1 should use a few predefined profiles per technique, not broad search.

Example recipe shape:

```yaml
logistic_regression:
  profiles:
    - name: default_balanced
      class_weight: balanced
      C: 1.0
    - name: stronger_regularization
      class_weight: balanced
      C: 0.25

linear_sgd:
  profiles:
    - name: hinge_balanced
      loss: hinge
      class_weight: balanced
    - name: log_loss_balanced
      loss: log_loss
      class_weight: balanced

decision_tree:
  profiles:
    - name: stump
      max_depth: 1
      min_samples_leaf: 10
    - name: shallow
      max_depth: 3
      min_samples_leaf: 10

random_forest:
  profiles:
    - name: small_forest
      n_estimators: 50
      max_depth: 4
      min_samples_leaf: 10
```

This prevents v1 from becoming a random-seed casino with a YAML addiction.

## Evaluation gates

A candidate should be disqualified before metric comparison if it fails any hard gate.

Suggested hard gates:

1. fixed train/validation/test split is respected;
2. no train/holdout overlap;
3. feature schema matches the canonical schema;
4. no raw usernames, hostnames, URLs, SPL strings, or private object names are used as model features;
5. missing features and nulls are handled deterministically;
6. model is not a constant predictor;
7. artifact export succeeds;
8. scoring path is supported for the technique;
9. if deployed to Splunk, local-vs-Splunk score/probability/prediction equivalence passes;
10. generated private data, private model artifacts, and private reports remain uncommitted;
11. generated public-facing text does not overclaim detection quality.

## Metrics to collect

Use metrics as diagnostics over weak proxy labels, not as claims of real-world malicious detection.

Quality metrics:

- average precision;
- balanced accuracy;
- precision;
- recall;
- F1;
- ROC AUC when valid;
- confusion matrix;
- precision/recall at selected thresholds.

Stability metrics:

- time-split performance;
- actor-heldout performance where feasible;
- bootstrap confidence interval;
- threshold stability;
- feature importance stability;
- train/validation gap.

Operational metrics:

- artifact size;
- number of features used;
- scoring latency or SPL expression size;
- deployability class: direct SPL, generated SPL, lookup-assisted SPL, offline-only;
- rollback complexity;
- explainability.

## Promotion rule

Do not automatically pick the highest raw metric. Promote the simplest candidate that clears the gates and improves enough to justify its complexity.

A practical promotion rule:

```text
A candidate may replace the current baseline only if:

1. all hard gates pass;
2. the primary validation metric improves by at least a configured minimum delta;
3. stability does not regress materially;
4. deployment complexity is acceptable for the current phase;
5. the candidate does not weaken the public claim boundary.
```

Candidate ranking can be a simple composite, for example:

```text
candidate_score =
  0.45 * average_precision
+ 0.25 * balanced_accuracy
+ 0.15 * stability_score
+ 0.10 * deployability_score
+ 0.05 * simplicity_score
```

But the final report should still explain the decision in plain English. If a complex model barely beats logistic regression, keep logistic regression. Tiny gain, giant yak: discard the yak.

## Recommended v1 harness outputs

The harness should produce a private report similar to:

```text
reports/private/v1-technique-bakeoff.md
```

Recommended sections:

```md
# AI TamperGuard v1 Technique Bakeoff

## Dataset
- source family:
- window family:
- split strategy:
- label source:
- feature count:

## Candidate Summary
| technique | profile | status | avg precision | balanced acc | stability | deployable | notes |
|---|---|---:|---:|---:|---:|---|---|

## Winner
Selected: ...

## Why This Won
- ...

## Why Other Candidates Lost
- ...

## Deployment Notes
- ...

## Non-Claims
- weak proxy labels, not malicious ground truth
- not production detection quality
- not a public benchmark result
```

The public repo can include a synthetic/example report template, but private lab results and trained artifacts should remain ignored unless explicitly prepared for publication.

## AutoResearch modes for AI TamperGuard

There are two useful modes.

### Mode A: deterministic bakeoff

Run a fixed harness with predeclared recipes:

```bash
python scripts/run_v1_technique_bakeoff.py \
  --features data/private/windows_train.csv \
  --output reports/private/v1-technique-bakeoff.md
```

This mode is best for a clean v1 implementation.

### Mode B: AutoResearch over bounded recipes

After the deterministic harness works, allow an agent to propose bounded candidate recipes.

Editable surface:

```text
experiments/v1_technique_bakeoff/recipes/*.yaml
```

or one narrow candidate file:

```text
src/ai_tamperguard/research/candidate_recipe.py
```

Forbidden surfaces:

```text
splits
labels
evaluator
feature extraction
privacy scanner
public-safety gates
Splunk equivalence checker
```

The agent can propose a technique recipe, run the harness, and keep the recipe only if it beats the current best while passing every gate.

## Relationship to broader research-agent work

This direction is consistent with the broader AI research-agent trend:

- [Karpathy AutoResearch](https://github.com/karpathy/autoresearch) demonstrates the simple autonomous loop: edit, train, evaluate, keep/discard, repeat.
- [Karpathy AutoResearch session reports](https://github.com/karpathy/autoresearch/discussions) show the public reporting shape AI TamperGuard should emulate: baseline score, best score, trial count, kept/discarded/crashed count, and ranked findings.
- [MLAgentBench](https://github.com/snap-stanford/MLAgentBench) evaluates agents on end-to-end ML experimentation tasks with file editing, code execution, and automatic metrics.
- [MLGym](https://github.com/facebookresearch/MLGym) frames machine-learning research tasks as environments where agents generate hypotheses, implement methods, run experiments, analyze results, and iterate.
- [Auto Research with Specialist Agents Develops Effective and Non-Trivial Training Recipes](https://arxiv.org/html/2605.05724) argues for evaluator-owned scoring, lineage feedback, specialist recipe surfaces, and auditable trajectories rather than one-shot generated papers or opaque final checkpoints.
- [Can LLMs Beat Classical Hyperparameter Optimization Algorithms? A Study on `autoresearch`](https://arxiv.org/html/2603.24647v3) is a useful warning: classical HPO can beat LLM agents in fixed numeric search spaces, so TamperGuard should treat deterministic grids/classical baselines as controls and reserve agents for higher-level recipe changes.

AI TamperGuard's differentiator is operational: the winning model does not just need to score well locally. It must survive the model-artifact-to-Splunk-scoring path and prove local-vs-Splunk equivalence.

## Suggested roadmap

```text
v0:
  Logistic regression only.
  Prove local training → artifact → SPL scoring → equivalence.

v1:
  Deterministic technique bakeoff harness.
  Compare simple tabular model families with minimal tuning.
  Pick winner based on quality, stability, simplicity, and deployability.

v1.5:
  AutoResearch recipe loop.
  Agent proposes bounded candidate recipes.
  Keep only candidates that beat the current best and pass all gates.

v2:
  Richer scenario-grounded dataset.
  Paired benign/tamper-congruent runs.
  Sequence, graph, and scenario-level features.
```

## Public framing

Good public framing:

> AI TamperGuard v1 explores whether autonomous research agents can improve a Splunk-scored behavior-window model under fixed privacy, leakage, schema, and deployment-equivalence gates.

Avoid:

- claiming malicious detection quality;
- claiming Splunk is insecure;
- publishing raw lab data;
- presenting weak proxy labels as ground truth;
- treating local notebook metrics as deployment success.

Better punchline:

> The model was not just trained. It was researched, exported, deployed, scored in Splunk, and numerically checked against the local artifact.

Numbers, not vibes.
