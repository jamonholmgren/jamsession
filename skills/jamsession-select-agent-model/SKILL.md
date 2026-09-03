---
name: jamsession-select-agent-model
description: Choose an explicit provider, model, and effort for Jam Session work using native availability plus one named recommendation pack. Use before dispatching costly review, implementation, or panel work; do not use when the caller already fixed the provider, model, and effort.
---

# Select An Agent Model With Jam Session

1. State the role you are staffing, why it is worth a separate agent, and what
   evidence the result must survive. Skip this skill when the caller already
   named the provider, model, and effort.
2. Establish availability from the providers themselves, not from advice:

   ```text
   jamsession doctor
   jamsession models <provider>
   ```

   A pack row is not evidence that a model exists or that its account is
   authenticated.
3. Name the recommendation pack you intend to consult, then read only it:

   ```text
   jamsession packs
   jamsession recommend <pack> [role] [provider]
   ```

   There is no default pack. If you cannot name one, decide without a pack and
   say so.
4. Read the pack's `#` metadata before its rows. Recommendations are dated
   advice from one author under one subscription mix, so treat every row as a
   candidate to check rather than an instruction to follow.
5. Prefer model-family diversity where independence is the point: independent
   review, contrarian review, and panels. Prefer a single strong model where
   continuity or a single coherent judgment matters more than breadth.
6. Choose one provider, model, effort, and access level, then pass them
   explicitly to `jamsession run`. A recommendation never becomes an implicit
   default: the run command still requires every value from you.
7. When a chosen model is unavailable, unauthenticated, or rejected by its
   adapter, treat that as a result. Make a new explicit choice rather than
   downgrading effort or swapping families silently.
8. Report the provider, model, effort, and session ID actually used, the pack
   consulted, and every substitution with its reason.

Packs describe what worked before. Availability, authorization, and the
correctness of the result remain yours to verify.
