---
name: jamsession-model-recommendations
description: "Choose agent providers, models and effort using Jamon's recommendations when the caller has not specified them."
---

# Jam Session Model Recommendations

These recommendations are fresh as of November 9, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Run
`jamsession status`, then choose the provider, model, effort, and access level
explicitly from what is available. If a default is unavailable, use a listed
alternative when possible and report the change.

Choose by the work being done. Each entry names a model at a specific effort;
defaults are preferred routes, and alternatives are acceptable for that role.
Task defaults take precedence over general daily-driver preferences. These are
Jamon's preferences, not a universal model ranking.

Always use the latest model in each family; configs say `<family>@latest`.

Prefer each model's native harness. Grok in the task table means native latest
Grok at high. Crok/Croc means Cursor Grok; use that harness when the caller names it.
Use `jamsession models <provider>` to resolve exact installed IDs. A missing
picker entry alone does not prove a requested model unavailable.

## Task defaults

| Work | Default | Alternatives |
| --- | --- | --- |
| Difficult planning or diagnosis | latest Opus high, latest Sol xhigh | latest Opus xhigh; latest Astra xhigh or latest Fable as panelists |
| UI work | latest Astra or latest Fable, as panelists under a Sol or Opus lead | latest Opus high |
| Analysis, planning, diagnosis, performance work | latest Sol high | latest Opus medium, native Grok high |
| Building new things, ordinary task work | latest Opus medium | latest Sol high, native Grok high |
| Light task work or implementation from a plan | native Grok high | Cursor Grok high |
| Cheap limited-scope work from a good plan | SWE-2 max, SWE-2 Flash max | latest Luna max, latest Haiku xhigh |
| Contrarian review | native Grok high | Cursor Grok high, SWE-2 max, latest Wonder high |

Cheap work assumes a good supplied plan: SWE-2 and SWE-2 Flash are free, so
use them as limited-scope spiders with a clear heuristic written by a stronger
model. Use the difficult-planning or diagnosis defaults when diagnosis is
needed; review and verification still belong to the task's workflow.

Latest Opus at medium or high is the best mix of power and efficiency, so do not
spend it on routine interactions unless the human asks. Spend Opus from Devin's
bucket first, then native Claude, then Cursor's included Opus as a last
fallback. The latest Astra and latest Fable are best in class and expensive: use them as
panelists for work a Sol or Opus lead manages, mostly UI work, not as leads.
Latest Terra high and latest Sonnet high are about Grok level; use native Grok
instead.

Jam Session's `tiers.toml` (`jamsession tiers`) ranks these models A to F and
lists the harnesses that serve each; `jamsession run --failover` and tier routes
follow it, so keep it in step with these recommendations.

## PPP / Noble Court

Ordinary PPP uses two independent model families and one challenge/integration round, with task-appropriate defaults or listed alternatives. Add a premium third reviewer (Noble Court: latest Astra xhigh, latest Opus xhigh, native latest Grok high contrarian) only when explicitly requested or justified by a concrete unresolved high-risk question. Follow the ping-pong planning workflow without expanding the agreed roster or round count.

## Peasant Mob

Use `jamsession-peasant-mob` for the requested eight-lane planning/research/
diagnosis workflow. That skill owns the exact roster and practical effort
settings: all eight attempted in parallel, failed members left behind, and at
least two complete feedback rounds after initial drafts. Synthesis uses latest
Sol LOW or latest Opus LOW, outside the eight lanes. It is experimental, with no
measured superiority claim or guarantee of effort-price/quota parity. Noble
Court keeps the premium PPP defaults and its existing round-count behavior.

## Babysitting

Use native latest Grok high or latest Luna xhigh to babysit external implementers. Route hard planning or diagnosis to the task defaults above.

## New autonomous assignments

For a new autonomous lead or implementer, prefer latest Sol through Codex first, then latest Opus through Devin, then Cursor, with native Claude last. In-process Claude Code subagents (the Agent tool) never default to Opus: hand the work to a jamsession Codex or Grok session, or use latest Sonnet or Haiku when it must stay in-process. Repository routing still chooses reviewers and panels; these choices do not change Noble Court's roster or Peasant Mob's LOW synthesizer, apply at new assignments or natural handoffs rather than by restarting productive workers, and explicit restrictions always win.

## Daily drivers

General interactive preferences, when no task-specific route applies:

* Routine replies and questions: native latest Grok high (it can be slow), then
  Cursor latest Grok high
* Task work: latest Sol high
* Best, when the human asks: latest Opus medium or high

## Do not use

* Claude Fable 5.1: superseded by Fable 5.2 (history); latest Fable is a panelist only (above)
* Latest Terra and latest Sonnet as a first choice: use native Grok; they
  remain last-resort tier C failover targets

## Known native models

Catalog snapshot: October 12, 2026. Models belong next to their native agent,
not every harness that can host them. This is an inventory, not a recommendation
or a guarantee of account availability. Effort, fast and contributor variants
are grouped; use `jamsession models <provider>` for exact installed IDs.

| Native agent | Known models and families |
| --- | --- |
| Codex / OpenAI | GPT-6.2 Astra (latest); GPT-6.1 Sol and Terra; GPT-6 Astra, Sol and Luna; GPT-5.6 Sol, Terra and Luna. Other harness catalogs retain GPT-5.5, GPT-5.4 and Mini, GPT-5.3 Codex, GPT-5.2, GPT-5.1 and GPT-4.1; these are legacy, not necessarily available in Codex. |
| Claude / Anthropic | Opus 5.5, 5, 4.8, 4.7, 4.6 and 4.5; Fable 5.2, 5.1 and 5; Sonnet 5.5, 5 and 4.6; Haiku 5.5 and 4.5. Some known families are omitted by the installed picker. |
| Grok / xAI | Grok 4.7 (including build-fast), 4.6 and 4.5. Crok/Croc uses these through Cursor; do not duplicate their catalog under Cursor. |
| Cursor | Composer 2.5 (including fast). Cursor also has access to other providers' models. |
| Devin / Cognition | SWE-2 (free; paid Lightning variants), SWE-2 Flash (free), SWE-1.7, SWE-1.7 Lightning and SWE-1.6 (including fast). Adaptive selects models; Fusion combines models rather than naming a separate native model. Devin also has access to other providers' models, including through Fusion. |
| Muse / Meta | Muse Wonder 1.0 and Muse Wonder Full 1.0; Muse Spark 1.3 and 1.2 (including contributor variants). |
| Copilot / GitHub | A multi-model harness; no separate GitHub-native base model is identified here. |
| Antigravity / Google | Gemini 3.8 Flash (low, medium, high) in the installed `agy` catalog. Older harness catalogs retain Gemini 3.7, 3.6 and 3.5 Flash, Gemini 3.1 Pro and Gemini 3 Flash; verify availability. Use provider `antigravity`, `agy` or `gemini`; xhigh/max map to high with a warning. Antigravity also hosts other providers' models. |

## Notes

* Muse Wonder 1.0 and Muse Wonder Full 1.0 are distinct models; keep their roles
  and requested settings separate
* Latest Wonder is tier C (with Grok) only at high effort; run it at high
* Devin's top SWE-2 effort is `swe-2-max` (there is no xhigh). The cheap tier
  is SWE-2 Flash (`swe-2-flash-max`); there is no "SWE-2 light". The
  `-lightning` variants are billed, so never pick them by default
* Devin `swe-2-high` remains a fallback for briefs that explicitly name it when
  Fusion returns `resource_exhausted`; routine cheap implementation uses max
* GPT-5.5, Claude Sonnet before 5.5, and other older models are poor choices;
  use them only when a harness has nothing better

Unknown, haven't used enough (do not route to these):

* Gemini 3.8 Flash
* GLM 5.3 (Flash)
* Gemini 4 Carbon, Argon and Hydrogen
* Muse Ember 1.0
* Kimi K3.1 Pro
* GLM-5.3

Users can copy this skill under another name and maintain their own model
recommendations. Prefer user recommendations over Jamon's if present.
