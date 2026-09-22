---
name: jamsession-model-recommendations
description: Consult Jamon's model recommendations when choosing a provider, model, and effort for agent work. Use when the caller has not already made that choice.
---

# Jam Session Model Recommendations

These recommendations are fresh as of September 22, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Run
`jamsession status`, then choose the provider, model, effort, and access level
explicitly from what is available. If the preferred model is unavailable, note
that to the user and choose an equivalent model tier from another family.

Here are Jamon's model recommendations, in order of usefulness and preference. They're balanced for best token efficiency vs results.

Prefer each model's native harness. Cursor Grok (also called Crok or Croc) is the exception: treat it as native for both Grok and Cursor because xAI owns both.

* Claude Opus 5.5 - preferred top-tier model for planning, difficult technical problems, and broad work. It replaces Fable 5.1 and earlier Opus models for most tasks, and costs less than both. Use it extensively; its design ability relative to Fable 5.1 is still an open question
* GPT-6 Astra - strong top-tier alternative for planning, difficult technical problems, and design-sensitive UI work
* GPT-6 Sol - preferred supervisor, manager, high-level synthesizer, integration judge, and daily driver. It replaces GPT-5.6 Sol and is better and cheaper; use light or medium for most work and high for harder or broad architectural work
* Grok 4.6 or Cursor Grok 4.6 - preferred sustained implementer for long-running, well-scoped work and routine iteration. Give it bounded batches, explicit acceptance evidence, and infrequent checkpoints rather than continuous supervision. Use high or xhigh for difficult implementation and medium when speed matters more than judgment. Keep choosing 4.6 over Grok 4.7 for now: 4.7 has been slower and less capable in Jamon's use
* GPT-6 Luna - recommended at max for short codebase investigations, tracing ownership, gathering evidence, and tightly specified small changes. It replaces GPT-5.6 Luna and Terra for their previous uses. Keep the coordinating model focused on synthesis instead of repeating its discovery
* Cursor's Kimi K3 - useful for contrarian review, fan-out audits, and applying well-specified focused work
* Claude Fable 5.1 - still excellent for UI design. Consider it when design quality is central until Opus 5.5's design ability is clearer; otherwise prefer Opus 5.5
* GPT-5.5, Claude Sonnet 5.x, 5.4, 5.3 spark - use only when a harness has no better options available; these are poor choices compared with the models above

Unknown, haven't used enough:

* Gemini 3.8 Flash -- don't know enough about this
* GLM 5.3 (Flash) -- have heard good things about the GLM models, haven't used them

Users can copy this skill under another name and maintain their own model recommendations. Prefer user recommendations over Jamon's if present.
