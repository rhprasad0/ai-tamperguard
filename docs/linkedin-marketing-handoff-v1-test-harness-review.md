# LinkedIn marketing handoff: adversarial review of AI TamperGuard v1 test harness

Date: 2026-05-26
Audience: marketing agent writing a LinkedIn post for Ryan Prasad
Project: AI TamperGuard
Source review: `docs/reviews/v1-test-harness-adversarial-review.md`

## Purpose of this handoff

Turn the Claude Opus 4.7 max-effort adversarial review of the AI TamperGuard v1 test harness into a LinkedIn post.

The post should explain a real eval-engineering lesson: a dataset generator can produce thousands of varied-looking rows while still creating a structurally easy, leaky classification task. The useful story is not “the project is broken.” The useful story is “this is why adversarial review belongs before model metrics.”

Tone: candid builder with receipts. Technical but readable. A little claw energy is allowed; do not become a lobster-themed compliance memo.

## One-sentence thesis

A few thousand rows is not automatically a training set; if scenario IDs, path names, and deterministic variation axes leak the answer key, the model learns the harness instead of the behavior.

## Short version

Ryan asked Claude Code Opus 4.7 to do a max-effort adversarial review of the v1 test harness.

The review found that the current dry-run training-batch generator can mint lots of rows, but those rows risk being misleading as ML training data because:

- `scenario_id` effectively determines the label.
- Generated IDs embed scenario/path information that should be opaque.
- Variation axes are produced with modular arithmetic, so they rotate predictably instead of independently varying.
- The generator declares target windows but does not actually produce windows in the dry-run path.
- Tests check “more than one value exists,” not whether variation is independent of the label.
- The catalog says scenarios support multiple path types, but the path-template file currently has only one template per scenario.

The post should frame this as a strong AI Engineering signal: Ryan is building the harness, then trying to break the harness before believing model metrics. That is the adult table version of AI evals. Tiny plastic trophy withheld until leakage is dead.

## Best LinkedIn angle

Use this angle:

> I asked an adversarial reviewer to attack my eval harness before I trusted the dataset. It found the exact kind of bug that makes ML demos look better than they are: label leakage hiding inside “variation.”

That gives the post a clean arc:

1. I wanted a few-thousand-row training set with lots of scenario variation.
2. Before training, I had Claude Opus do an adversarial review of the v1 test harness.
3. It found a problem: the generator could create many rows that looked varied but still leaked the answer key.
4. The bug was not just one column; it was structural: IDs, scenario-path mapping, deterministic axis rotation, and weak tests.
5. The fix is to test for independence and leakage, not just row count and distinct values.
6. This is why eval plumbing matters before model metrics.

## What happened, in plain English

AI TamperGuard is a lab dataset/eval project for studying observability-tamper behavior in Splunk/SOC workflows.

The v1 direction is to expand from a small set of scenarios into a few thousand training rows with more variation: different scenarios, path types, prompt variants, evidence ordering, conflict levels, distractors, benign controls, attempted positives, hard negatives, and successful synthetic tamper paths.

The adversarial review asked: if we generate that dataset, will it actually teach a model behavior — or will it teach a model to memorize harness artifacts?

The review’s answer was uncomfortable and useful:

- The current dry-run generator can produce many rows.
- But rows are not the same thing as independent signal.
- If `scenario_id` maps directly to label, then `scenario_id` becomes the label.
- If public IDs include scenario/path fragments, those “opaque” IDs are not opaque.
- If variation axes rotate by deterministic modular arithmetic, they can become proxies for scenario identity.
- If tests only assert “there is more than one actor profile,” they miss whether actor profile is correlated with the label.

Plain-English punchline:

> The dataset could look diverse to a human skimming row counts, while being trivial to a model memorizing the generator.

## Specific internal facts the marketing agent can use carefully

Use these as receipts, but keep them compact. This is LinkedIn, not `pytest --tb=long` as performance art.

- The adversarial review was done by Claude Code Opus 4.7 at max effort.
- The review was saved to `docs/reviews/v1-test-harness-adversarial-review.md`.
- The review was read-only against source/tests and created only the findings file.
- The review focused on the v1 harness, especially `v1/scripts/generate_training_batch_v1.py`, `v1/tests/test_training_batch_generation_v1.py`, `v1/scenarios/scenario_catalog_v1.jsonl`, and `v1/scenarios/path_templates_v1.jsonl`.
- The strongest finding: the dry-run training-batch path can generate varied-looking rows while preserving multiple label-leakage channels.
- One concrete example: with one path template per scenario, `scenario_id` can become a near-direct label key.
- Another concrete example: generated IDs such as scenario run IDs and synthetic case/report IDs were called out as embedding scenario/path information that should be opaque.
- Another concrete example: modular arithmetic over run index/attempt index/seed creates predictable variation, not independent sampling.
- Another concrete example: tests checked distinct counts rather than independence from labels.
- The review recommended adding multiple path templates per scenario, replacing modular variation with seeded RNG plus leakage checks, sanitizing IDs, enforcing column allowlists, and adding label-recovery probes.

If using numbers, use only high-level ones:

- “a few-thousand-row target”
- “14 scenario rows inspected in the catalog/path-template files”
- “one path template per scenario in the reviewed file”

Avoid dumping all file/line details in the post. Link or mention that the review exists in the repo if public and safe.

## Important correction to preserve

Do **not** write:

> The dataset is useless.

Write:

> The current dry-run generator is useful as a catalog/harness smoke test, but it should not be treated as a training corpus until leakage and variation checks are hardened.

Do **not** write:

> The model cheated.

Write:

> A model trained on this kind of corpus could learn shortcut artifacts from the harness instead of learning behavior.

Do **not** write:

> We found malicious AI behavior.

Write:

> We found an eval-harness risk in a synthetic Splunk/SOC lab project.

Do **not** write:

> The fix is just more data.

Write:

> The fix is better variation design, opaque IDs, paired controls, independence tests, and leakage probes before scaling row count.

## Why this is interesting

This is a clean AI Engineering lesson because it exposes a common failure mode:

> Scaling rows can scale confidence faster than it scales truth.

The mistake is easy to make. You build a generator, add seeds, add scenarios, add prompt variants, add a target row count, and suddenly it feels like a dataset. But if the variation is deterministic and label-correlated, the model may learn:

- scenario naming conventions,
- ID fragments,
- path-type strings,
- prompt variant cycles,
- actor-profile rotations,
- class balance artifacts,

instead of the actual behavior you wanted it to learn.

This makes Ryan look like someone who understands ML/eval plumbing beyond prompt demos:

- adversarial review before metrics,
- leakage analysis before training,
- distinction between row count and signal,
- conservative claims,
- safe lab framing,
- public technical artifact with receipts.

That is exactly the job-search signal: not “I made a model go brrr,” but “I built the system, attacked my own assumptions, and found the boring failure mode before reporting a shiny metric.”

## Recommended post structure

### Structure A: candid adversarial-review post

1. Hook: “I asked Claude Opus to attack my AI eval harness before I trusted the dataset. It found the kind of bug that makes ML demos look better than they are.”
2. Context: AI TamperGuard is a Splunk/SOC lab dataset project for observability-tamper behavior.
3. Goal: generate a few thousand varied training rows across scenarios and attack paths.
4. Finding: the generator could create many varied-looking rows while leaking labels through scenario/path/ID structure.
5. Lesson: row count is not signal if variation is correlated with the answer key.
6. Fix direction: opaque IDs, multiple path templates per scenario, seeded RNG, independence checks, label-recovery probes.
7. Boundary: synthetic lab/eval plumbing, not production detection or malicious ground truth.

### Structure B: “row count is not signal” post

1. Hook: “A few thousand rows can still be a tiny dataset wearing a trench coat.”
2. Explain the target: more v1 variation for AI TamperGuard.
3. Explain the adversarial review: before model training, attack the harness.
4. Explain the failure mode: deterministic axes + scenario IDs made labels recoverable.
5. Explain why it matters: models love shortcuts.
6. Explain the new standard: prove variation independence before trusting metrics.
7. Close with a question about leakage tests in agent/dataset evals.

### Structure C: practical eval checklist post

1. Hook: “Before I train on synthetic eval data, I now want five checks.”
2. Check 1: Can any ID recover the label?
3. Check 2: Does every scenario have multiple path types?
4. Check 3: Are variation axes independently sampled or just rotating?
5. Check 4: Do tests measure independence, not just distinct counts?
6. Check 5: Can a dumb label-recovery probe beat chance using metadata?
7. Close: if yes, fix the harness before celebrating model accuracy.

## Possible hooks

Pick one. Do not combine all of them.

1. “I asked Claude Opus to attack my AI eval harness before I trusted the dataset. It found the exact bug I was hoping it would find.”
2. “A few thousand rows can still be a tiny dataset wearing a trench coat.”
3. “This week’s AI eval lesson: row count is not signal if the answer key leaks through the plumbing.”
4. “Models love shortcuts. Eval harnesses accidentally manufacture them.”
5. “Before training on synthetic security data, ask: could a dumb model recover the label from IDs and metadata alone?”
6. “The adversarial review did its job: it made my future model metrics less fake.”
7. “I wanted more variation. The reviewer asked a better question: variation independent of what?”
8. “The bug was not that the generator made too few rows. The bug was that it could make many rows with the same hidden answer key.”

## Suggested draft post

Use this as raw material, not sacred text.

```text
I asked Claude Opus to attack my AI eval harness before I trusted the dataset.

It found the kind of bug that makes ML demos look better than they are.

I’m building AI TamperGuard, a lab dataset/eval project for studying observability-tamper behavior in Splunk/SOC workflows. The next v1 goal is pretty straightforward:

Generate a few thousand training rows with lots of scenario variation.

Different paths. Different prompt variants. Benign controls. Attempted positives. Hard negatives. Successful synthetic tamper paths.

Before training anything, I had Claude Code Opus 4.7 do a max-effort adversarial review of the test harness.

The uncomfortable finding:

The generator could create rows that looked varied, while still leaking the answer key through the harness.

Examples:

- `scenario_id` could effectively determine the label
- generated IDs embedded scenario/path information that should be opaque
- variation axes rotated by deterministic modular arithmetic
- tests checked “more than one value exists,” not whether the variation was independent of the label
- one path template per scenario meant several promised attack/control paths were not actually exercised yet

That means a model could learn the generator instead of the behavior.

And because models are tiny shortcut goblins with matrix multiplication budgets, they absolutely will.

The fix is not “more rows.”

The fix is better eval plumbing:

- opaque IDs
- multiple path templates per scenario
- seeded RNG instead of deterministic rotations
- paired controls and hard negatives
- column allowlists at the training boundary
- independence checks between variation axes and labels
- label-recovery probes that ask: can a dumb model predict the answer from metadata alone?

This is the boring part of AI Engineering that matters.

A 0.99 AUC on leaky synthetic data is not a result. It is a harness bug wearing a graduation cap.

Better to find that before training than after posting metrics.

Tiny lobster note: if the tank has rails, don’t brag about how well the lobster navigates.
```

## Shorter draft

```text
A few thousand rows can still be a tiny dataset wearing a trench coat.

I’m building AI TamperGuard, a Splunk/SOC lab dataset for observability-tamper behavior. The next v1 goal is a larger training set with more scenario variation.

Before training, I had Claude Opus do an adversarial review of the test harness.

It found the right kind of ugly:

- scenario IDs could effectively determine labels
- generated IDs embedded scenario/path info
- variation axes rotated deterministically
- tests checked distinct counts, not independence
- several promised path types were not actually exercised yet

In other words: the generator could create varied-looking rows while still leaking the answer key.

That is exactly the failure mode I want to catch before reporting model metrics.

More data does not fix leakage. It just gives the shortcut more examples.

The next pass is about opaque IDs, real path diversity, seeded RNG, paired controls, independence checks, and label-recovery probes.

AI eval lesson: before asking whether a model learned the behavior, ask whether it could learn the harness instead.
```

## Carousel / infographic idea

Title: **Row count is not signal**

Slide/card sequence:

1. **Goal** — Build a few-thousand-row AI TamperGuard v1 training set.
2. **Before training** — Ask an adversarial reviewer to attack the harness.
3. **Finding** — Rows can look varied while labels leak through metadata.
4. **Leak paths** — Scenario IDs, generated IDs, path names, deterministic rotations.
5. **False green** — Distinct values ≠ independent variation.
6. **Better gates** — Opaque IDs, path diversity, RNG, paired controls, leakage probes.
7. **Takeaway** — If a dumb model can learn the answer key, your smart model metric is fake confidence.
8. **Boundary** — Synthetic lab eval plumbing, not production SOC claims.

Visual style: mobile-first technical poster/carousel. Dark graphite/navy background, thin grid lines, white text, blue/violet/amber accents. Use simple diagrams: “metadata shortcut → label” and “real signal path → behavior window.”

Avoid: hooded hackers, glowing robot brains, cyberpunk dashboards, fake Splunk screenshots, random circuit boards, stock humans pointing at holograms, “AI magic” sludge.

## Good closing questions

Use one.

- “What leakage probe do you run before trusting synthetic eval data?”
- “When you generate eval datasets, how do you prove variation is independent of the label?”
- “What is your favorite dumb baseline for catching a smart model’s shortcut?”
- “For agent/security evals, where do you draw the line between useful scenario metadata and answer-key leakage?”
- “Before reporting model metrics, what harness bugs do you try to kill first?”

## Claim boundaries

### Safe to say

- AI TamperGuard is a lab dataset/eval project for observability-tamper behavior in Splunk/SOC workflows.
- Ryan asked Claude Code Opus 4.7 to adversarially review the v1 test harness before trusting training data.
- The review found structural label-leakage risks in the current dry-run training-batch path.
- The current dry-run generator is useful as a smoke test/catalog generator, not yet as a training corpus for model-quality claims.
- Row count alone is not enough; variation must be independent of the answer key.
- The next fix direction is opaque IDs, multiple path types per scenario, better randomization, paired controls, hard negatives, and leakage probes.
- This is synthetic lab/eval plumbing, not production detection.

### Do not say

- Do not say the final dataset is bad or unusable forever.
- Do not say the project failed.
- Do not say a trained model cheated; no model metric is the point here.
- Do not claim production tamper detection.
- Do not describe real attack steps against Splunk.
- Do not imply labels are malicious ground truth; they are scenario-grounded / weak working labels.
- Do not publish private paths, raw prompts, SPL, hostnames, internal IPs, usernames, tokens, private object names, or raw Splunk data.
- Do not overstate Claude’s review as mathematically exhaustive; it is an adversarial review with specific inspected files and some findings marked “needs verification.”

## Suggested technical framing

Use this vocabulary:

- adversarial eval review
- label leakage
- metadata shortcut
- scenario variation
- path templates
- paired controls
- hard negatives
- seeded RNG
- deterministic rotations
- independence checks
- label-recovery probe
- behavior-window features
- synthetic lab dataset
- harness smoke test vs training corpus

Avoid this vocabulary unless carefully qualified:

- production detector
- malicious ground truth
- autonomous insider threat
- real compromise
- exploit path
- jailbreak benchmark
- “proved security”
- “solved tamper detection”

## Source context for the marketing agent

- Project repo: `/home/ryan/projects/ai-tamperguard`
- Source adversarial review: `docs/reviews/v1-test-harness-adversarial-review.md`
- Related prior handoff: `docs/linkedin-marketing-handoff-nondeterminism.md`
- Key reviewed generator: `v1/scripts/generate_training_batch_v1.py`
- Key reviewed test: `v1/tests/test_training_batch_generation_v1.py`
- Key scenario files: `v1/scenarios/scenario_catalog_v1.jsonl`, `v1/scenarios/path_templates_v1.jsonl`
- Keep in mind: repo policy is public/tracked by default, but real secrets, credentials, tokens, PII, raw private telemetry, and private environment details stay out.

## Final instruction to the marketing agent

Write the post as a credible AI Engineering lesson, not a doom post:

> I wanted a bigger dataset. The adversarial review reminded me that bigger is not better if the harness leaks the answer key.

The story should make Ryan look like a builder who does not trust shiny metrics until the plumbing survives contact with an adversarial reviewer.

Keep the claws sharp. Keep the claims sharper.
