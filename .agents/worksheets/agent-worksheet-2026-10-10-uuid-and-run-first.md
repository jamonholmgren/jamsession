# Shared UUIDs and Run-First Codex Follow-Ups

Status: COMPLETE
Starting HEAD: 5896e087ade3622f137e21baf371eac93ad450ba

Jamon requested OS-backed session IDs in the common helper for all affected
adapters, and run/resume first for Codex follow-ups, queue only on confirmed
busy/foreign ownership. Update scripts, skill, output and docs. Preserve unrelated
Muse/Antigravity WIP and permissions; never retry denied or uncertain delivery.

Evidence: 100 parallel stock macOS Bash 3.2 UUID calls produced 98 unique IDs,
with one repeated three times. A second 300-process check produced 297 IDs.
Claude, Grok and Copilot use the same Bash RANDOM helper and pass the result
as the provider session ID. Replace this source, not adapter-specific symptoms.

The prior Codex investigation proved that a desktop process may retain a native
writer lock while idle. Its queue consumer may wait for UI focus. Run-first
cannot steal that lock or guarantee queued work starts. Use native run/resume
for controllable idle sessions and report queued-only outcomes explicitly.
Explicit read access must not fall back to a queue whose sandbox cannot be set.

Plan: change shared UUID generation and all callers' failure handling; make Codex
run-first/busy-only fallback; preserve steer as explicit redirection; align docs
and summon skill; exercise concurrent adapter launches, idle/busy/foreign-owner,
denial and uncertain-ack paths through existing tests and owned real fixtures.

## Implementation and validation

Shared UUID helper reads 16 OS-random bytes with system od, sets RFC v4 bits,
and rejects read failures, malformed or incomplete entropy. Claude, Grok and
Copilot all stop before provider launch if allocation fails. Native-generated
provider IDs and Codex Python UUIDs already use OS-backed generation.

Codex control run rejects confirmed active state before submitting input, then
the adapter falls back once to native delivery on that exact busy result or
the native foreign-writer refusal. CLI-only resume recognizes the installed
pre-input writer-conflict error only with empty event/result output. No generic
failure, denied request, partial output or lost acknowledgement triggers queue.
Idle messages use turn/start directly instead of queuing. Queued-only diagnostics
say execution is unconfirmed and warn about desktop focus and retained owner
settings; read runs refuse fallback rather than weaken the requested sandbox.
Serialize same-session follow-ups: the installed native turn/start API has no
atomic idle-only precondition and can steer if another sender races into a turn.

Evidence:
- Stock macOS Bash 3.2 generated 1,000 distinct valid v4 IDs in five concurrent
  workers. Public CLI tests exercise 60 parallel Claude/Grok/Copilot launches,
  actual provider arguments, OS-entropy consumption and failure handling.
- The entropy-source regression fails against the previous tracked helper and
  passes against the implementation. Shell PRNG reseeding alone was not a
  deterministic collision reproducer, so tests verify the actual entropy seam.
- 26 Codex protocol/CLI tests and 3 adapter session tests passed.
- Final clean task-only package suite passed 485 checks. Shell/Python syntax
  and skill validation passed. Log: /tmp/jamsession-uuid-resume.GMHwxY/final-suite.log.
- Owned live fixture 01a12770-1e4f-7ae0-a1a6-c4bc2f4041a0 returned RUN_FIRST_OK
  on idle run, started IDLE_MESSAGE_OK directly, refused a second CLI writer,
  and accepted/consumed FOREIGN_QUEUE_OK once. Read-only sandbox and on-request
  approval policy survived fallback. This native daemon drained its queue
  without UI focus; it does not prove a separate desktop owner will do so.
  Fixture was archived; no shared daemon or user session was stopped.
- Earlier live probe assumed a queued item remained pending; the daemon had
  already consumed it. The corrected check verifies the completed marker.

Changed: common helper, three UUID callers, Codex adapter/control helper,
summon skill, CLI help, README/install guidance and regression tests. Unrelated
Muse usage/Antigravity WIP remains excluded. No Gunship files or installed copies
have been changed.
