---
name: jamsession-model-recommendations
description: "Choose agent providers, models and effort using Jamon's recommendations when the caller has not specified them."
---

# Jam Session Model Recommendations

These recommendations are fresh as of October 5, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Run
`jamsession status`, then choose the provider, model, effort, and access level
explicitly from what is available. If the preferred model is unavailable, note
that to the user and choose a model from the same class in another family.

Here are Jamon's model recommendations, grouped into classes. A class names a model at a specific effort, so one model can appear in two classes. Within a class, "Best" means the best tradeoff of power against efficiency, not the most raw intelligence; "Good" choices also work, with a less favorable tradeoff.

Prefer each model's native harness. Cursor Grok (also called Crok or Croc) is the exception: treat it as native for both Grok and Cursor because xAI owns both.

## Known native models

Catalog snapshot: October 12, 2026. Models belong next to their native agent,
not every harness that can host them. This is an inventory, not a recommendation
or a guarantee of account availability. Effort, fast and contributor variants
are grouped; use `jamsession models <provider>` for exact installed IDs.

| Native agent | Known models and families |
| --- | --- |
| Codex / OpenAI | GPT-6.1 Sol; GPT-6 Astra, Sol and Luna; GPT-5.6 Sol, Terra and Luna. Other harness catalogs retain GPT-5.5, GPT-5.4 and Mini, GPT-5.3 Codex, GPT-5.2, GPT-5.1 and GPT-4.1; these are legacy, not necessarily available in Codex. |
| Claude / Anthropic | Opus 5.5, 5, 4.8, 4.7, 4.6 and 4.5; Fable 6.1, 5.1 and 5; Sonnet 5.5, 5 and 4.6; Haiku 5.5 and 4.5. Some known families are omitted by the installed picker. |
| Grok / xAI | Grok 4.7 (including build-fast), 4.6 and 4.5. Crok/Croc uses these through Cursor; do not duplicate their catalog under Cursor. |
| Cursor | Composer 2.5 (including fast). Cursor also has access to other providers' models. |
| Devin / Cognition | SWE-2, SWE-1.7, SWE-1.7 Lightning and SWE-1.6 (including fast). Adaptive selects models; Fusion combines models rather than naming a separate native model. Devin also has access to other providers' models, including through Fusion. |
| Muse / Meta | Muse Wonder 1.0; Muse Spark 1.3 and 1.2 (including contributor variants). |
| Copilot / GitHub | A multi-model harness; no separate GitHub-native base model is identified here. |
| Antigravity / Google (custom adapter) | Gemini 3.8, 3.7, 3.6 and 3.5 Flash; Gemini 3.1 Pro and Gemini 3 Flash are also known from harness catalogs. Verify the installed Google agent's catalog; the custom adapter is not bundled. |

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

* Best: Claude Sonnet 5.5 high, Grok high (including Cursor Grok), GPT-6.1 Sol low
* Good: GPT-6 Luna max, Devin SWE-2 high

## Cheap

Good for narrowly focused implementation, low-priority work, and conserving tokens. Never use cheap models for diagnosis: once the data is gathered, diagnosis belongs to the premium class.

* Best: Devin SWE-2 max, Muse spark, GPT-6 Luna xhigh
* Good: Antigravity, Copilot
* Do not use Claude Haiku

Weaker implementers are fine as long as review and verification eventually get the change right; do not move routine implementation up a class just to save review rounds.

## Notes

* As of October 12, Jamon considers Muse Wonder 1.0 at xhigh to be GPT-6.1 Sol-level
* Devin `swe-2-high` is the fallback when the Devin Fusion models return `resource_exhausted` (weekly quota). Briefs that pin a Fusion model should name it as the fallback
* There is no GPT-6 Terra, and GPT-5.6 Terra is weak; use GPT-6.1 Sol low in its place
* Devin's top SWE-2 effort is `swe-2-max` (there is no xhigh)
* `jamsession models <provider>` lists exact model IDs and efforts, including Codex
* GPT-5.5, Claude Sonnet before 5.5, and other older models are poor choices; use them only when a harness has nothing better

Unknown, haven't used enough:

* Gemini 3.8 Flash -- don't know enough about this
* GLM 5.3 (Flash) -- have heard good things about the GLM models, haven't used them

Users can copy this skill under another name and maintain their own model recommendations. Prefer user recommendations over Jamon's if present.
