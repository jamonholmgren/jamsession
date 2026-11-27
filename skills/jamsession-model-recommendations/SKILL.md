---
name: jamsession-model-recommendations
description: "Choose agent providers, models and effort using Jamon's recommendations when the caller has not specified them."
---

# Jam Session Model Recommendations

These recommendations are fresh as of November 27, 2026. If that date is more
than two months old, warn that the recommendations could be stale. Run
`jamsession status`, then choose the provider, model, effort, and access level
explicitly from what is available. If a model is unavailable, take the next one
in its group and report the change.

Work picks a group; a group is Jamon's ranked fallback list, and the effort
shown is each rung's default. Always use the latest model in each family;
configs say `<family>@latest`. Prefer each model's native harness. Jam Session's
`groups.toml` holds these groups (`jamsession route group:<name>`), and
`tiers.toml` keeps failover in step with them. Claude rungs try the accounts in
`accounts.toml` order (personal, then work, then api); a login account's
`min_usage` replaces the 25% skip, using the weekly window.

## Groups

| Group | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- |
| premium | Fable (latest) medium | Astra (latest) high | Neon xhigh | Wonder Full 1.0 high |
| daily | Neon medium | Opus (latest) medium | Sol (latest) high | |

Daily's first two are interchangeable: new work starts on whichever has more usage left.
| efficient | Devin SWE-2.1 max | Sonnet (latest) high | Terra (latest) high | |
| cheap | Devin SWE-2.1 max | Luna (latest) max | Haiku (latest) max | |
| token-burners | Grok 4.7 high (native) | Muse Wonder 1.0 high | | |

Neon is Antigravity's `gemini-4-neon` (provider `agy`); Antigravity has no
`read` mode, so a read-only role on Neon runs with the no-writes line from
`jamsession-summon-agent`. No CLI serves Wonder Full yet; skip that rung until
one does. Cursor is not used.

## Work

| Work | Group | Prefer |
| --- | --- | --- |
| Interactive planning sessions | daily | Neon medium |
| Difficult planning or diagnosis | premium | Council ×2 |
| Architecture | premium | Council ×2 |
| Performance optimization | premium | Astra xhigh |
| 3D design, planning, implementation | premium | Astra xhigh |
| UI / UX design planning | premium | Fable |
| Analysis, planning, ordinary diagnosis | daily | Neon |
| Building new things, ordinary task work | daily | Neon |
| Light task work or implementation from a plan | efficient | SWE-2.1 max |
| Cheap limited-scope work from a good plan | cheap | SWE-2.1 xhigh |
| Contrarian review | token-burners | different model family |
| Babysitting external agents | cheap | SWE-2.1 high |
| Routine replies and questions | daily | Neon medium |

"Prefer" moves that model to the front for that work; the rest of the group
stays as fallback. "Council ×N" means `jamsession-council-panel` with N
revision rounds.

Cheap work assumes a good supplied plan: SWE-2.1 is free for now, so use it as
a limited-scope spider with a clear heuristic written by a stronger model.

## Peasant Mob

Use `jamsession-peasant-mob` for the requested eight-lane planning/research/
diagnosis workflow; that skill owns its roster.

## New autonomous assignments

In-process Claude Code subagents (the Agent tool) never default to Opus: hand
the work to a jamsession session from the matching group, or use latest Sonnet
or Haiku when it must stay in-process. Apply these choices at new assignments or
natural handoffs rather than by restarting productive workers; explicit
restrictions always win.

## Known native models

Catalog snapshot: October 12, 2026. Models belong next to their native agent,
not every harness that can host them. This is an inventory, not a recommendation
or a guarantee of account availability. Effort, fast and contributor variants
are grouped; use `jamsession models <provider>` for exact installed IDs.

| Native agent | Known models and families |
| --- | --- |
| Codex / OpenAI | GPT-6.2 Astra (latest); GPT-6.1 Sol and Terra; GPT-6 Astra, Sol and Luna; GPT-5.6 Sol, Terra and Luna. Other harness catalogs retain GPT-5.5, GPT-5.4 and Mini, GPT-5.3 Codex, GPT-5.2, GPT-5.1 and GPT-4.1; these are legacy, not necessarily available in Codex. |
| Claude / Anthropic | Opus 5.5, 5, 4.8, 4.7, 4.6 and 4.5; Fable 5.2, 5.1 and 5; Sonnet 5.5, 5 and 4.6; Haiku 5.5 and 4.5. Some known families are omitted by the installed picker. |
| Grok / xAI | Grok 4.7 (including build-fast), 4.6 and 4.5. |
| Cursor | Composer 2.5 (including fast). Cursor also has access to other providers' models. |
| Devin / Cognition | SWE-2.1 (free for now; paid Lightning variants), SWE-2 (free), SWE-2 Flash (free for now), SWE-1.7, SWE-1.7 Lightning and SWE-1.6 (including fast). Adaptive selects models; Fusion combines models rather than naming a separate native model. Devin also has access to other providers' models, including through Fusion. |
| Muse / Meta | Muse Wonder 1.0 and Muse Wonder Full 1.0; Muse Spark 1.3 and 1.2 (including contributor variants). |
| Copilot / GitHub | A multi-model harness; no separate GitHub-native base model is identified here. |
| Antigravity / Google | Gemini 4 Neon (low, medium, high, xhigh) and Gemini 3.8 Flash (low, medium, high) in the installed `agy` catalog. Older harness catalogs retain Gemini 3.7, 3.6 and 3.5 Flash, Gemini 3.1 Pro and Gemini 3 Flash; verify availability. Use provider `antigravity`, `agy` or `gemini`; xhigh is used where the catalog lists a `-xhigh` variant (Gemini 4 Neon and Hydrogen), and max maps to it; otherwise xhigh/max fall back to high with a warning. Antigravity also hosts other providers' models. |

## Notes

* Muse Wonder 1.0 and Muse Wonder Full 1.0 are distinct models; keep their roles
  and requested settings separate
* Latest Wonder runs only at high effort
* SWE-2.1 (`swe-2.1@latest`, IDs `swe-2-1-<effort>`) has low through max;
  the groups set its effort. There is no SWE-2.1 Flash yet, so the cheapest tier stays SWE-2
  Flash (`swe-2-flash-max`). The `-lightning` variants are billed, so never
  pick them by default
* Devin `swe-2-1-high` is the fallback when Fusion returns
  `resource_exhausted`; routine cheap implementation uses max
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
