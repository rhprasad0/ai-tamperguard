# LinkedIn marketing handoff: what AI TamperGuard should collect next

## Purpose of this handoff

Turn the AI TamperGuard feature-findings discussion into a LinkedIn post for Ryan Prasad.

The post should make the work legible to AI engineers, SOC engineers, detection engineers, recruiters, and technical hiring managers. It should sound like a builder explaining what he learned while designing a real eval/data pipeline, not like a vendor announcing a product.

This is not a victory-lap post. The useful angle is: the current TamperGuard rows are a skeleton, and the next dataset only gets interesting if it captures security-relevant context, deltas, and sequences.

## One-sentence thesis

For AI TamperGuard, the valuable signal is not just that an agent searched or modified something in Splunk; it is the surrounding story: what the agent looked at, what changed before and after, whether visibility or alerting was degraded, and whether protected evidence disagrees with the final report.

## Short version

AI TamperGuard is becoming a scenario-grounded dataset for observability tamper behavior in a Splunk/SOC lab.

The first dataset shape has useful atoms:

- actor
- action
- object
- surface
- status
- scenario/run IDs
- derived behavior windows

But those fields are only the starting point. Security people do not just care that a dashboard, saved search, alert, lookup, or report changed. They care what changed, who changed it, whether the actor had the right role, whether the change followed a suspicious search, whether alerts or evidence got suppressed, and whether another protected surface still tells the truth.

That is the post.

## Why this is interesting

The feature discussion ties AI/security engineering to things SOC teams already care about:

- Splunk audit activity: searches, logins/logouts, capability checks, admin actions, configuration changes, and knowledge-object changes.
- Detection engineering lifecycle: saved searches, alerts, dashboards, lookups, findings, intermediate findings, risk scores, detection versions, and suppression/throttle behavior.
- MITRE-style defense impairment and indicator-removal patterns: search/read, then modify/disable/delete/suppress, then requery or report.
- Insider-threat ML patterns: user/session/day/week windows plus ordered event sequences.

The core idea is practical: if AI agents are going to operate inside SOC/admin workflows, we need datasets that capture behavior stories, not just isolated log rows.

## Best LinkedIn angle

Use this angle:

> The boring-looking feature engineering is the security story.

That avoids hype. It also shows Ryan thinking like an AI engineer who understands security data, not someone sprinkling ML on logs and calling it a detector.

The post should say something like:

- I am building AI TamperGuard as a lab dataset around observability-tamper behavior.
- The current events are useful, but they are only the bones.
- The next pass needs before/after deltas, sequence features, object criticality, capability outcomes, alert/finding impact, and protected-vs-sacrificial evidence checks.
- That is what makes the data useful to security people.

Tiny lobster skeleton joke optional. Do not overdo it.

## Possible hooks

Pick one. Do not combine all of them.

1. "The feature I care about is not `action=modify`. It is what changed before and after."
2. "A Splunk event saying an agent modified a dashboard is not enough. The security question is: what did that modification hide?"
3. "I am learning that AI/SOC datasets need fewer magic labels and more boring context."
4. "For AI TamperGuard, the model is not the interesting part yet. The interesting part is deciding what evidence should exist."
5. "A tamper dataset built from isolated log rows is mostly a spreadsheet with anxiety. The signal is in the sequence."

## Recommended post structure

### Structure A: feature-story post

1. Hook: isolated events are not enough.
2. Context: AI TamperGuard is a Splunk/SOC lab dataset for observability-tamper behavior.
3. Problem: early rows capture actor/action/object/status, but that only gives the skeleton.
4. Better features: before/after state, sequence/order, object criticality, actor/capability context, alert/finding impact, evidence-chain completeness.
5. Security framing: this lines up with Splunk audit data, detection engineering, defense impairment, and insider-threat style sequence/window modeling.
6. Claim boundary: not claiming malicious ground truth or production detection.
7. Close: this is the kind of AI engineering work that makes the later model worth training.

### Structure B: "what changed?" post

1. Hook: `modify` is not a finding.
2. Explain: in a SOC, the important question is what changed and what evidence still exists.
3. Examples:
   - saved search enabled before/after
   - alert suppression added/removed
   - risk score changed
   - lookup row count changed
   - search-before-modify sequence
   - protected surface disagreed with sacrificial surface
4. Tie to AI agents: if agents operate in Splunk/admin workflows, we need datasets that model those deltas.
5. Boundary: this is dataset design, not a production detector claim.

## Suggested draft post

Use this as raw material, not sacred text.

```text
The feature I care about is not `action=modify`.

It is what changed before and after.

I have been building AI TamperGuard, a lab dataset for studying observability-tamper behavior in Splunk/SOC workflows. The early event shape is intentionally simple:

- actor
- action
- object
- status
- source surface
- scenario/run ID

That is useful, but it is just the skeleton.

A security engineer usually does not care that "a dashboard changed" in isolation. They care about the surrounding story:

- Was the actor admin-like, analyst-like, service-account-like, or an AI agent?
- Did the actor search for evidence before changing the object?
- Was a saved search disabled, rescheduled, throttled, or suppressed?
- Did a lookup shrink after the agent read it?
- Did a risk score or finding count drop?
- Did a protected audit/config surface still preserve the truth?
- Did the final report disagree with the evidence chain?

That is where the dataset starts to become useful.

The next AI TamperGuard pass needs less "magic label" energy and more boring security context:

- before/after state
- search -> modify -> report sequences
- object criticality
- capability outcomes
- alert/finding suppression impact
- protected-vs-sacrificial evidence agreement
- baseline rarity once there is enough benign volume

This lines up with normal SOC/SIEM practice: Splunk audit activity, detection lifecycle changes, defense-impairment patterns, and insider-threat style user/session windows.

Important boundary: I am not claiming this is malicious ground truth or a production detector.

Right now, the work is dataset/eval plumbing. The goal is to build rows that a security person would recognize as meaningful before asking a model to learn from them.

Tiny lobster skeleton is anatomically correct. Not yet dinner.
```

## Shorter version

```text
I am learning that AI/SOC datasets need fewer magic labels and more boring context.

For AI TamperGuard, an event like `action=modify` is not enough.

The useful questions are:

- What changed before and after?
- Did the actor search first?
- Was alerting, logging, risk scoring, or evidence visibility degraded?
- Did a protected audit/config surface preserve a different version of the story?
- Was this normal admin behavior, a denied probe, a hard negative, or tamper-congruent behavior?

That means the next dataset pass needs features like before/after state, search -> modify -> report sequences, object criticality, capability outcomes, alert/finding impact, and evidence-chain completeness.

This is not a production detector claim. It is the boring-but-necessary part before model training: deciding what evidence should exist.
```

## Claim boundaries

### Safe to say

- AI TamperGuard is a lab dataset/eval effort around observability-tamper behavior.
- The current rows are a minimum viable skeleton.
- The feature direction maps to SOC/SIEM practice, Splunk audit activity, detection lifecycle changes, MITRE-style defense impairment, and insider-threat sequence/window modeling.
- The next useful features are contextual deltas, sequence/order, object criticality, capability outcomes, alert/finding impact, evidence-chain completeness, and later baseline rarity.
- The work is about creating meaningful trainable/evaluable rows before making model-quality claims.

### Do not say

- Do not say this detects malicious insiders.
- Do not say it proves production tamper detection.
- Do not say the dataset already contains enough live Splunk evidence for model-quality claims.
- Do not imply private Splunk data, raw SPL, usernames, hostnames, object names, URLs, tokens, prompts, or reports are public.
- Do not turn weak or scenario-grounded labels into malicious ground truth.
- Do not present the feature backlog as already implemented if the post is about findings/design direction.

## Feature backlog to mention

If the marketing agent wants a concrete list, use this order:

1. Before/after state
   - enabled/scheduled before and after
   - suppression/throttle added or removed
   - risk score or finding count changed
   - lookup row count changed
   - query/config hash changed

2. Sequence and timing
   - search -> modify -> report
   - read -> disable
   - denied probe -> next action
   - requery after modification
   - time gaps between stages

3. Object criticality and lineage
   - detection vs dashboard vs lookup vs report
   - visibility-control object
   - evidence-source object
   - version/hash/change magnitude

4. Actor and capability context
   - analyst-like vs admin-like vs service account vs AI agent
   - privilege tier
   - capability checked
   - allow/deny result
   - permission-denied count

5. Alert/finding suppression impact
   - finding count before/after
   - suppression rule created
   - throttle window changed
   - notable visibility changed
   - risk modifier changed

6. Evidence-chain completeness
   - expected vs observed evidence count
   - protected surface seen
   - sacrificial surface seen
   - protected/sacrificial agreement
   - contradiction flag

7. Baseline and peer rarity
   - actor/action rarity
   - actor/object rarity
   - peer-group rarity
   - object-modification rarity
   - sequence rarity

## Public/private safety notes

The post can mention abstract feature families, but should not reveal or imply any private lab identifiers.

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

- `search_scope_family = audit_surface`
- `object_type = dashboard`
- `object_criticality = high`
- `change_magnitude = medium`
- `actor_privilege_tier = admin_like`
- `search_result_count_bucket = 10_100`

## Tone guidance

- Crisp, technical, plain English.
- Builder with receipts, not hype goblin.
- A little humor is good. Keep the lobster restrained unless the post is intentionally playful.
- Avoid "thrilled to share," "game changer," "revolutionizing," or "AI-powered security transformation." The SOC lobster will pinch us.
- Do not write like a vendor whitepaper.
- Do not over-explain Splunk. Mention enough that practitioners recognize the surfaces.
- Make the claim boundary obvious without sounding defensive.

## Good closing questions

Use one.

- "For people who build SOC/detection datasets: what before/after fields do you wish logs preserved more cleanly?"
- "If you were modeling observability tamper behavior, would you prioritize deltas, sequences, or peer-baseline rarity first?"
- "What is the most useful feature you have seen for distinguishing harmless admin changes from evidence-laundering behavior?"

## Source context for the marketing agent

- Project: AI TamperGuard.
- Current repo: `/home/ryan/projects/ai-tamperguard`.
- Existing v0 handoff style reference: `v0/docs/linkedin-marketing-handoff-v0.md`.
- Relevant docs:
  - `docs/finished-dataset-requirements.md`
  - `docs/scenario-design.md`
  - `docs/v1-dataset-spec.md`
  - `docs/v1-dataset-implementation-plan.md`
  - `v1/docs/data_dictionary.md`
  - `v1/docs/known_limitations.md`
  - `v1/docs/redaction_methodology.md`

## Final instruction to the marketing agent

Write the post as if Ryan is explaining an engineering judgment call he just made:

> The dataset is not useful because it has labels. It becomes useful when the rows preserve enough security context for a human analyst to understand the behavior story.

That is the signal. Keep the claws sharp, keep the claims honest.
