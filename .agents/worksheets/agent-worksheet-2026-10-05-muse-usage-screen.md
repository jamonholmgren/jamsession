# Muse Usage Screen

Status: COMPLETE
Starting HEAD: 0b3f4da3406d5ce9c58179f5898dace90ae5cf30

## Request and plan

Jamon demonstrated subscription quota in Muse 1.4.3 after sending `/usage`.
Add that supported local command as a fallback when MSP `usage/read` has no
unexpired observation. Reuse the bounded disposable PTY; read only Subscription,
preserve as-of/reset text, and never send a model prompt or consume a reset.
Update guidance, extend existing tests, and verify the installed native CLI.
Keep changes local; do not push. Preserve the unrelated Antigravity adapter.

## Progress

The shared Python usage reader already owns terminal capture and the MSP read.
No daemon, persistent cache, login change, or new runtime dependency is needed.

Muse reads `/dev/tty` and negotiates key encoding before interactive input.
An isolated controlling PTY plus ordinary-key/terminal query replies makes
Enter submit `/usage` rather than insert a newline. Native Muse 1.4.3's screen
confirmed zero tokens and zero turns while displaying subscription windows.
The source and refreshed installed CLI both report 100% current, 99% weekly
remaining, resets at 10:00 PM and Oct 11 at 5:00 PM, as of 6:25 PM.

The fallback shares the existing timeout budget and requires both Subscription
rows plus an as-of stamp; session tokens alone cannot become quota. Tests cover
the actual public collector with a dual MSP/controlling-terminal fixture, key
negotiation, safe launch flags and temporary cwd, and missing subscription data.
The terminal fixture uses CRLF after entering raw mode, matching native rendering.
All 452 tests pass. Syntax, Python compile, skill metadata and diff checks pass.
Self-review confirmed quota-only parsing, bounded collection, isolated terminal
ownership, safe temporary workspace trust, and provider-native as-of/reset text.
The local installed helper matches the source byte-for-byte. Changes remain
uncommitted and unpushed; the unrelated Antigravity adapter is untouched.

Updated files: `usage/jamsession_tui_usage.py`, `tests/test_jamsession.sh`,
`adapters/jamsession_muse`, `jamsession`, `README.md`, `install.md`, and
`skills/jamsession-get-agent-usage/SKILL.md`. Other concurrent skill-description
edits were committed separately as `59c1fc1`; they were not part of this task.
