# LinkedIn Marketing Handoff: AI TamperGuard v0

## Purpose of this handoff

Turn this v0 milestone into a LinkedIn post that communicates **AI Engineering with receipts**: scoped ambition, real blockers, measured verification, and honest claim boundaries.

This is not a request to write hype. The post should make the work legible to recruiters, hiring managers, AI engineers, security engineers, and Splunk/SOC-adjacent readers.

## One-sentence thesis

I built AI TamperGuard v0 as a smoke test for a local-training → Splunk-side-scoring pipeline, and the useful lesson was not “we made a detector” — it was proving the plumbing, discovering the deployment guardrails, and verifying local-vs-Splunk scoring equivalence with numbers.

## Short version

AI TamperGuard v0 proves that a baseline model can be trained locally on private authorized Splunk control-plane data, converted into an auditable scoring artifact, deployed into a scoped Splunk app context, scored inside Splunk, and verified against local expected results.

It is explicitly **not** a production tamper detector.

The most important part: the first deployment path was blocked for good reasons. Generic Splunk write surfaces were too broad for v0, and the MCP guard blocked `outputlookup`. Instead of weakening the guardrail, the implementation narrowed the scope: local training, JSON model artifact, rendered SPL coefficient math, scoped app deployment, equivalence checks, and rollback verification.

## What actually happened

### Built

- A self-contained v0 implementation under `v0/`.
- JSON schema contracts for behavior windows, model artifacts, and held-out fixtures.
- Feature extraction for authorized Splunk control-plane logs.
- Deterministic train/holdout splitting.
- Local logistic-regression baseline training.
- A renderer that converts the trained model into plain SPL scoring math.
- A verification harness that compares local expected scores to Splunk-scored results.
- Public-safety checks to prevent private Splunk data, private model artifacts, generated CSVs, hostnames, usernames, tokens, or overclaims from entering the public repo.

### Verified

- Unit/hygiene test suite: **79 passed**.
- Private v0 Splunk run scored **241 held-out rows**.
- Local-vs-Splunk verification results:
  - `max_score_residual = 4.54747350886e-13`
  - `max_probability_residual = 2.22044604925e-16`
  - `prediction_mismatches = 0`
- Rollback was exercised by removing the `ai_tamperguard` Splunk app artifacts, restarting Splunk, and confirming no remaining `ai_tamperguard` / `tamperguard_v0_score_holdout` matches in fresh Splunk MCP inventory.

### Organized for review

- v0 code, tests, scripts, schemas, Splunk templates, docs, and report template now live under `v0/`.
- `v0/README.md` explains what was accomplished, what v0 does not claim, the blocker, the workaround, how to run checks, and the safety boundary.
- `v0/docs/v0_explainer.png` is a visual explainer for the pipeline.

## The blocker

The blocker was **Splunk-side deployment surface area**, not local model training.

The initial idea was to use a normal AI Toolkit / MLTK / ONNX-style model path. That was intentionally paused because:

- ONNX / MLTK availability and permissions were unresolved for v0.
- Broad write paths were too much surface area for a first smoke test.
- The Splunk MCP guard correctly blocked generic `outputlookup`.

That block should be framed as a good engineering moment. The guardrail did its job.

## The workaround

Instead of weakening the guardrail, v0 narrowed the path:

1. Train a baseline model locally.
2. Store the model as a private JSON artifact with feature order, coefficients, intercept, threshold, metadata, and diagnostics.
3. Render plain SPL that computes the logistic-regression score using explicit coefficient math.
4. Deploy only scoped private lookup/search artifacts into the `ai_tamperguard` Splunk app context.
5. Run Splunk-side scoring on held-out rows.
6. Export scored results and compare them against local expected scores.
7. Roll back the app artifacts and verify removal.

This kept v0 independent from Splunk AI Toolkit, MLTK, ONNX import, custom Python search commands, and broad MCP write permissions.

## Claim boundaries

### Safe to say

- “v0 is a smoke test of a local-training → Splunk-side-scoring pipeline.”
- “The pipeline is private-first and public-safe.”
- “The labels are weak proxy labels, not malicious ground truth.”
- “The result verifies scoring equivalence between local Python and Splunk SPL on held-out rows.”
- “The deployment blocker was handled by narrowing scope rather than weakening guardrails.”
- “This is an AI engineering / eval / deployment plumbing milestone.”

### Do not say

- Do not say v0 detects malicious tampering.
- Do not say the model is production-ready.
- Do not claim field detection effectiveness.
- Do not imply the private Splunk data is public or shareable.
- Do not frame weak proxy labels as adversarial ground truth.
- Do not claim ONNX / MLTK / AI Toolkit deployment was completed.
- Do not over-index on model metrics as security efficacy. Metrics here are plumbing diagnostics.

## Suggested LinkedIn angle

### Best angle

**“The interesting part of this AI/SOC experiment was the blocker.”**

That lets the post avoid generic “I built a thing” energy and instead show engineering judgment:

- A broad deployment path was tempting.
- A guardrail blocked it.
- Rather than bypassing the guardrail, the system was narrowed.
- The final proof was measured equivalence and rollback, not a vibes-based demo.

### Possible hook options

Pick one. Do not kitchen-sink them.

1. “The best part of this AI/SOC experiment was the part that failed.”
2. “I built a Splunk-side scoring pipeline, then refused to call it a detector.”
3. “A guardrail blocked my first deployment path. Good.”
4. “This is what I mean by AI engineering with receipts: not a demo, an equivalence check.”
5. “The model was not the hard part. The deployment boundary was.”

## Recommended post structure

### Structure A: blocker-first story

1. Hook: the blocker was the useful part.
2. Context: AI TamperGuard v0 is a local-training → Splunk-side-scoring smoke test.
3. Blocker: broad ML app / write path was too much surface; generic `outputlookup` was blocked.
4. Decision: do not weaken the guardrail; narrow the path.
5. Workaround: local training → JSON artifact → rendered SPL coefficient math → scoped app deployment → Splunk scoring.
6. Receipts: 241 rows, residuals, zero prediction mismatches, rollback verified, 79 tests passed.
7. Boundary: not a tamper detector; labels are weak proxies.
8. Close: this is the kind of AI engineering I want to do — systems that are measurable, auditable, and honest about what they prove.

### Structure B: receipts-first story

1. Hook: “The number I cared about was not accuracy.”
2. Explain: weak labels make model metrics less important for v0.
3. Important metric: local-vs-Splunk scoring equivalence.
4. Receipts: residuals and prediction agreement.
5. Blocker/workaround: no ONNX/MLTK path; plain SPL math and scoped deployment.
6. Boundary: plumbing milestone, not security efficacy.
7. Close: ask whether others test deployment equivalence this explicitly.

## Suggested draft post

Do not use this verbatim if it sounds too polished. Use it as raw material.

```text
The most useful part of my latest AI/SOC experiment was the part that blocked.

I built AI TamperGuard v0 as a smoke test for a local-training → Splunk-side-scoring pipeline.

Not a production detector.
Not a benchmark.
Not “AI catches attackers.”

The goal was narrower:

Can I take authorized Splunk control-plane logs, extract behavior-window features, train a small local baseline, turn that model into something Splunk can score, and verify that Splunk reproduces the local scoring math?

The first obvious path was an AI Toolkit / MLTK / ONNX-style deployment.

But for v0, that was too much surface area. Availability and permissions were unresolved, and the Splunk MCP guard correctly blocked a generic outputlookup-style write path.

So I did the boring-but-correct thing: I did not weaken the guardrail.

I narrowed the system.

v0 became:

- local logistic-regression training
- private JSON model artifact
- explicit SPL coefficient math
- scoped ai_tamperguard app deployment
- held-out Splunk-side scoring
- local-vs-Splunk equivalence verification
- rollback verification

Receipts:

- 79 tests passing
- 241 held-out rows scored in Splunk
- max score residual: 4.55e-13
- max probability residual: 2.22e-16
- prediction mismatches: 0
- rollback exercised and verified clean

The labels are weak working-model proxies, not malicious ground truth. v0 does not claim detection quality.

What it does prove is the pipeline: private local data → model artifact → auditable Splunk scoring → measured equivalence.

This is the kind of AI engineering I want to keep doing: less “look, model!” and more “here is exactly what the system proves, exactly what it does not, and the receipts.”
```

## Optional visual caption for `v0_explainer.png`

```text
AI TamperGuard v0: a private-first smoke test of local model training → Splunk-side scoring. The result is not a tamper-detection claim; it is a measured equivalence check between local Python scoring and Splunk SPL scoring on held-out rows.
```

## Suggested close questions

Use one, not all.

- “How do you usually verify that a model deployed into a data platform still matches local training-time behavior?”
- “Do you treat deployment equivalence as part of eval, or as a separate release-engineering concern?”
- “Where do you draw the line between useful ML plumbing and premature detection claims?”

## Voice guidance

- Crisp, honest, builder-with-receipts tone.
- A little personality is good; do not turn it into founder-bro fireworks.
- Avoid “thrilled to share.” The lobster will file a complaint.
- Keep the post mobile-skimmable.
- Lead with the blocker or the receipts, not with a long project intro.

## Source artifacts to reference

- `v0/README.md`
- `v0/docs/v0-model-pipeline-spec.md`
- `v0/docs/v0-model-pipeline-spec-adversarial.md`
- `v0/docs/v0-open-questions.md`
- `v0/docs/v0_explainer.png`
- `v0/reports/v0-smoke-test-template.md`
