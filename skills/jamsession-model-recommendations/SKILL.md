---
name: jamsession-model-recommendations
description: Consult Jamon's model recommendations when choosing a provider, model, and effort for agent work. Use when the caller has not already made that choice.
---

# Jam Session Model Recommendations

These recommendations are fresh as of October 5, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Run
`jamsession status`, then choose the provider, model, effort, and access level
explicitly from what is available. If the preferred model is unavailable, note
that to the user and choose a model from the same class in another family.

Here are Jamon's model recommendations, grouped into classes. A class names a model at a specific effort, so one model can appear in two classes. Within a class, "Best" means the best tradeoff of power against efficiency, not the most raw intelligence; "Good" choices also work, with a less favorable tradeoff.

Prefer each model's native harness. Cursor Grok (also called Crok or Croc) is the exception: treat it as native for both Grok and Cursor because xAI owns both.

## Premium

Expensive, with the best results. Use for ping-pong planning and hard problems.

* Best: Claude Opus 5.5 xhigh, GPT-6 Astra medium
* Good: Claude Fable 6.1 high, GPT-6 Astra high. Both are great but expensive; xhigh is not worth it

## Daily drivers

Good interactive models and supervisors.

* Best: Claude Opus 5.5 medium, GPT-6.1 Sol medium
* Good: GPT-6 Astra low

## Mid-levels

Good for babysitting external workers, implementation work, and contrarian review.

* Best: Claude Sonnet 5.5 high, Grok high (including Cursor Grok), GPT-6 Terra high
* Good: GPT-6 Luna max, Devin SWE-2 high

## Cheap

Good for narrowly focused implementation, low-priority work, and conserving tokens. Never use cheap models for diagnosis: once the data is gathered, diagnosis belongs to the premium class.

* Best: Devin SWE-2 xhigh, Muse spark, GPT-6 Luna xhigh
* Good: Antigravity, Copilot
* Do not use Claude Haiku

Weaker implementers are fine as long as review and verification eventually get the change right; do not move routine implementation up a class just to save review rounds.

## Notes

* Devin `swe-2-high` is the fallback when the Devin Fusion models return `resource_exhausted` (weekly quota). Briefs that pin a Fusion model should name it as the fallback
* GPT-5.5, Claude Sonnet before 5.5, and other older models are poor choices; use them only when a harness has nothing better

Unknown, haven't used enough:

* Gemini 3.8 Flash -- don't know enough about this
* GLM 5.3 (Flash) -- have heard good things about the GLM models, haven't used them

Users can copy this skill under another name and maintain their own model recommendations. Prefer user recommendations over Jamon's if present.
