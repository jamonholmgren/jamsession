# Named provider accounts

Status: COMPLETE

Add named provider accounts: `accounts.toml` env maps, `provider:account` and
`JAMSESSION_<PROVIDER>_ACCOUNT`, per-run env, session → account memory,
per-account usage, failover pools, and recall across each account's history.
Do not put a personal Claude account in the shipped `tiers.toml`.

Starting commit: 5a09bd2 on main.

The first account listed for a provider is the default. An empty via account
is that default pool, so a plain `claude` run is not tried twice. A low pool
is skipped before it is tried, including the one named. Session records use
`r+` (not append) so a second session replaces the JSON object. The installer
ships `accounts.toml.example` and never writes `accounts.toml`.

Validation: `bash tests/test_jamsession.sh` — 644 passed, 0 failed.
`tests/test_accounts.py` covers one-run env, recorded resume and mismatch,
failover from a 10% account to an 80% account, per-account usage rows, and
recall across both Claude history directories.
