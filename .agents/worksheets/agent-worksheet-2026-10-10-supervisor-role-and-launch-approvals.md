# Supervisor continuity and launch approvals

Status: COMPLETE
Starting HEAD: 54f74f6ee0b596ef86e5a860f0e7b34fc5aca1f8

## Request and scope

Jamon requested implicit orchestration, firm supervisor continuity across steering
and compaction, investigation of Codex Desktop launch-approval stalls, and commit
and push. Keep this a concise skill fix, not an approval subsystem or a behavioral
evaluation campaign. Preserve unrelated Muse/usage and Antigravity work.

## Changes

Remove orchestration's explicit-only metadata. Include ongoing orchestration in
the trigger; steering changes tasks, not roles. Keep the supervisor out of code,
tests and commits unless the user changes its role. Retain role and exact manager
IDs in existing task records. Replace the direct-implementation escape clause
with batching through an existing manager. Align Codex follow-ups with the summon
skill's run-first guidance.

The summon skill now prefers simple direct commands, separates parent launch
approval from child permissions, prohibits alternate-tool approval workarounds,
and requires an authorized representative launch before promising unattended
readiness. Genuine provider consent remains reusable; no policy settings change.

## Findings and limits

The October 9 consent commit (4a964a9) added caller-visible provider/data-scope
guidance and entry-point links, not runtime approval settings. It expressly
reuses genuine selected-provider consent. This could affect an agent's launch
reasoning, but does not prove the friend's reported regression.

Official Codex command rules distinguish simple argv from complex shell scripts:
https://learn.chatgpt.com/docs/agent-configuration/rules
Auto-review sees the action and compact transcript, and a denial must not be
routed around: https://learn.chatgpt.com/docs/sandboxing/auto-review

The friend's exact failed command, approval rationale and Desktop permission
configuration are unavailable. Command formatting is a plausible contributor,
not a confirmed root cause; no model-specific regression or guaranteed approval
is claimed. No secrets, rules files or private transcripts were collected.

## Validation

Both changed packages passed the system skill validator using the existing
Homebrew Python with PyYAML. Their UI metadata parsed, with default implicit
invocation confirmed enabled. Focused whitespace checks passed. Manual review
covered follow-up corrections, compaction, blocked delegation, reused consent,
changed provider/data scope, and approval denial; no direct-implementation escape
or alternate-tool approval workaround remains. The first validator attempt used
a Python without PyYAML; the existing Homebrew interpreter resolved it without
installing dependencies. No runtime code changes or live provider launches were
needed. Publication excludes unrelated working-tree changes.

Gunship's checkout also has a Claude explicit-only override and older copies of
these packages. It has unrelated unpublished shader commits; this task publishes
the canonical Jam Session fix only, without publishing or modifying that work.
A Gunship refresh must update its Claude override alongside the source packages.
