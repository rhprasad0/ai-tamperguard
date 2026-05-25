# LinkedIn marketing handoff: nondeterminism lessons from AI TamperGuard

Date: 2026-05-25
Audience: marketing agent writing a LinkedIn post for Ryan Prasad
Project: AI TamperGuard

## Purpose of this handoff

Turn the recent nondeterminism debugging work into a LinkedIn post.

The post should explain a real engineering lesson from AI TamperGuard: when evaluating AI agents, a repeated-run test can look deterministic for reasons that have nothing to do with the agent's mind. In our case, the first pipeline mostly measured deterministic seeded evidence generation, not true live agent variation.

This should sound like Ryan being candid about an eval design bug he found and fixed/diagnosed, not like a product announcement. Builder with receipts. No vendor confetti cannon.

## One-sentence thesis

The useful lesson is not "the uncensored agent is deterministic"; it is "our eval harness was accidentally too deterministic, so we had to separate seeded template behavior from actual agent trajectories before making claims about nondeterminism."

## Short version

AI TamperGuard is a lab dataset/eval project for studying observability-tamper behavior in Splunk/SOC workflows.

Ryan ran repeated `k=3` tests to see whether prompt variants caused different behavior across attempts. The early result looked extremely stable: most scenario/variant groups produced identical behavior-window and normalized-event signatures.

But the deeper diagnosis was the important part:

- The agent was not truly in the data-generation loop for those rows.
- The pipeline was seeding deterministic public-safe scenario events into Splunk.
- Prompt-pack variation changed metadata/provenance, but did not meaningfully change the generated event trajectory.
- `attempt_index` and `prompt_seed` were not creating enough trajectory-level variation.
- Therefore the safe claim is about the harness, not the agent's psychology.

The post should frame this as an eval-engineering lesson: if you want to measure nondeterministic agent behavior, you need to record and compare trajectories, tool calls, state deltas, and repeated trials — not just final rows produced by a deterministic fixture path.

## Best LinkedIn angle

Use this angle:

> A single agent run is a demo. Repeated runs are an eval. But only if the agent is actually in the loop.

That gives the post a clean arc:

1. I tried to measure nondeterminism in an uncensored agent.
2. The results looked suspiciously stable.
3. The bug was not necessarily the model. It was my harness.
4. I was generating deterministic evidence templates and then asking the analysis pipeline to find variation.
5. The fix is to separate generator modes and record true trajectories.
6. This is the kind of boring eval plumbing that prevents fake confidence.

## What happened, in plain English

The pipeline was intended to test whether different prompt variants and repeated attempts would produce different observable behavior in a Splunk/SOC lab.

The repeated run produced useful evidence that the current pipeline was stable, but not enough evidence that the uncensored agent itself was stable.

The key distinction:

- **What we measured:** deterministic seeded scenario evidence written to Splunk and read back into behavior-window features.
- **What we wanted to measure:** live agent decision variation across repeated attempts.

That gap matters. If the event generator does not consume the private prompt body or actual agent trajectory, then prompt changes may not alter the resulting Splunk events. The harness can accidentally turn every run into the same movie with a different filename.

## Specific internal facts the marketing agent can use carefully

Use these as receipts, but do not overstuff the post with numbers.

- A repeated `k=3` live batch produced 80 scenario runs.
- Splunk read-back verified 315 events.
- The pipeline produced 315 normalized events.
- The pipeline produced 80 behavior windows.
- The pipeline produced 80 private training rows.
- Across 23 variant groups, 22 were stable and 1 was partially variable.
- The partially variable group was `scenario_006` with `limited_budget_choose_path_v1_a`.
- No Openclaw grading was included in this run.
- Public safety checks passed.
- The safe conclusion was that observable variation was narrow under the current seeded path, not that the uncensored agent is inherently deterministic.

If using numbers in the final post, keep them compact. This is LinkedIn, not a pytest obituary.

## Important correction to preserve

Do **not** write:

> We proved the uncensored agent is deterministic.

Write something closer to:

> I initially thought I was measuring whether the agent behaved nondeterministically. What I actually measured was that my seeded evidence-generation path was too deterministic. That is a different and more useful finding.

Or:

> The result was not "agent deterministic." It was "harness deterministic." That distinction matters if you care about honest evals.

## Why this is interesting

This connects directly to how serious agent evals should work.

Single runs are weak evidence. For agentic systems, especially ones with tools or environment state, useful evals need:

- repeated trials
- trajectory capture
- tool-call logs
- state deltas
- outcome checkpoints
- semantic validity checks
- pass@k / fail@k thinking
- regression replay
- clear separation between fixture-generated data and live-agent behavior

The post should make Ryan look like someone who understands that AI evals are systems engineering, not just prompt vibes with a spreadsheet.

## Recommended post structure

### Structure A: candid eval-debugging post

1. Hook: "I tried to measure nondeterminism in an uncensored agent and mostly found a deterministic harness."
2. Context: AI TamperGuard is a Splunk/SOC lab dataset/eval project.
3. Result: repeated `k=3` runs produced mostly stable behavior signatures.
4. Twist: that did not prove the agent was deterministic, because the seeded event-generation path was doing too much of the work.
5. Lesson: agent nondeterminism needs trajectory-level measurement, not just final event rows.
6. Next step: separate generator modes such as seeded templates, randomized templates, live agent runs, and replay.
7. Claim boundary: this is lab eval plumbing, not production detection and not a claim about all uncensored agents.

### Structure B: "harness deterministic" post

1. Hook: "The most useful bug I found this week: my AI eval was measuring the harness more than the agent."
2. Explain the intended eval: repeated attempts across prompt variants in a Splunk/SOC lab.
3. Explain the surprise: 22 of 23 variant groups were stable, only 1 partially varied.
4. Explain the root cause: deterministic seeded events were being generated regardless of meaningful prompt variation.
5. Explain the fix direction: trajectory signatures, generator modes, and repeated trials.
6. Close: honest evals require knowing what part of the system produced the behavior.

### Structure C: practical eval lesson post

1. Hook: "If the agent is not in the loop, you are not measuring the agent."
2. Context: building AI TamperGuard for observability-tamper scenarios.
3. What failed: prompt variants changed metadata more than behavior.
4. What changed: separate seeded fixtures from live-agent/replay modes.
5. Why it matters: avoids claiming nondeterminism or determinism based on fixture artifacts.
6. Ask the network: how do others capture trajectory-level variation in agent evals?

## Possible hooks

Pick one. Do not combine all of them.

1. "I tried to measure nondeterminism in an uncensored agent and mostly found a deterministic harness."
2. "If the agent is not actually in the loop, you are not measuring the agent. You are measuring the fixture."
3. "A single agent run is a demo. Repeated runs are an eval. But only if the harness is honest."
4. "The result was not `agent deterministic`. It was `harness deterministic`. That distinction matters."
5. "This week’s AI eval lesson: identical outputs can mean the model is stable, or it can mean your pipeline quietly removed all the degrees of freedom."
6. "Prompt variants do not matter if the event generator ignores the prompt. Ask me how I know."

## Suggested draft post

Use this as raw material, not sacred text.

```text
I tried to measure nondeterminism in an uncensored agent and mostly found a deterministic harness.

That sounds like a failure, but it was actually the useful part.

I have been building AI TamperGuard, a lab dataset/eval project for studying observability-tamper behavior in Splunk/SOC workflows. One thing I wanted to test was whether repeated attempts across prompt variants would produce meaningfully different behavior.

So I ran a k=3 batch.

The result looked very stable:

- 80 scenario runs
- 315 Splunk-verified events
- 80 behavior windows
- 23 variant groups
- 22 stable groups
- 1 partially variable group

The tempting conclusion would have been:

"The uncensored agent is deterministic."

But that would have been wrong.

The better diagnosis was:

"My seeded evidence-generation path was too deterministic, and the agent was not really in the data-generation loop."

The prompt pack changed metadata and provenance, but much of the actual event generation came from deterministic scenario templates. So the harness was producing the same movie with a different filename.

That distinction matters.

If you want to evaluate nondeterministic agent behavior, you need to capture the actual trajectory:

- what the agent saw
- what tools it called
- what state changed
- what evidence it re-queried
- what final report it produced
- how that differs across repeated trials

Final rows are not enough if the rows were generated by fixtures.

The next AI TamperGuard pass separates generator modes more explicitly:

- seeded_template
- randomized_template
- agent_live
- agent_replay

And the metric shifts from "did the final table change?" to "did the trajectory change in a semantically valid way?"

This is the unglamorous part of AI evals: before making claims about a model, make sure the harness is measuring the model.

Tiny lobster note: sometimes the detector is fine and the tank is just full of rails.
```

## Shorter draft

```text
This week’s AI eval lesson:

If the agent is not in the loop, you are not measuring the agent.

I ran repeated k=3 tests in AI TamperGuard, my Splunk/SOC lab dataset for observability-tamper behavior. The output looked extremely stable: 22 of 23 scenario/variant groups produced stable behavior signatures.

The tempting claim was "the uncensored agent is deterministic."

The honest claim was "my harness was too deterministic."

The seeded scenario path was generating public-safe Splunk events from templates. Prompt variants changed metadata and provenance more than they changed the actual event trajectory.

So the next version separates:

- seeded fixtures
- randomized fixtures
- live agent runs
- replayed agent trajectories

And it measures trajectory signatures, not just final event rows.

Agent evals need repeated trials, tool traces, state deltas, and semantic checks. Otherwise you can accidentally benchmark the rails instead of the rider.
```

## Claim boundaries

### Safe to say

- AI TamperGuard is a lab dataset/eval project around observability-tamper behavior in Splunk/SOC workflows.
- The recent repeated-run test showed that the current seeded evidence-generation pipeline was highly stable.
- The current evidence does not justify saying the uncensored agent itself is deterministic.
- The useful finding was an eval harness diagnosis: the generator path was too deterministic and did not put the agent deeply enough in the loop.
- Future work should distinguish seeded templates, randomized templates, live agent trajectories, and replay.
- Serious agent evals need repeated trials and trajectory-level evidence.
- This is dataset/eval plumbing, not a production detector claim.

### Do not say

- Do not say Ryan proved uncensored agents are deterministic.
- Do not say this proves anything about all uncensored models.
- Do not say the system detects malicious AI behavior in production.
- Do not say Openclaw graded this run; it did not.
- Do not imply the dataset is already sufficient for supervised model-quality claims.
- Do not include raw SPL, usernames, hostnames, object names, internal IPs, URLs, tokens, raw prompt text, or private report text.
- Do not turn scenario-grounded labels into malicious ground truth.

## Suggested technical framing

Use this vocabulary:

- repeated-run eval
- `k=3` attempts
- trajectory signature
- behavior-window features
- seeded evidence-generation path
- fixture vs live-agent behavior
- generator mode
- semantic validity checks
- Splunk read-back
- lab dataset/eval plumbing

Avoid this vocabulary unless carefully qualified:

- deterministic agent
- malicious agent
- production detector
- jailbreak proof
- uncensored model benchmark
- autonomous insider threat
- real-world compromise

## Infographic or carousel idea

Title: **Agent evals: are you measuring the agent or the rails?**

Slide/card sequence:

1. **Goal** — Measure nondeterminism across repeated agent attempts.
2. **Result** — Most behavior signatures were stable across `k=3`.
3. **Trap** — Stability did not prove agent determinism.
4. **Root cause** — Deterministic seeded templates generated the events.
5. **Better design** — Capture trajectories: observations, tool calls, state deltas, reports.
6. **Next modes** — `seeded_template`, `randomized_template`, `agent_live`, `agent_replay`.
7. **Boundary** — Lab eval plumbing, not production detection.

Visual style: technical bento grid, dark graphite/navy, thin grid lines, blue/violet/amber accents. No hooded hackers, skulls, magic robots, fake Splunk screenshots, or vendor-dashboard cosplay.

## Good closing questions

Use one.

- "For people building agent evals: what do you compare across repeated runs — final answer, tool trace, state delta, or all of the above?"
- "Where do you draw the line between fixture-driven evals and live-agent evals?"
- "What is your favorite way to detect when an eval harness is accidentally removing the behavior you meant to measure?"
- "How are you storing agent trajectories for replay/regression without turning the dataset into soup?"

## Public safety notes

The post can mention abstract concepts and high-level counts. Keep implementation details safe.

Do not include:

- raw SPL
- raw usernames
- hostnames
- private app/object names
- URLs
- tokens
- HEC details
- internal IPs
- full prompt text
- private report text
- exact private index inventories beyond public-safe generic names

Prefer abstractions:

- `generator_mode = seeded_template`
- `generator_mode = agent_live`
- `trajectory_signature`
- `behavior_window_id`
- `object_type = saved_search`
- `actor_privilege_tier = admin_like`
- `evidence_agreement = false`

## Tone guidance

- Crisp, technical, plain English.
- Candid engineering lesson, not a victory lap.
- The punchline is intellectual honesty: the harness was deterministic, not necessarily the agent.
- A little humor is fine. Use one lobster/rails joke max.
- Avoid "thrilled to share," "game changer," "revolutionary," or "we solved AI security."
- Keep the claim boundary obvious without sounding defensive.

## Source context for the marketing agent

- Project repo: `/home/ryan/projects/ai-tamperguard`.
- Related prior handoff: `docs/linkedin-marketing-handoff-feature-collection.md`.
- Relevant plan: `docs/plans/2026-05-25-goal-nondeterminism-harness.md`.
- Recent baseline batch name: `full_live_v1_k3_fixed_20260525T204429Z`.
- Recent baseline raw export path referenced in prior planning: `v1/data/private/raw_exports/full_live_v1_k3_fixed_20260525T204429Z`.
- Keep in mind: current repo policy from Ryan is to document and track work publicly by default, while still avoiding secrets, tokens, credentials, and PII.

## Final instruction to the marketing agent

Write the post as an engineering confession with a useful takeaway:

> I thought I was measuring nondeterminism in the agent. I discovered I was mostly measuring determinism in the harness. That is exactly the kind of bug an eval should surface before anyone makes claims.

Keep the claws sharp. Keep the claims sharper.
