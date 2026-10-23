# Codex accepted identity retention

Status: COMPLETE
Request: Archie owner-directed scoped repair, October 23, 2026; task-relevant
Jam Session source only. No recovery/retry of UNKNOWN helicopter review.

## Cause and correction

Control resume received the accepted native turn ID but emitted no identity
before waiting. Native CLI redirected its JSONL stream to a temporary file and
only parsed it after exit. Caller timeout could therefore lose the exact ID.

Flush accepted control session/turn IDs before waiting. For CLI, retain each
event in the existing temporary log and emit the exact thread.started ID as
it arrives. The documented native exec schema has a thread_id on thread.started
but no turn ID on turn.started; do not infer or invent one. Source:
https://learn.chatgpt.com/docs/non-interactive-mode

Preserve native exit status, final output, pre-input busy guards, denial behavior,
read access and UNKNOWN/no-resend semantics. Local cancellation is not proof of
remote cancellation. No generic transport or retry mechanism added.

## Validation and ownership

Fake WebSocket/native subprocess tests: 49 passed, including identity visible
before caller timeout/cancellation, SIGTERM/SIGINT nonzero exits, fresh event
streaming in both JSON field orders without fabricated turn ID, pre-input denial
and accepted disconnect without fallback. No model calls in tests. Package
suite: final rerun 616 passed, 0 failed (including 49 control tests).
Shell syntax, whitespace and summon skill quick_validate passed.

Archie authorized reduced Astra/Grok Court coverage because Claude is paused.
Native Grok failed with exhausted balance (402), left behind without retry,
reset or substitution. Single-reviewer caveat: native Astra xhigh session
01a16aaa-72bc-7181-8505-636616f214b9 found JSON field-order loss. Corrected using
shell-native matching of the documented two-field event in either order, no
per-event subprocess/parser dependency. Astra's retained-session follow-up found
the issue resolved and no remaining concrete regression; it independently
checked matcher probes and syntax, not the full file-writing fake suite.

Published fix: 0f6e3e89e967c69c6391e4487ae159125580665e, normal main push.
Normal installed `jamsession update` from public main succeeded. Installed
Codex adapter, control helper, CLI and summon skill byte-match canonical source;
installed `help codex` displays the new contract. No global Codex settings,
transcripts, locks, UNKNOWN sessions or Gunship files changed. Local cancellation
still makes no remote cancellation guarantee. Review coverage remains one Astra
reviewer, with Grok unavailable as recorded above.

Unrelated usage-skill changes appeared during work and remain excluded, along
with pre-existing Finder files and cache-investigation worksheet.
