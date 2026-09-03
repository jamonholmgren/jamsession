---
name: jamsession-ping-pong-planning
description: Produce a plan through independent drafts and explicit cross-model challenge rounds using resumable Jam Session sessions. Use when the user requests ping-pong or cross-model planning; do not use for routine planning that does not benefit from a second model family.
---

# Ping-Pong Plan With Jam Session

1. Establish the planning question, verified context, requested round count,
   and final decision owner. Default an omitted count to one.
2. Run `jamsession doctor` and choose two available agents from different model
   families. Choose provider, model, effort, and read access explicitly.
3. Start both agents in fresh sessions with the same evidence. Ask each for an
   independent plan before showing either agent the other's reasoning.
4. Compare both plans against the evidence and form one candidate. Resolve
   factual disagreements by inspection rather than model reputation or voting.
5. For each requested round, resume one session to challenge the candidate,
   then resume the other to integrate only supported corrections. Preserve the
   same two session IDs throughout the rounds.
6. Return one coherent plan with material disagreement, remaining decisions,
   completed round count, and the providers, models, efforts, and session IDs
   actually used. Do not claim a round completed unless both halves finished.
