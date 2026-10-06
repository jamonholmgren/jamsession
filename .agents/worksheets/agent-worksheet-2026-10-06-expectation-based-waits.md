# Expectation-Based Agent Waits

Status: COMPLETE
Starting HEAD: 6c00de70d49f5b6369215105acf5849719820a5d

## Request

Jamon asked supervisors, managers and babysitters to use `sleep n`, where n is
the expected number of seconds before checking child processes or subagents,
when that is the best way to avoid hovering. He authorized commit and push.

## Scope and plan

Add one shared rule to `jamsession-orchestrate-agent-work`, naming all three
roles. Prefer completion-aware harness waits when available; otherwise sleep
until a meaningful expected checkpoint and inspect owned evidence without a
status message. Keep long waits responsive and honor existing deadlines.
No new timer, polling loop, CLI behavior, or separate babysitter skill.

Gunship's babysitter acts as a manager under this shared skill. Its checkout is
on an in-progress feature branch with unrelated edits; leave it untouched.
Preserve the pending Muse fix and unrelated Antigravity adapter. Validate the
changed skill and statically review wait, early completion and timeout cases.

## Outcome and validation

Added one shared waiting section naming supervisors, managers and babysitters.
`sleep n` is the shell-job option, with n based on expected completion or a
meaningful checkpoint. Completion-aware waits remain preferred when available;
long waits must stay responsive, and sleep does not prove completion or extend
the task's deadline. Idle waiting requires no child status message or resume.

The system skill validator and `git diff --check` pass. Static scenario review
covers shell jobs, early completion/blocker notifications, useful independent
work, unchanged evidence, long interactive delays, and existing deadlines.
No runtime code changed; no agent-run experiment or runtime test was claimed.
Commit/push scope: this worksheet and the orchestration skill only.
