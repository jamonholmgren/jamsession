---
name: jamsession-ask-agent-panel
description: Ask a small panel of independent coding agents for complementary judgments, then synthesize and verify their claims. Use when the user requests an agent panel, several independent opinions, or a diverse multi-model review.
---

# Ask An Agent Panel With Jam Session

1. Identify one question or review target. Give every panelist the same facts,
   intended outcome, constraints, and requested answer format.
2. Choose three (or the user-specified amount) of available agents with distinct
   model families, different from your own if possible.
3. Start every panelist in a fresh session with explicit read access. Do not
   expose other answers during the independent round.
4. Collect complete answers, deduplicate concrete claims, and preserve which
   session first raised each one. Agreement indicates where to inspect; it does
   not prove correctness.
5. Verify claims against available evidence. If material disagreement remains,
   resume the same sessions for one anonymized challenge round, then stop when
   each claim has a disposition.
6. Return a synthesis rather than a transcript: supported conclusions,
   rejected claims, real disagreement, residual uncertainty, and the providers,
   models, efforts, and session IDs used.
