# Scoring and reporting

## Freeze criteria before seeing candidates

Start source-only planning with this 100-point rubric. Fill task-specific anchors
for full, partial and poor credit before dispatch; preserve the version/hash.

| Category | Points | Evidence |
|---|---:|---|
| Correctness and requirements | 35 | Required behavior, causal reasoning, preserved invariants |
| Ownership and source grounding | 25 | Real callers, data ownership, lifecycle and integration paths |
| Simplicity and scope | 15 | Small coherent change, justified abstractions, no unrelated work |
| Actionable sequence | 10 | Concrete edits and dependency-aware steps without arbitrary ordering |
| Discriminating verification | 10 | Proposed checks distinguish success from the actual failure |
| Honest uncertainty | 5 | Observations, hypotheses, assumptions and unrun work distinguished |

The rubric author verifies criteria against actual source paths and callers.
Reference solutions and experts can be wrong. Retain rejected criteria and
source reasons; do not require a named helper, exact architecture or historical
step order when a valid alternative meets the behavior. An unresolved hypothesis
with a measurement-before-edit gate is not a confidently selected wrong fix.
Source-only verification proposals receive credit as proposals, never as passes.

## Blind independent evaluation

Freeze each complete submission and assign an opaque ID through a private map.
Remove identifying model/provider/session details wherever they occur, including
body text and artifact paths. Use neutral output IDs and paths from the start.
Keep a private removal log with original/redacted hashes and locations. Preserve
substantive meaning; if identity cannot be removed without changing meaning,
qualify the artifact and resolve access before grading rather than silently edit it.
Keep author, effort, cost, traces, other ratings, historical answers and reputation
out of quality-review inputs. Give two fresh independent premium reviewers from
different model families the same task, source, artifact and frozen rubric.
If either identity leaks, qualify that rating and obtain a clean authorized
review before using it as primary; preserve the contaminated original.

Use category sums, not a denominator or a prose number, as raw quality. The
primary result is the mean of two complete valid reviews. An independent
adjudicator who has never seen the private map, dispatch identity or revealing
traces settles disputes using only opaque artifacts, task, source, frozen rubric
and blind reviews. The dispatch/map custodian must not make final quality or
defect decisions. Lock final scores and the confirmed-defect ledger before
unblinding results for aggregation; preserve the lock artifact/hash.

Predeclare allowed overrides in the manifest: source-verified factual or category
application errors, demonstrable arithmetic/extraction errors, or exclusion of a
review contaminated by identity, missing required access or incomplete coverage.
Record the affected category, evidence, prior points and correction. Replacement
reviews require existing authorization; if unavailable, mark coverage qualified
or pending under the frozen policy, never fabricate a second rating. Reputation,
preferred rankings and cost cannot justify overrides. Trigger blind adjudication
for essential-defect disagreement or a score gap greater than ten points; do not
vote or average away a concrete contradiction. Unresolved claims stay pending.

There is no essential-defect score cap and no additional numeric deduction for
Flaws, essential counts or imperfect frequency. The rubric already assesses
quality. Preserve raw reviews, category points, adjudicated score and reasons
separately; never rewrite history to match the final display.

## Distinct defect ledger

Read complete primary reviews, not issue excerpts. For each plan keep accepted
confirmed defects, rejected claims, merged duplicates and unresolved claims.
Each accepted defect needs a concise description, ordinary/essential severity,
plan/source evidence with path and location, and the adjudication basis.

Merge repeated descriptions of the same underlying defect across reviewers or
categories. Separate independently failing paths that need distinct corrections;
explain the boundary rather than multiplying one failure into several symptoms.
A missing test for an already-counted product defect is not automatically a second
defect. Count an independent verification gap only when it omits a distinct,
necessary assertion. Optional ideas, generic absent topics and rejected claims
do not count. Missing an exact function name is not a defect by itself.

Essential means a concrete selected design loses required behavior or cannot
fulfill the task. Check the whole plan for a broader valid dispatch, guard,
conditional investigation or alternative architecture before confirming it.
Neither a reviewer marker nor a plan-level flag establishes every defect's
severity. Escalate uncertain cases to the independent blind adjudicator.

Perfect is true only after complete review, no unresolved claims and zero
confirmed distinct defects of any severity. A plan without essential defects
can still be imperfect. Incomplete review or unresolved claims cannot be called
Perfect. Flaws is the sum of each plan's distinct confirmed defects. Essential
flaws are a subset, not an extra addition. These counts describe reviewed evidence,
not proof that undiscovered defects are absent.

## Compare quality without disguising uncertainty

Report per-task mean, median, range, worst, sample coverage, Perfect and Flaws.
Unavailable or partial submissions have no quality score; report availability
separately. If an overall score is requested, predeclare equal task-mean weights
or justified alternatives. Do not pool unequal task samples into an accidental
weighting, infer missing task scores or mix assisted finals into solo means.

If tiers are requested, freeze their interpretation before candidates: relative
planning quality for the tested tasks, informed primarily by rubric quality and
specific source patterns. Use all S/A/B/C/D/F labels, leave empty tiers empty and
insufficient evidence unplaced. Do not force a distribution, import model
reputation anchors or switch between relative quality and functional readiness.
Small close differences are not established population differences. Functional
failures remain explicit findings even in a relatively high tier. A later
user-requested calibration is post-hoc: preserve the prior map and explain the
changed interpretation; do not pretend new scoring evidence was collected.

## Observable process and cost

Evaluate public messages and tool calls separately from blind quality. Distinguish
corrected hypotheses and normal exploration from unresolved false claims,
repeated dead ends or rule violations. Do not infer hidden reasoning or turn
infrastructure errors into cognitive failures. Use qualitative process findings
unless an observable numeric process rubric was frozen in advance.

Report wall time and exposed input/cache/output/reasoning token counters with
their native definitions. Cache may already be included in input and reasoning
in output; do not double-count. Session context size is not cumulative billing.
Separate candidate, review, rework and waiting cost. Missing telemetry is unknown,
not zero. Quote dollars only from verified applicable pricing and comparable
usage, with date and assumptions; subscription quota is not API-equivalent cost.
