# Codex launch permissions

Status: COMPLETE
Starting HEAD: 92b41bb7419c978c058328721cbd560e54838c52

Jamon explicitly authorized edit workers to honor configured full-access/never
on this isolated machine. Work only in Jam Session; no night-shift restart,
Archie messages, implementation workers, global Codex edits or Gunship edits.

## Trace and plan

Installed and source adapters match. Gunship night-shift run_control_turn calls
the installed CLI with new/low/edit. Both CLI paths force workspace-write and
never; the control-resume helper also creates a workspace-only policy. Saved
user config instead specifies danger-full-access/never. The supplied controller
log reports Seatbelt denials and FETCH_HEAD write failure, not Auto-review.

Delegate fresh edit configuration to Codex's native loader, including selected
profile and explicit scoped overrides. Preserve saved control-resume permissions;
explicit launch overrides select native CLI resume before any send. Enforce read
regardless of edit configuration, including legacy sandbox=off. Preserve busy,
denial and cold-start restoration guards. Test through fake providers/control
peers and native config-only probes; no model turns required.

## Evidence

Official config precedence: https://learn.chatgpt.com/docs/config-file/config-basic
Permission-profile/legacy precedence: https://learn.chatgpt.com/docs/permissions

## Validation

- Initial full package suite: 612 checks passed. Fresh/resume launch tests and
  socket-peer tests cover native delegation, overrides, read access, cold full
  access/never, existing custom-profile rejection and denial/uncertain sends.
- Native config/read without a model turn confirmed operator edit config:
  danger-full-access/never. Read selectors resolve read-only/never.
- Native debug prompt-input in an isolated temporary Codex home confirmed a
  valid automation.config.toml profile selects full access, and an explicit
  config override selects workspace-write. No model or implementation worker
  was launched. app-server does not support --profile, so explicit-profile
  resumes deliberately use the native runtime CLI, never a guessed RPC policy.
- Native missing-profile probing silently fell back. Added an explicit readable
  profile-file guard and native --strict-config; missing profile now fails before
  launch. Focused suites pass 9 launch cases and 29 control cases.
- Final full suite after the final guards: 612 passed, zero failed. Shell syntax,
  skill-creator validation and diff whitespace checks passed. Self-review verified
  no new config parser/framework, no altered busy/denial retry gates, and no
  change to saved cold-start restoration checks. Native Codex owns config merging;
  the small adapter surface forwards overrides rather than reconstructing policy.
- No global Codex configuration
  or Gunship files changed. User config SHA256 before installed update:
  4f74740ecf4a7f33ee521a7a390a66218653fb392afbdaa7499788433fe0071f.

## Changed files and handoff

adapters/jamsession_codex; adapters/_jamsession_codex_control.py; jamsession;
skills/jamsession-summon-agent/SKILL.md; README.md; tests/test_jamsession.sh;
tests/test_codex_control.py; tests/test_codex_launch_settings.py; this worksheet.

Publish the scoped fix and verify normal installed update against the exact
committed files. Re-run the launch-boundary fixtures against the installed CLI;
do not start a worker or restart the night shift. Unrelated DS_Store files remain
untracked and excluded. User configuration, managed requirements, permission
denials, session writer locks and saved-policy restoration remain authoritative.
