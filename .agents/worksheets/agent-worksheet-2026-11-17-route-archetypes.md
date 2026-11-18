# Routes: named archetypes

- Status: COMPLETE
- Source: Leader task. Every role should point at a few named model lists.
- Starting commit: `591a3bc9764c238c0c87d4fabcbe96ab68af77c5`

## Requirements

- `[archetype.<name>]` tables in the routes file, each with `rungs` in the same shape as a route rung, including `provider:account`.
- A route may set `archetype` instead of `rungs` or `tier`, plus an optional `effort` that overrides every rung. The override is mapped per harness the way a tiers via maps `efforts`.
- A panel may set `from_archetypes`. It takes each archetype's first available rung, skips refused or low pools, and keeps at most one per provider:account until `size`. An explicit `from` list still works.
- `jamsession route` shows the expanded rungs and which archetype each came from.
- Tests: archetype expansion, effort override, distinct panel heads, unknown archetype. One short README note.
- Do not edit `~/Code/jambot/routes.toml`.

## Decisions

- Low pools use the same weekly remaining check as failover, from `JAMSESSION_USAGE_JSON` or the usage cache. Route expansion does not launch a live usage read. Unknown usage stays available.
- A refused pool here is one `unavailable_reason` rejects (budget, keychain, unknown backend). A missing account name is refused too.
- An archetype ladder lists every rung. Only a `from_archetypes` panel skips and dedupes.
- The route printer notes `archetype=<name>`. JSON includes the same field.

## Outcome

`bash tests/test_jamsession.sh` — 644 passed, 0 failed. `tests/test_failover.py` — 32 tests, OK. An archetype route expands its rungs, including `provider:account`. A route `effort` overrides every rung and follows the tiers `efforts` map (`max` on Grok becomes `high`). A `from_archetypes` panel skips a low head, keeps one rung per provider, and stops at `size`. An explicit `from` list is unchanged. An unknown archetype exits 2 and names the ones that exist.

`~/Code/jambot/routes.toml` was not edited.
