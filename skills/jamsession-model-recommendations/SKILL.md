---
name: jamsession-model-recommendations
description: Consult Jamon's model recommendations when choosing a provider, model, and effort for agent work. Use when the caller has not already made that choice.
---

# Jam Session Model Recommendations

These recommendations are fresh as of September 3, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Confirm that
the chosen model is currently available and note to the user if it is not.
Substitute with an equivalent model tier from another family.

Here are Jamon's model recommendations, in order of usefulness and preference. They're balanced for best token efficiency vs results.

* GPT-5.6 Sol - best general purpose model and supervisor/manager, used at light or medium for most work; high for harder or broad architectural work
* Claude Fable 5.x - use for targeted highly intelligent review, beautiful UIs; expensive, so preserve tokens, use lower effort levels unless doing architectural work
* Grok 4.6, GPT-5.6 Terra, Kimi K3 - good for contrarian review, babysitting long-running processes, fan-outs to audit code base, applying well-specified and focused work, or using as a daily driver if you're out of Sol tokens. Use high or xhigh for best results unless doing audits
* Claude Opus 5.x - useful for code review and UI design. Be careful with deeper system design; tends to overengineer. Use in place of Fable 5.x if no Fable usage left
* GPT-5.6 Luna, GPT-5.5, Claude Sonnet 5.x, 5.4, 5.3 spark - useful for targeted implementation work where the result is known and for contrarian review when treated with low trust

Unknown, haven't used enough:

* Gemini 3.8 Flash -- don't know enough about this
* GLM 5.3 (Flash) -- have heard good things about the GLM models, haven't used them

Users can copy this skill under another name and maintain their own model recommendations. Prefer user recommendations over Jamon's if present.
