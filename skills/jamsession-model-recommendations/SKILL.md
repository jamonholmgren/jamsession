---
name: jamsession-model-recommendations
description: "Choose agent providers, models and effort using Jamon's recommendations when the caller has not specified them."
---

# Jam Session Model Recommendations

These recommendations are fresh as of October 13, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Run
`jamsession status`, then choose the provider, model, effort, and access level
explicitly from what is available. If a default is unavailable, use a listed
alternative when possible and report the change.

Choose by the work being done. Each entry names a model at a specific effort;
defaults are preferred routes, and alternatives are acceptable for that role.
Task defaults take precedence over general daily-driver preferences. These are
Jamon's preferences, not a universal model ranking.

Prefer each model's native harness. Grok in the task table means native Grok 4.7
at high. Crok/Croc means Cursor Grok; use that harness when the caller names it.
Use `jamsession models <provider>` to resolve exact installed IDs. A missing
picker entry alone does not prove a requested model unavailable.

## Task defaults

| Work | Default | Alternatives |
| --- | --- | --- |
| Difficult planning or diagnosis | Astra 6 xhigh, Opus 5.5 xhigh | Wonder Full 1.0 xhigh |
| Bounded bugfix planning | Sol 6.1 xhigh, Sonnet 5.5 xhigh | native Grok high |
| Cheap implementation from a good plan | Luna 6 max, SWE-2 max | Sonnet 5.5 high, Haiku 5.5 xhigh |
| Complex production or multi-file implementation | Sol 6.1 medium, Opus 5.5 medium | native Grok high |
| Contrarian review | Native Grok high | Sonnet 5.5 high, Luna 6 max, SWE-2 max, Wonder 1.0 xhigh, Haiku 5.5 xhigh |

Cheap implementation assumes a good supplied plan. Use the difficult-planning
or diagnosis defaults when diagnosis is needed; review and verification still
belong to the task's workflow.

## PPP

For ping-pong planning, use Astra 6 xhigh and Opus 5.5 xhigh as planners, with
native Grok 4.7 high as the contrarian. Use the ping-pong planning workflow for
independent drafts, challenge rounds and synthesis.

## Babysitting

Use Luna 6 xhigh, Sonnet 5.5 medium or native Grok 4.7 high to babysit external
implementers. Route hard planning or diagnosis to the task defaults above.

## Daily drivers

General interactive preferences, when no task-specific route applies:

* Best: Claude Opus 5.5 medium, GPT-6.1 Sol medium, Muse Wonder 1.0 xhigh
* Good: GPT-6 Astra low

## Do not use

* Claude Fable 5.1: an excellent model, but it burns tokens too fast and is far
  too expensive when Opus 5.5 xhigh does the job

## Known native models

Catalog snapshot: October 12, 2026. Models belong next to their native agent,
not every harness that can host them. This is an inventory, not a recommendation
or a guarantee of account availability. Effort, fast and contributor variants
are grouped; use `jamsession models <provider>` for exact installed IDs.

| Native agent | Known models and families |
| --- | --- |
| Codex / OpenAI | GPT-6.1 Sol; GPT-6 Astra, Sol and Luna; GPT-5.6 Sol, Terra and Luna. Other harness catalogs retain GPT-5.5, GPT-5.4 and Mini, GPT-5.3 Codex, GPT-5.2, GPT-5.1 and GPT-4.1; these are legacy, not necessarily available in Codex. |
| Claude / Anthropic | Opus 5.5, 5, 4.8, 4.7, 4.6 and 4.5; Fable 5.1 and 5; Sonnet 5.5, 5 and 4.6; Haiku 5.5 and 4.5. Some known families are omitted by the installed picker. |
| Grok / xAI | Grok 4.7 (including build-fast), 4.6 and 4.5. Crok/Croc uses these through Cursor; do not duplicate their catalog under Cursor. |
| Cursor | Composer 2.5 (including fast). Cursor also has access to other providers' models. |
| Devin / Cognition | SWE-2, SWE-1.7, SWE-1.7 Lightning and SWE-1.6 (including fast). Adaptive selects models; Fusion combines models rather than naming a separate native model. Devin also has access to other providers' models, including through Fusion. |
| Muse / Meta | Muse Wonder 1.0 and Muse Wonder Full 1.0; Muse Spark 1.3 and 1.2 (including contributor variants). |
| Copilot / GitHub | A multi-model harness; no separate GitHub-native base model is identified here. |
| Antigravity / Google | Gemini 3.8 Flash (low, medium, high) in the installed `agy` catalog. Older harness catalogs retain Gemini 3.7, 3.6 and 3.5 Flash, Gemini 3.1 Pro and Gemini 3 Flash; verify availability. Use provider `antigravity`, `agy` or `gemini`; xhigh/max map to high with a warning. Antigravity also hosts other providers' models. |

## Notes

* Muse Wonder 1.0 and Muse Wonder Full 1.0 are distinct models; keep their roles
  and requested settings separate
* As of October 12, Jamon considers Muse Wonder 1.0 at xhigh to be GPT-6.1
  Sol-level for his interactive use; task defaults still take precedence
* Devin's top SWE-2 effort is `swe-2-max` (there is no xhigh)
* Devin `swe-2-high` remains a fallback for briefs that explicitly name it when
  Fusion returns `resource_exhausted`; routine cheap implementation uses max
* GPT-5.5, Claude Sonnet before 5.5, and other older models are poor choices;
  use them only when a harness has nothing better

Unknown, haven't used enough:

* Gemini 3.8 Flash
* GLM 5.3 (Flash)

Users can copy this skill under another name and maintain their own model
recommendations. Prefer user recommendations over Jamon's if present.
