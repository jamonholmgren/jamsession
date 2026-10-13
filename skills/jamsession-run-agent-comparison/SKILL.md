---
name: jamsession-run-agent-comparison
description: "Design, run or evaluate controlled coding-agent comparison trials."
---

# Run an Agent Comparison

Use concise plain English. Keep planning quality, implementation quality,
observable process, rework, availability and cost separate.

## Choose the authorized scope

Loading this skill authorizes no calls, trials, reviews, retries or publication.
Use the user's existing authorization: design only, evaluate existing evidence,
or execute a bounded experiment. Do not turn a recommendation request into a
benchmark. Recommendation edits remain proposals unless separately authorized.

Keep one coordinator for the manifest, dispatch ownership and result accounting.
Follow the caller's task-record and runner rules. Recover existing state before
starting more work; never duplicate a live cell or adopt another owner's work.

## Prepare before dispatch

Read [experiment design](references/experiment-design.md) for task selection,
source access, model settings, receipts and closeout. Read
[scoring](references/scoring.md) before designing or evaluating an experiment.

Start with source-only planning. Default to five fresh independent trials per
model/harness/effort condition per task. A user-selected three-trial budget is
exploratory and weak evidence about consistency. Implementation is an optional,
separately authorized mode with isolated writers and frozen acceptance checks.

Copy [the manifest](assets/experiment-manifest.json) into the caller's evidence
folder and fill it before launch. Freeze tasks, source, rubric, conditions,
counts, limits, access, writes, outputs and retry rules. Every remaining null is
unfilled; resolve it and conditional prerequisites before launch. Hash inputs.

Freeze the rubric and source-verified criteria before candidate outputs exist.
Candidates receive the task and common constraints, never expert checklists,
reference answers, other submissions, scores or identity maps. Source comparators
are evidence to verify, not a mandatory solution or architecture.

Verify native model and effort capabilities without inference where possible.
Record requested versus effective settings; missing telemetry stays unverified.
No silent backend, model or effort substitution, quota reset, authentication or
global spend-setting change is permitted by this workflow.

## Use the relevant templates

Copy and fill only the templates needed for the authorized stage:

- [Coordinator brief](assets/coordinator-prompt.md): manifest and dispatch owner.
- [Planning candidate](assets/candidate-planning-prompt.md): identical source-only
  task envelope, fresh sessions, assigned plan output or final stdout.
- [Rubric author](assets/rubric-author-prompt.md): pre-output source-grounded
  anchors and private expert criteria.
- [Blind grader](assets/grader-prompt.md): two independent premium reviewers
  from different model families, without author identity or process telemetry.
- [Results report](assets/results-template.md): caller-owned summary, coverage,
  uncapped quality, confirmed distinct flaws and honest cost limits.

For a requested assisted planning experiment, also read
[panel protocol](references/panel-protocol.md) and use the
[panel review template](assets/panel-review-prompt.md). Do not add panels to an
ordinary solo comparison. Assisted finals are a separate cohort.

## Evaluate and preserve

Use frozen 100-point category scores and independent blind reviews. An independent
adjudicator without the identity map locks scores and defects before unblinding.
Do not apply an essential-flaw score ceiling or extra arithmetic penalties for
defect counts. Record distinct confirmed defects per plan;
Perfect means zero confirmed defects of any severity after complete review with
no unresolved claims. Missing evidence is not perfection.

Inspect only observable public outputs and tool activity, never hidden reasoning.
Preserve original artifacts, receipts and ratings. Separate infrastructure
failures from quality; unavailable submissions have no quality score.

Tiers, if requested, use a predeclared relative-quality interpretation informed
by task evidence. Do not invent reputation anchors, force a distribution or
change tier meaning after seeing results. Label close ties and sparse evidence;
leave insufficient evidence unplaced. Later user-requested changes are explicit
post-hoc amendments with the earlier presentation preserved.

## Results belong to the caller

The caller owns results. Keep criteria, identity maps, reviews and other plans
physically outside candidate-readable snapshots, even in an ignored evidence
home. There is no required shared results file. Restrict private evidence access.
Sharing, publishing or committing results requires separate authorization and
a redaction check.

Account for every authorized cell and owned process, preserve evidence hashes,
verify source/index/untracked changes, and return runners through their owning
workflow. Report missing work and unresolved ownership honestly. This skill does
not authorize product integration or unrelated cleanup.
