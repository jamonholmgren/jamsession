# Accounts: failover, Keychain, API budget

- Status: COMPLETE
- Source: Leader follow-up on named accounts (main `5a0e5a95cbde1e0591cf15159b76126c4e8f9840`)
- Starting commit: `5a0e5a95cbde1e0591cf15159b76126c4e8f9840`

## Requirements

- Cross-account failover is on by default, in accounts.toml order. No per-repo pin. Docs describe it. Shipped tiers.toml names no account.
- `jamsession accounts add` and `accounts list`.
- Codex accounts via `CODEX_HOME` for run, resume, message, steer, usage, recall, and failover.
- `keychain_env` resolved at run time with `security find-generic-password -s <name> -w`. Passed only to that run. Never logged. A missing item skips the account.
- `claude:api` uses the Claude CLI (`backend = "claude-cli"`) in `~/.claude-api`. Cost from `total_cost_usd` accumulates in `spend.json` per calendar month. `monthly_budget_usd` makes the account unavailable at the limit. No Agent SDK runner.
- No accounts file keeps today's behavior. Three or more accounts fail over in file order.
- Local-only accounts and tiers for Jamon. Do not commit them.

## Decisions

- Auto-expand unlabeled failover candidates only when that provider has two or more accounts and no via names an account. Explicit vias keep their order. Zero or one account does not rewrite the provider argument. One account leaves usage JSON untagged.
- Account kind `api` plus backend `claude-cli` is the seam. Any other backend is unavailable until a runner exists.
- `JAMSESSION_TIERS` in jamsession.conf is exported when set. The installer overwrites `tiers.toml`, so the local ladder lives in `tiers.user.toml`.

## Outcome

Validation: `bash tests/test_jamsession.sh` — 644 passed, 0 failed. `tests/test_accounts.py` (19) covers unchanged behavior with no accounts file, one untagged account, three-account file order, Codex `CODEX_HOME` run/resume/message/steer/usage/recall, keychain values passed only to the run, a missing keychain item, the monthly budget, and `accounts add`/`list`. `tests/test_failover.py` (26) passed inside the same suite.

Local-only, not committed: `~/.agents/jamsession/accounts.toml` (work, personal, api, codex.default), `tiers.user.toml` (work, personal, api after the shipped harnesses for fable, opus, sonnet, haiku), `JAMSESSION_TIERS` in `jamsession.conf`, and `~/.local/bin/claude-personal`. No login and no `security add-generic-password`.

`claude:api` runs the Claude CLI (`backend = "claude-cli"`). No Agent SDK runner.
