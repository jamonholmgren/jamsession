---
name: jamsession-council-panel
description: "AKA ping-pong planning (PPP), planning panel or Noble Court: develop analysis, plans, or high-powered reviews through cross-model drafts and revision rounds; not Peasant Mob or routine single-agent work."
---

# Council Panel With Jam Session

Use this panel for analysis, planning, or high-powered review: independent
drafts from different model families, then revision rounds where they
challenge and improve one candidate. "Council ×N" means N revision rounds;
default one.

Before starting, resuming or messaging panelists, use `jamsession-summon-agent`
for provider consent and caller-visible launch context.

1. Establish the problem, desired outcome, verified context, round count, and
   final decision owner.
2. Seat three premium models from different families when available: Fable,
   Astra and Neon xhigh (`jamsession route group:premium`, or a routes.toml
   panel such as `noble-court`). Wonder Full fills a seat when one is out. Run
   `jamsession status` and choose provider, model, effort, and safe access
   explicitly under the summon skill.
3. Start every seat in a fresh session with the same evidence. Ask each for an
   independent analysis, plan, or review before showing it the others'
   reasoning.
4. Compare the contributions against the evidence and form one candidate.
   Resolve factual disagreements by inspection rather than model reputation or
   voting.
5. For each round, resume each seat to challenge the candidate, then resume
   one seat to integrate only supported corrections. Preserve every seat's
   session ID throughout.
6. Return one coherent analysis, plan, or review with material disagreement,
   remaining decisions, completed round count, and the providers, models,
   efforts, and session IDs actually used. Do not claim a round completed
   unless every seat finished its part.
