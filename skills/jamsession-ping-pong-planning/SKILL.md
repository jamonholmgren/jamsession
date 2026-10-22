---
name: jamsession-ping-pong-planning
description: "AKA PPP, planning panel or Noble Court: develop analysis, plans, or high-powered reviews through cross-model drafts and challenge rounds; not Peasant Mob or routine single-agent work."
---

# Ping-Pong Planning (PPP) With Jam Session

Use this planning panel for analysis, planning, or high-powered review. Apply
best-in-class intelligence to a problem, or get stronger reasoning from cheaper
models by having them challenge and improve each other's work.

The premium Astra/Opus planners with native Grok as contrarian are nicknamed
**Noble Court**; use `jamsession-model-recommendations` for that roster. This is
the same PPP workflow and requested round count (default one), not Peasant Mob's
eight-lane, two-feedback-round minimum.

Before starting, resuming or messaging panelists, use `jamsession-summon-agent`
for provider consent and caller-visible launch context.

1. Establish the problem, desired outcome, verified context, requested round
   count, and final decision owner. Default an omitted count to one.
2. Run `jamsession status` and choose two available planners from different model
   families. Noble Court adds native Grok as a separate contrarian alongside
   the Astra/Opus planners; use the recommended roster. Choose provider, model,
   effort, and safe access explicitly under the summon skill.
3. Start both planners in fresh sessions with the same evidence. Ask each for an
   independent analysis, plan, or review before showing either agent the
   other's reasoning. If using Noble Court, also give Grok that evidence in a
   fresh session for an independent adversarial critique, not a deciding vote.
4. Compare both contributions against the evidence and form one candidate.
   Include the contrarian's findings when present. Resolve factual disagreements
   by inspection rather than model reputation or voting.
5. For each requested round, resume one session to challenge the candidate,
   then resume the other to integrate only supported corrections. For Noble
   Court, collect Grok's independent challenge to that same candidate before
   integration. Preserve the planners' and contrarian's session IDs throughout.
6. Return one coherent analysis, plan, or review with material disagreement,
   remaining decisions, completed round count, and the providers, models,
   efforts, and session IDs actually used. Do not claim a round completed
   unless both halves finished.
