# Accounts: warn when a bare provider has several

- Status: COMPLETE
- Source: Leader task. Jamon wants agents to learn to name an account.
- Starting commit: `c372516cbcbcaefc5fe94ea3aed18d29dfc86b47`

## Requirements

- A bare provider with two or more accounts warns on stderr, lists each account with weekly usage, and still runs. A budgeted account shows spend against its budget. Usage comes from the usage cache only; unknown usage is `?`.
- The run uses the first account still above its own `min_usage` and budget. File order is the order. Unknown usage does not skip. Remaining equal to the floor is still used.
- No warning when the caller named an account, the provider has one account, the session already has a recorded account, or the run is an internal failover step. A caller's own `--failover` warns once and does not pin the provider argument.
- The same rule applies to every provider.
- Tests for the bare warning, a named account, a single account, and a recorded resume. One README sentence and one summon-agent sentence.

## Decisions

- There was no usage cache. `jamsession usage` writes `~/.cache/jamsession/usage.json` (`JAMSESSION_USAGE_CACHE`). The warning only reads that file.
- A plain run actually selects the eligible account. That selection is not an explicit name, so it does not latch onto an unrecorded session.
- Failover children get `JAMSESSION_FAILOVER_STEP=1` so a bare default pool does not warn again. The parent warning does not rewrite the provider argument.

## Outcome

`bash tests/test_jamsession.sh` — 644 passed, 0 failed. `tests/test_accounts.py` — 27 tests, OK. A bare provider warns with weekly usage or `?`, shows a budgeted account as spend against its budget, and runs the first account still above its `min_usage` and budget. A named account, one account, a recorded resume, and an internal failover step do not warn. The caller's `--failover` warns once and does not pin the provider argument.

`jamsession usage` writes `~/.cache/jamsession/usage.json`. The warning only reads that file. `claude:api` stays on the Claude CLI.
