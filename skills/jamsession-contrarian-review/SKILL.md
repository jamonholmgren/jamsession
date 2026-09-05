---
name: jamsession-contrarian-review
description: Ask an independent agent to make the strongest evidence-based case that a plan, diagnosis, or implementation is wrong. Use when the user requests a contrarian, adversarial, devil's-advocate, or assumption-challenging review; do not treat invented disagreement as a finding.
---

# Run A Contrarian Review With Jam Session

1. Identify the exact review target and state its intended outcome, evidence,
   assumptions, completed checks, and excluded scope.
2. Run `jamsession status` and choose an available model from a different family
   than the author. Choose provider, model, effort, and read access explicitly,
   then start a fresh session using `jamsession`.
3. Ask the reviewer to attack the strongest assumptions, trace failure cases,
   distinguish facts from guesses, and return concrete counterevidence. Require
   it to say `PASS` when it cannot support a meaningful objection.
4. Verify every objection against the source material. Contrarian posture is a
   search strategy, not evidence and not a requirement to manufacture conflict.
5. Resume the same session once when a claim needs focused challenge or when a
   revised target should be rechecked.
6. Return confirmed objections, rejected objections, unresolved uncertainty,
   and the provider, model, effort, and session ID used. Do not edit the target
   unless the user separately authorizes implementation.
