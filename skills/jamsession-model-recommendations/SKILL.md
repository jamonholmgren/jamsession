---
name: jamsession-model-recommendations
description: Consult Jamon's model recommendations when choosing a provider, model, and effort for agent work. Use when the caller has not already made that choice.
---

# Jam Session Model Recommendations

These recommendations are fresh as of September 5, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Run
`jamsession status`, then choose the provider, model, effort, and access level
explicitly from what is available. If the preferred model is unavailable, note
that to the user and choose an equivalent model tier from another family.

Here are Jamon's model recommendations, in order of usefulness and preference. They're balanced for best token efficiency vs results.

* Claude Fable 5.x - preferred top-tier model for planning, genuinely sticky technical problems, and UI work that needs a strong design eye; expensive, so keep it out of routine implementation and orchestration and use lower effort unless the problem warrants more
* GPT-6 Astra - full Fable alternative for planning, sticky technical problems, and design-sensitive UI work; Jamon slightly prefers Fable when both are available
* GPT-5.6 Sol - preferred supervisor, manager, high-level synthesizer, and integration judge; use light or medium for most work and high for harder or broad architectural work
* Grok 4.6 or Cursor Grok 4.6 - preferred sustained implementer for long-running, well-scoped work and routine iteration. Give it bounded batches, explicit acceptance evidence, and infrequent checkpoints rather than continuous supervision. Use high or xhigh for difficult implementation and medium when speed matters more than judgment
* GPT-5.6 Terra and GPT-5.6 Luna - preferred for short codebase investigations, tracing ownership, gathering evidence, and tightly specified small changes. Keep the coordinating model focused on synthesis instead of repeating their discovery
* Kimi K3 - useful for contrarian review, fan-out audits, and applying well-specified focused work
* Claude Opus 5.x - useful as a read-only checkpoint reviewer and for UI design. Explicitly ask it to identify concrete defects and the simplest sufficient fixes; it must not expand scope, invent abstractions, or act as architect or manager. Use in place of Fable 5.x if no Fable usage remains
* GPT-5.5, Claude Sonnet 5.x, 5.4, 5.3 spark - useful for targeted implementation work where the result is known and for contrarian review when treated with low trust

Unknown, haven't used enough:

* Gemini 3.8 Flash -- don't know enough about this
* GLM 5.3 (Flash) -- have heard good things about the GLM models, haven't used them

Users can copy this skill under another name and maintain their own model recommendations. Prefer user recommendations over Jamon's if present.
