# Quiet Agent Coordination

Status: COMPLETE
Starting HEAD: 59c1fc1b9e90603856ac0f31b0480f9e9b1d55ae

## Request and scope

Jamon asked to add stricter messaging rules after a friend reported excessive
inter-agent status chatter. Gunship's night-shift contracts already require
material-event-only communication and mechanical waiting without inference.
Jam Session discourages polling, but does not explicitly prohibit routine
narration or acknowledgement loops. The friend's actual transcript is unavailable;
this is a requested guidance improvement, not a verified diagnosis of that run.

Update only the orchestration, individual worker, and summon skills. Keep real
blockers, requested planning/review exchanges, checkpoints and handoffs useful.
Do not change the CLI or add scheduling machinery. Jamon subsequently asked
"Push when done." Commit and push only this scoped guidance change; preserve
the pending Muse fix and unrelated Antigravity adapter.

## Plan

Require quiet execution between material events. Do not ask agents to answer
notifications or acknowledge acknowledgements. Keep waiting mechanical and
respect explicitly requested reporting cadence. Validate the changed packages
and review realistic communication cases; refresh only already-installed copies.

## Outcome and validation

Updated the three owning skills with material-event-only messaging, batching
non-urgent findings, no courtesy replies or acknowledgement loops, mechanical
waiting, and explicit cadence/planning/review exceptions. Summon now requests a
return route only for an actual answer or handoff, not every notification.

All three packages pass the system skill validator and `git diff --check`.
Static scenario review: routine progress and acknowledgements require no reply;
real blockers and urgent shared risks are reported immediately; agreed evidence
checkpoints, review verdicts, and deliberate planning rounds remain valid.
This is guidance review, not an observed behavioral test of the friend's agents.
No CLI changes or runtime tests were needed for this prose-only patch.

Refreshed the already-installed global summon skill from local source; its bytes
match. Orchestrator and worker are not installed globally, so were not added.
Gunship's checked-in copies are unchanged. Files owned by this change:
`skills/jamsession-orchestrate-agent-work/SKILL.md`,
`skills/jamsession-individual-worker-workflow/SKILL.md`,
`skills/jamsession-summon-agent/SKILL.md`, and this worksheet.
