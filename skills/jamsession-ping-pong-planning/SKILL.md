---
name: jamsession-ping-pong-planning
description: "AKA PPP or planning panel: develop analysis, plans, or high-powered reviews through requested cross-model drafts and challenge rounds; not routine single-agent work."
---

# Ping-Pong Planning (PPP) With Jam Session

Use this planning panel for analysis, planning, or high-powered review. Apply
best-in-class intelligence to a problem, or get stronger reasoning from cheaper
models by having them challenge and improve each other's work.

Before starting, resuming or messaging panelists, use `jamsession-summon-agent`
for provider consent and caller-visible launch context.

1. Establish the problem, desired outcome, verified context, requested round
   count, and final decision owner. Default an omitted count to one.
2. Run `jamsession status` and choose two available agents from different model
   families. Choose provider, model, effort, and read access explicitly.
3. Start both agents in fresh sessions with the same evidence. Ask each for an
   independent analysis, plan, or review before showing either agent the
   other's reasoning.
4. Compare both contributions against the evidence and form one candidate.
   Resolve factual disagreements by inspection rather than model reputation
   or voting.
5. For each requested round, resume one session to challenge the candidate,
   then resume the other to integrate only supported corrections. Preserve the
   same two session IDs throughout the rounds.
6. Return one coherent analysis, plan, or review with material disagreement,
   remaining decisions, completed round count, and the providers, models,
   efforts, and session IDs actually used. Do not claim a round completed
   unless both halves finished.
