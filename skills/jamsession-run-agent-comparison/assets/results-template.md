# {{EXPERIMENT_TITLE}}

Status/as-of: {{STATUS_AND_TIMEZONE}}
Owner-chosen evidence home: {{LOCATION}}
Frozen manifest/rubric/source hashes: {{HASH_REFERENCES}}
Authorized scope and task provenance: {{SCOPE_AND_PROVENANCE}}

## Current conditions

| Model | Harness | Effort | Feature | Bugfix | Overall | Scored | Perfect | Flaws |
|---|---|---|---:|---:|---:|---|---:|---:|
{{CONDITION_ROWS}}

Adapt task columns to the actual frozen tasks. Use em dashes for missing quality,
not zero. Overall uses the declared task-mean weights and is absent if required
task coverage is missing. Requested/effective settings and exceptions:
{{SETTINGS_EVIDENCE_OR_UNKNOWN}}

Perfect counts completely reviewed plans with no unresolved claims and zero
confirmed distinct flaws of any severity. Flaws is the sum of each plan's distinct
confirmed defects. Essential defects are a subset. Incomplete/unresolved reviews cannot
count as Perfect. Counts are reviewed findings, not proof of no hidden defects.

## Evidence and coverage

Authorized/dispatched/live/terminal/usable/graded/unavailable/pending:
{{COUNTS_WITH_DEFINITIONS}}

Per task, report mean, median, range, worst, actual n and intended target. Preserve
failed attempts and retry cohorts. Identify incomplete reviews and adjudications.
Source findings, distinct defect ledger and score provenance: {{EVIDENCE_LINKS}}
Blind review coverage, independent adjudication and pre-unblinding score/defect
lock hash: {{REVIEW_COVERAGE_AND_LOCK}}
Before/after source audits and process closeout: {{AUDITS_AND_OWNERSHIP}}

## Interpretation

{{PREDECLARED_RELATIVE_QUALITY_INTERPRETATION_AND_LIMITATIONS}}

If tiers were requested, use a separate Tier | Agents table, with all S/A/B/C/D/F
rows, empty rows allowed and insufficient evidence unplaced. Do not infer tiers
from reputation, force a distribution or quietly change their meaning. State
close ties and limited sampling. Quality scores are uncapped category assessments;
there is no additional arithmetic defect penalty. Preserve any post-hoc amendment
and its prior presentation. Keep functional failures visible separately.

## Assisted cohort, if authorized

{{SEPARATE_PANEL_TABLE_OR_OMIT_SECTION}}

Use Mode, task score, actual n, Perfect, Flaws, best constituent Seed and Gain.
Label Gain explicitly: final score minus the best of the constituent seeds
selected for lowest solo scores in a prior grading batch, not matched random
controls or a fresh blind paired estimate.
Keep membership/harness/settings, rounds and added work explicit. Single assisted
finals do not enter solo means. Targeted weakest-seed gains are observations, not
causal or population claims. Do not invent missing panel tasks or overall scores.

## Process and cost

{{PUBLIC_OBSERVABLE_FINDINGS_AND_NATIVE_TELEMETRY}}

Separate candidate calls, reviewer calls, sessions, accepted turns, rework and
waiting. Missing telemetry stays unknown. Explain cache/reasoning token overlap;
session context size is not cumulative billing. Use no common dollar estimate
without applicable pricing and comparable usage. Subscription quota differs from
API-equivalent estimates. No hidden reasoning is inspected or published.

## Preservation and sharing

Raw evidence and earlier cohorts: {{PRIVATE_RETENTION_RECORD}}
Report artifact hashes: {{PUBLIC_ARTIFACT_HASHES}}
Remaining work and limitations: {{REMAINING_WORK}}

This report belongs to the caller/project. Before any separately authorized
sharing or commit, remove private source, local identifiers/paths, secrets,
identity maps and expert checklists from the agreed public scope. Do not publish
a private evidence link merely because it exists in the local report.
