---
name: jamsession-use-agent-worksheet
description: Maintain a concise, checked-in worksheet as durable task state for repository changes, delegated work, multi-session work, or investigations needing a handoff. Use when this skill is installed unless the repository already defines another task-record convention; do not create one for a short read-only answer or trivial task.
---

# Use an Agent Worksheet

Keep one concise worksheet that lets another agent resume the task without
replaying chat transcripts or repeating discovery. Repository instructions and
an existing task-record convention take precedence over this skill.

## Start the worksheet

Create the worksheet before changing repository files when the work is
multi-step, delegated, expected to span sessions, or needs durable findings or
a handoff. For an ordinary repository change, create one unless the user or
repository explicitly waives it. Do not create one for a short read-only answer,
status check, or trivial task.

Use the repository's existing location and naming convention when present.
Otherwise create:

```text
.agents/worksheets/agent-worksheet-YYYY-MM-DD-short-task-slug.md
```

Use the task's local start date, a short lowercase hyphenated slug, and the full
date. If that path already exists for different work, append `-2`, `-3`, and so
on. Never overwrite another worksheet.

## Keep it useful

Record only durable task state:

- status: `ACTIVE`, `BLOCKED`, or `COMPLETE`
- task source and accepted requirements
- starting Git commit when available
- relevant findings and decisions
- plan and current progress
- agent sessions that made a useful contribution, with provider or transport,
  exact resumable identifier when exposed, role, and state
- files changed by repository-relative path
- commands, tests, reviews, and other decisive evidence
- blockers, remaining work, handoff, and final outcome

Preserve important user requirements and corrections accurately. Quote exact
language when its wording matters, but do not copy the entire conversation by
default. Link raw transcripts or session identifiers instead of reproducing
them. Keep failed approaches only when they prevent the next agent from wasting
time or explain a decision.

Update the worksheet at meaningful boundaries: after investigation, when the
plan or scope changes, after delegated results arrive, after validation, and
before handoff. It is task state, not a running narration.

## Coordinate ownership

For orchestrated work, the manager responsible for a ticket owns its worksheet.
Workers return concise evidence and handoffs to that manager rather than editing
one shared worksheet concurrently. The supervisor uses the worksheets as the
durable summary of queue state.

## Finish with the work

Mark the worksheet `COMPLETE` only when the requested implementation, required
validation and review, documentation, and handoff are complete. Otherwise leave
it `ACTIVE` or `BLOCKED` and state the exact next action.

Check the worksheet into Git with the associated work unless repository
instructions or the user say task records should remain local. Follow the
repository's authorization and commit conventions; this skill does not itself
authorize staging, committing, or pushing.
