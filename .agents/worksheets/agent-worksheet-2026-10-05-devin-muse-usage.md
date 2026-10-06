# Devin And Muse Subscription Usage

Status: BLOCKED
Starting HEAD: 48a72fb85b11c2d4bcb69830eb2b743c0912241c

## Task source

Jamon asked to fix Devin and Muse usage collection rather than omit them from
agent usage reports. Preserve account quota versus local session-token totals;
never consume a reset or submit a model prompt just to measure quota.

## Findings and plan

- Devin 3000.11.3 startup TUI reports `Max · 100% remaining (resets in 5d 8h)`.
  Read that supported screen through the existing bounded PTY reader without
  submitting `/usage` or a model prompt. Report the provider's countdown, not
  an invented exact reset or billing-period label.
- Muse 1.4.3 exposes documented MSP `usage/read`, returning optional last-seen
  subscription windows. Sequential initialize/result/initialized handshake is
  required. A read on this account currently returns an empty result. Investigate
  normal native startup only; never fabricate zero usage from missing data.
- Extend existing usage owner and adapter dispatch, include both in aggregates,
  keep errors honest, and add fixture/transport regression coverage.
- Preserve the unrelated untracked `adapters/jamsession_antigravity`.

## Evidence

Live probes retained in `/tmp/jamsession-usage-probe.Mu3TpX/`.
Muse reference: https://meta-models.github.io/muse-code-sdk/next/generated/msp/methods/usage-read/
No login changes, resets, browser-cookie reads, or model turns requested.

## Agent sessions

- Primary Codex app runtime `/root` — investigation and implementation; exact
  resumable ID not exposed.

## Handoff

Devin collection works live and is installed locally: 100% remaining, reset
countdown `in 5d 7h` at final verification. Both adapter usage commands now
delegate to the existing collector, and both providers appear in aggregates.

Muse now performs the official initialize/result/initialized handshake and
`usage/read` request through a temporary, memory-only CLI host. It accepts
provider percentages and reset stamps, preserves `observed_at`, filters expired
windows, and rejects malformed data. Live reads on this account return an empty
result, including after safe session initialization. This yields the specific
`usage_not_observed` diagnostic rather than fabricated unused quota. No current
Muse balance was obtained: that part of the user outcome remains blocked on a
provider observation or a supported quota-refresh interface. Do not claim a
live Muse quota fix from successful mock responses alone.

Validation: all 446 tests pass, including the startup PTY, sequential Muse wire
transport, no-model-turn request log, missing/malformed/expired quota, decimal
percentages, direct adapter dispatch, aggregate reporting, and bounded timeout.
Bash syntax, Python compile, diff check, and the usage-skill validator pass.
Final installed-CLI checks reproduce Devin quota and Muse's missing-observation
diagnostic. README, install/help text, and the usage skill explain the source,
timestamps, and unavailable cases. No credentials printed, browser cookies
read, model turns submitted, or usage resets consumed.

Files changed: `usage/jamsession_usage`, `usage/jamsession_tui_usage.py`,
`adapters/_jamsession_adapter_common`, Devin/Muse adapters, `jamsession`,
`tests/test_jamsession.sh`, `README.md`, `install.md`, the usage skill, and this
worksheet. The unrelated Antigravity adapter remains untouched.

Jamon subsequently authorized committing/pushing the implementation and
updating Gunship's copy. Local installation was refreshed from source.
Next action: establish a supported way to obtain a Muse subscription observation
without inference; any proposal to spend a prompt or read browser credentials
requires explicit user direction. The quota itself is not inferred from tokens.
