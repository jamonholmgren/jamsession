# Muse usage/status and native model inventory

Status: COMPLETE
Starting HEAD: eb12d4a1aba01921ba6a203ee0f70a04f3c18703

## Scope

Jamon requested Muse quota capability in usage and status, validation, commit and
push. Finish the existing uncommitted October 5 reader rather than duplicate it.
He also requested native models next to their native agents in the model skill,
with Cursor and Devin identified as multi-model harnesses. Record his comparison
of Muse Wonder at xhigh to GPT-6.1 Sol; revisit rankings together after this work.
Preserve the untracked Antigravity adapter and .DS_Store files.

## Implementation and evidence

Muse reads official MSP usage/read first, then its supported /usage screen in a
disposable controlling PTY when no unexpired observation exists. No prompt,
reset, authentication change or private API is used. Preserve quota timestamps
and literal reset text; token counts alone are never account quota. Terminal
negotiation now handles split reads, and killed PTY children are reaped.

Usage and status already share the collector, including Muse in aggregates.
Extend existing integration tests to prove Muse-specific status and missing
quota behavior using the real reader with native-shaped fake hosts and PTYs.
The model snapshot uses native CLI/cache catalogs plus already-known families;
separate current Codex entries from legacy families visible in other harnesses.
Do not renew the date of the existing ranking recommendations merely because
the inventory is refreshed.

Official method: https://meta-models.github.io/muse-code-sdk/next/generated/msp/methods/usage-read/
It reads the host's last observation and omits quota when none exists.
Model ownership/availability is distinct; Codex reference:
https://learn.chatgpt.com/docs/models?surface=cli

## Live limitation

Installed Muse is 1.4.7-R6101.1. MSP returns no quota. Its normal fresh /usage
screen currently displays zero session tokens/turns but no subscription panel.
A temporary Spark model selection and contributor-mode-on check did not produce
quota either; no model turn was submitted. Earlier October 5 evidence confirms
the same reader obtained real subscription windows on Muse 1.4.3. Do not claim
that fixtures prove current live quota availability or infer zero account usage.

## Validation

The task-only staged package under /tmp/jamsession-muse-status.szQNxX/jamsession
passed the full existing suite: 502 passed, 0 failed. This includes the added
MSP-to-TUI path, split terminal queries, quota-bearing Muse status, absent-quota
status, aggregate status, and all existing adapters/install/uninstall/messaging
regressions. Both edited skills passed the system validator. Bash and Python
syntax and staged whitespace checks passed.

Manual scope review confirms no model requests or resets in the quota path,
temporary workspace/terminal isolation, observation timestamps, and no fabricated
balance. The native-model inventory keeps ownership separate from harness access
and recommendations; existing rankings and their freshness date remain intact.
The only post-suite changes are this record and shortening the Wonder comparison
note; tested runtime bytes are unchanged. Antigravity and Finder metadata are
excluded from the commit. Commit/push are explicitly authorized for this task;
their exact result is reported in the chat handoff.

The quota-reader capability is implemented and integrated; live subscription
availability on Muse 1.4.7 remains a documented provider limitation. No new
balance is claimed until the provider exposes an observation without a model
turn. Revisit recommendation rankings with Jamon after publication.
