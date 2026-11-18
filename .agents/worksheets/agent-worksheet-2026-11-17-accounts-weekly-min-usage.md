# Accounts: weekly window and min_usage

- Status: COMPLETE
- Source: Leader change after `b487b41d18c81e0f70fbc4d09e70e87e0ba426e8`
- Starting commit: `b487b41d18c81e0f70fbc4d09e70e87e0ba426e8`

## Requirements

- `claude:api` stays on the Claude CLI. No Agent SDK runner. Keep the Keychain item, `~/.claude-api`, and the $500 budget.
- Local Claude failover order stays work, personal, api. `min_usage = 5` on work and personal overrides the 25% skip. API is skipped when the month's budget is spent.
- Adding another account is `accounts add` plus an entry in that order when tiers name accounts.
- Usage skip and `min_usage` read the longest window. A 5-hour session window does not make an account unavailable when a weekly or monthly window exists. `usage` and `accounts list` lead with the weekly window.
- Tests: per-account `min_usage` overrides the global threshold; 2% session and 40% weekly stays available.

## Decisions

- Windows at or under 6 hours are short. When a longer window exists, only windows of the longest duration count, and the lowest of those is the threshold. A short window alone does not skip.
- `--min-usage 0` still turns the usage skip off, including for an account that sets `min_usage`.
- Display puts weekly-length windows first, then other long windows, then the session window. Reordering keeps the original JSON text so `0.000001` is not rewritten as `1e-06`.

## Outcome

Validation: `bash tests/test_jamsession.sh` — 644 passed, 0 failed. `tests/test_accounts.py` covers `min_usage` overriding 25%, and 2% session plus 40% weekly staying available while 10% weekly still skips.

`claude:api` remains `backend = "claude-cli"`. Local `accounts.toml` sets `min_usage = 5` on work and personal. Tiers still list work, personal, api after the shipped harnesses. Not committed.
