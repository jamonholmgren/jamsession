#!/usr/bin/env bash

set -u

# A developer with Jam Session configured in their own environment must not have
# those values leak into the fixtures. Otherwise the suite writes into the
# checkout instead of its temporary directories.
unset JAMSESSION_HOME JAMSESSION_ADAPTER_DIR JAMSESSION_CONFIG JAMSESSION_SKILL_DIR \
  JAMSESSION_PACK_DIR JAMSESSION_SOURCE_URL JAMSESSION_INSTALL_URL JAMSESSION_CWD \
  JAMSESSION_CODEX_BIN JAMSESSION_CLAUDE_BIN JAMSESSION_CURSOR_BIN \
  JAMSESSION_GROK_BIN JAMSESSION_COPILOT_BIN

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/jamsession-test.XXXXXX")"
trap 'rm -rf "$TEMP_ROOT"' EXIT HUP INT TERM

passed=0
failed=0

pass() { passed=$((passed + 1)); printf 'PASS: %s\n' "$1"; }
fail() { failed=$((failed + 1)); printf 'FAIL: %s\n' "$1" >&2; }

check() {
  local label="$1"
  shift
  if "$@"; then pass "$label"; else fail "$label"; fi
}

run_command() {
  stdout_file="$TEMP_ROOT/stdout"
  stderr_file="$TEMP_ROOT/stderr"
  status=0
  "$@" >"$stdout_file" 2>"$stderr_file" || status=$?
}

contains() { grep -Fq -- "$2" "$1"; }
equals() { [ "$(cat "$1")" = "$2" ]; }

# Modes are asserted, never repaired. A repository file that ships non-executable
# would otherwise be hidden by the test run that fixes it.
check "the CLI ships executable" test -x "$ROOT/jamsession"
check "the installer ships executable" test -x "$ROOT/install.sh"
non_executable_adapter=""
for adapter in "$ROOT"/adapters/jamsession_*; do
  [ -x "$adapter" ] || non_executable_adapter="$adapter"
done
check "every adapter ships executable" test -z "$non_executable_adapter"
check "the adapter helper ships non-executable" test ! -x "$ROOT/adapters/_jamsession_adapter_common"

run_command "$ROOT/jamsession" adapters
check "bundled providers are discovered" contains "$stdout_file" codex
check "adapter helper is not exposed as a provider" sh -c "! grep -Fq _jamsession '$stdout_file'"

run_command "$ROOT/jamsession" providers
check "providers lists the bundled adapters" contains "$stdout_file" claude
cp "$stdout_file" "$TEMP_ROOT/providers-output"
run_command "$ROOT/jamsession" adapters
check "adapters is an exact alias for providers" sh -c "diff -q '$TEMP_ROOT/providers-output' '$stdout_file' >/dev/null"
run_command "$ROOT/jamsession" agents
check "agents remains an exact alias" sh -c "diff -q '$TEMP_ROOT/providers-output' '$stdout_file' >/dev/null"
run_command "$ROOT/jamsession" providers extra
check "providers rejects arguments" test "$status" -eq 2

run_command "$ROOT/jamsession" help
check "main help documents providers" contains "$stdout_file" "jamsession providers"
check "main help notes the adapters alias" contains "$stdout_file" "\`adapters\` is an exact alias"
check "main help does not present adapters as the primary name" sh -c "! grep -q '^  jamsession adapters\$' '$stdout_file'"
check "main help documents skills uninstall" contains "$stdout_file" "uninstall <name|all>"
check "main help no longer documents recommendation packs" sh -c "! grep -Eq 'jamsession (packs|recommend)' '$stdout_file'"

run_command "$ROOT/jamsession" packs
check "the removed packs command is rejected" test "$status" -eq 2

run_command "$ROOT/jamsession" help providers
check "provider help explains the listing" contains "$stdout_file" "Usage: jamsession providers"
check "provider help names the alias" contains "$stdout_file" "exact alias"

run_command "$ROOT/jamsession" help configure
check "configure help does not execute its examples" test ! -s "$stderr_file"
check "configure help includes the init command" contains "$stdout_file" "jamsession init"

run_command "$ROOT/jamsession" run codex new default default maybe prompt
check "invalid access fails" test "$status" -eq 2
check "invalid access prints compact help" contains "$stderr_file" "access must be read or edit"

CUSTOM_HOME="$TEMP_ROOT/custom-home"
run_command env JAMSESSION_HOME="$CUSTOM_HOME" "$ROOT/jamsession" make-adapter antigravity
check "make-adapter creates an executable" test -x "$CUSTOM_HOME/adapters/jamsession_antigravity"
run_command env JAMSESSION_HOME="$CUSTOM_HOME" "$ROOT/jamsession" make-adapter antigravity
check "make-adapter protects an existing file" test "$status" -eq 2
run_command env JAMSESSION_HOME="$CUSTOM_HOME" "$ROOT/jamsession" make-adapter antigravity --force
check "make-adapter force replaces explicitly" test "$status" -eq 0

cat >"$CUSTOM_HOME/adapters/jamsession_echo" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >"$FAKE_LOG"
printf '%s\n' DISPATCH_RESULT
EOF
chmod 755 "$CUSTOM_HOME/adapters/jamsession_echo"
LOG="$TEMP_ROOT/dispatch-args"
run_command env FAKE_LOG="$LOG" JAMSESSION_HOME="$CUSTOM_HOME" \
  "$ROOT/jamsession" run echo new model high read prompt
check "core dispatches without the provider argument" equals "$LOG" "run new model high read prompt"
check "core preserves adapter stdout" equals "$stdout_file" DISPATCH_RESULT

FAKE_BIN="$TEMP_ROOT/bin"
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/codex" <<'EOF'
#!/bin/sh
if [ "${1:-}" = --version ]; then printf '%s\n' CODEX_VERSION; exit 0; fi
if [ "${1:-}" = login ]; then printf '%s\n' CODEX_AUTH_OK; exit 0; fi
last=
take_last=0
for argument in "$@"; do
  if [ "$take_last" -eq 1 ]; then last=$argument; take_last=0; fi
  [ "$argument" = -o ] && take_last=1
done
printf '%s\n' "$*" >"$FAKE_LOG"
printf '%s' CODEX_RESULT >"$last"
printf '%s\n' '{"type":"thread.started","thread_id":"codex-session"}'
exit "${FAKE_EXIT:-0}"
EOF

cat >"$FAKE_BIN/claude" <<'EOF'
#!/bin/sh
if [ "${1:-}" = --version ]; then printf '%s\n' CLAUDE_VERSION; exit 0; fi
if [ "${1:-}" = auth ]; then printf '%s\n' CLAUDE_AUTH_OK; exit 0; fi
printf '%s\n' "$*" >"$FAKE_LOG"
printf '%s\n' CLAUDE_RESULT
exit "${FAKE_EXIT:-0}"
EOF

cat >"$FAKE_BIN/cursor-agent" <<'EOF'
#!/bin/sh
if [ "${1:-}" = create-chat ]; then printf '%s\n' cursor-session; exit 0; fi
if [ "${1:-}" = --list-models ]; then printf '%s\n' CURSOR_MODELS; exit 0; fi
if [ "${1:-}" = status ]; then printf '%s\n' CURSOR_AUTH_OK; exit 0; fi
printf '%s\n' "$*" >"$FAKE_LOG"
printf '%s\n' "$#" >"$FAKE_LOG.count"
shift $(($# - 1))
printf '%s' "$1" >"$FAKE_LOG.last"
printf '%s\n' '{"type":"result","result":"CURSOR_RESULT\n\"quoted\" \\ path"}'
exit "${FAKE_EXIT:-0}"
EOF

cat >"$FAKE_BIN/grok" <<'EOF'
#!/bin/sh
case "${1:-}" in
  --version) printf '%s\n' GROK_VERSION; exit 0 ;;
  sessions) printf '%s\n' GROK_SESSIONS; exit 0 ;;
  models) printf '%s\n' GROK_MODELS; exit 0 ;;
  doctor) printf '%s\n' GROK_DOCTOR_OK; exit 0 ;;
esac
printf '%s\n' "$*" >"$FAKE_LOG"
printf '%s\n' GROK_RESULT
exit "${FAKE_EXIT:-0}"
EOF

cat >"$FAKE_BIN/copilot" <<'EOF'
#!/bin/sh
case "${1:-}" in --version) printf '%s\n' COPILOT_VERSION; exit 0 ;; esac
printf '%s\n' "$*" >"$FAKE_LOG"
printf '%s\n' COPILOT_RESULT
exit "${FAKE_EXIT:-0}"
EOF
chmod 755 "$FAKE_BIN"/*

LOG="$TEMP_ROOT/args"

run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/adapters/jamsession_codex" run new default high read prompt
check "Codex final response is normalized" equals "$stdout_file" CODEX_RESULT
check "Codex new session ID is reported" contains "$stderr_file" "session: codex-session"
check "Codex read mode uses native read-only sandbox" contains "$LOG" "-s read-only"

run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/adapters/jamsession_claude" run new default high read prompt
check "Claude response passes through" contains "$stdout_file" CLAUDE_RESULT
check "Claude read mode uses plan permissions" contains "$LOG" "--permission-mode plan"
check "Claude session ID is a UUID" grep -Eq 'session: [0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}' "$stderr_file"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/adapters/jamsession_claude" run new default none read prompt
check "Claude rejects an unsupported explicit effort" test "$status" -eq 2
check "Claude names the rejected effort" contains "$stderr_file" "no none effort"
check "a rejected Claude run never invokes the provider CLI" test ! -e "$LOG"

run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new cursor-model high read prompt
check "Cursor creates and reports a native session" contains "$stderr_file" "session: cursor-session"
check "Cursor explicit effort is encoded in the model" contains "$LOG" "cursor-model[effort=high]"
check "Cursor read mode uses ask mode" contains "$LOG" "--mode ask"
check "Cursor read mode does not force tool approval" sh -c "! grep -Fq -- '--force' '$LOG'"
check "Cursor JSON result is decoded without dependencies" equals "$stdout_file" 'CURSOR_RESULT
"quoted" \ path'

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new default high read prompt
check "Cursor rejects effort without a model" test "$status" -eq 2
check "Cursor explains the model requirement" contains "$stderr_file" "explicit effort needs an explicit model"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new 'cursor-model[effort=low]' high read prompt
check "Cursor rejects effort on an overridden model" test "$status" -eq 2
check "Cursor explains the override conflict" contains "$stderr_file" "already contains overrides"
check "a rejected Cursor run creates no chat session" sh -c "! grep -Fq 'session:' '$stderr_file'"

# Establish how many arguments a one-word prompt produces, so the stdin case can
# prove it adds exactly one more rather than word-splitting into several.
rm -f "$LOG" "$LOG.last" "$LOG.count"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new default default read single
baseline_count="$(cat "$LOG.count")"
check "a one-word prompt is the final argument" equals "$LOG.last" single

PIPED_PROMPT='piped prompt with spaces $(touch /dev/null) "quotes" & | ; * ~
and a second line'
rm -f "$LOG" "$LOG.last" "$LOG.count"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  PIPED_PROMPT="$PIPED_PROMPT" sh -c \
  'printf "%s" "$PIPED_PROMPT" | "$0" run new default default read -' \
  "$ROOT/adapters/jamsession_cursor"
check "stdin prompt arrives whole as the final argument" equals "$LOG.last" "$PIPED_PROMPT"
check "stdin prompt is neither word-split nor glob-expanded" equals "$LOG.count" "$baseline_count"

run_command env FAKE_LOG="$LOG" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  "$ROOT/adapters/jamsession_grok" run new default high read prompt
check "Grok rejects unenforceable read access" test "$status" -eq 2
check "Grok explains the read rejection" contains "$stderr_file" "cannot guarantee no writes"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  "$ROOT/adapters/jamsession_grok" run new default xhigh edit prompt
check "Grok rejects an effort above its ceiling" test "$status" -eq 2
check "Grok states its effort ceiling" contains "$stderr_file" "up to high effort"
check "a rejected Grok run never invokes the provider CLI" test ! -e "$LOG"

run_command env FAKE_LOG="$LOG" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  "$ROOT/adapters/jamsession_grok" run new default high edit prompt
check "Grok passes a supported effort natively" contains "$LOG" "--reasoning-effort high"

run_command env FAKE_LOG="$LOG" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  "$ROOT/adapters/jamsession_grok" list 7
check "Grok uses its native session list" contains "$stdout_file" GROK_SESSIONS

run_command env FAKE_LOG="$LOG" JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" \
  "$ROOT/adapters/jamsession_copilot" run new auto default read prompt
check "Copilot rejects unverified read access" test "$status" -eq 2

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" \
  "$ROOT/adapters/jamsession_copilot" run new auto high edit prompt
check "Copilot rejects explicit effort with the auto model" test "$status" -eq 2
check "Copilot explains the auto conflict" contains "$stderr_file" "auto model"
check "a rejected Copilot run never invokes the provider CLI" test ! -e "$LOG"

run_command env FAKE_LOG="$LOG" JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" \
  "$ROOT/adapters/jamsession_copilot" run new auto default edit prompt
check "Copilot response passes through" contains "$stdout_file" COPILOT_RESULT
check "Copilot edit mode allows tools" contains "$LOG" "--allow-all-tools"
check "Copilot auto model sends no effort flag" sh -c "! grep -Fq -- '--effort' '$LOG'"

run_command env FAKE_LOG="$LOG" JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" \
  "$ROOT/adapters/jamsession_copilot" run new copilot-model high edit prompt
check "Copilot passes explicit effort with a named model" contains "$LOG" "--effort high"

run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/adapters/jamsession_codex" doctor
check "Codex doctor checks native authentication" contains "$stdout_file" CODEX_AUTH_OK

run_command env JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/adapters/jamsession_codex" usage
check "unsupported operations return the standard status" test "$status" -eq 3
check "unsupported operations explain the limitation" contains "$stderr_file" "not available from this provider CLI"

run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/adapters/jamsession_claude" doctor
check "Claude doctor checks native authentication" contains "$stdout_file" "authentication: ready"

run_command env FAKE_LOG="$LOG" FAKE_EXIT=17 JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/adapters/jamsession_claude" run saved-session default default edit prompt
check "provider exit status is preserved" test "$status" -eq 17
check "resumed session ID is preserved" contains "$stderr_file" "session: saved-session"

INIT_HOME="$TEMP_ROOT/init-home"
run_command env HOME="$TEMP_ROOT/user" JAMSESSION_HOME="$INIT_HOME" \
  PATH="$FAKE_BIN:/usr/bin:/bin" "$ROOT/jamsession" init
check "init creates shell configuration" test -f "$INIT_HOME/jamsession.conf"
check "init records discovered Codex path" contains "$INIT_HOME/jamsession.conf" JAMSESSION_CODEX_BIN
before="$(cat "$INIT_HOME/jamsession.conf")"
run_command env HOME="$TEMP_ROOT/user" JAMSESSION_HOME="$INIT_HOME" \
  PATH="$FAKE_BIN:/usr/bin:/bin" "$ROOT/jamsession" init
check "init is idempotent" test "$(cat "$INIT_HOME/jamsession.conf")" = "$before"

INSTALL_HOME="$TEMP_ROOT/install-user"
mkdir -p "$INSTALL_HOME/.agents/jamsession/adapters"
printf '%s\n' custom >"$INSTALL_HOME/.agents/jamsession/adapters/jamsession_custom"
chmod 755 "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_custom"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "installer installs the command" test -x "$INSTALL_HOME/.agents/jamsession/bin/jamsession"
check "installer links the command" test -L "$INSTALL_HOME/.local/bin/jamsession"
check "installer preserves unknown adapters" equals "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_custom" custom
check "installer installs the summon-agent skill" test -f "$INSTALL_HOME/.agents/skills/jamsession-summon-agent/SKILL.md"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install jamsession-work-over-ssh
check "optional skill installs on request" test -f "$INSTALL_HOME/.agents/skills/jamsession-work-over-ssh/SKILL.md"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" "$ROOT/jamsession" skills
check "skills lists installed state" contains "$stdout_file" "jamsession-work-over-ssh"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install jamsession-model-recommendations
check "model-recommendations skill installs on request" test -f "$INSTALL_HOME/.agents/skills/jamsession-model-recommendations/SKILL.md"
check "model recommendations carry a freshness date" contains "$INSTALL_HOME/.agents/skills/jamsession-model-recommendations/SKILL.md" "fresh as of September 5, 2026"

# --- Second run: recognized files refresh, everything else survives ---
INSTALLED="$INSTALL_HOME/.agents/jamsession"
INSTALLED_SKILLS="$INSTALL_HOME/.agents/skills"
printf '%s\n' stale >"$INSTALLED/bin/jamsession"
printf '%s\n' stale >"$INSTALLED/adapters/jamsession_codex"
printf '%s\n' stale >"$INSTALLED/adapters/_jamsession_adapter_common"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-summon-agent/SKILL.md"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-work-over-ssh/SKILL.md"
printf '%s\n' 'JAMSESSION_CUSTOM_SETTING=kept' >>"$INSTALLED/jamsession.conf"

run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "a second install succeeds" test "$status" -eq 0
check "second install refreshes the command" contains "$INSTALLED/bin/jamsession" JAMSESSION_VERSION
check "second install refreshes a bundled adapter" contains "$INSTALLED/adapters/jamsession_codex" jamsession_validate_run
check "second install refreshes the adapter helper" contains "$INSTALLED/adapters/_jamsession_adapter_common" jamsession_adapter_setup
check "second install refreshes the default skill" contains "$INSTALLED_SKILLS/jamsession-summon-agent/SKILL.md" "name: jamsession-summon-agent"
check "second install refreshes an installed optional skill" contains "$INSTALLED_SKILLS/jamsession-work-over-ssh/SKILL.md" "name: jamsession-work-over-ssh"
check "second install preserves configuration" contains "$INSTALLED/jamsession.conf" JAMSESSION_CUSTOM_SETTING=kept
check "second install preserves a custom adapter" equals "$INSTALLED/adapters/jamsession_custom" custom
check "second install leaves uninstalled optional skills absent" test ! -e "$INSTALLED_SKILLS/jamsession-ask-agent-panel/SKILL.md"
check "second install leaves no staging files behind" sh -c "! ls '$INSTALLED/bin/'*.jamsession-new '$INSTALLED/adapters/'*.jamsession-new >/dev/null 2>&1"
check "installed command stays executable" test -x "$INSTALLED/bin/jamsession"
check "installed adapters stay executable" test -x "$INSTALLED/adapters/jamsession_codex"
check "installed adapter helper stays non-executable" test ! -x "$INSTALLED/adapters/_jamsession_adapter_common"

# --- An incomplete bundle must replace nothing ---
BROKEN_SOURCE="$TEMP_ROOT/broken-source"
mkdir -p "$BROKEN_SOURCE"
cp "$ROOT/jamsession" "$BROKEN_SOURCE/jamsession"
cp -R "$ROOT/adapters" "$ROOT/skills" "$BROKEN_SOURCE/"
rm -f "$BROKEN_SOURCE/adapters/jamsession_grok"
printf '%s\n' stale >"$INSTALLED/bin/jamsession"
printf '%s\n' stale >"$INSTALLED/adapters/jamsession_codex"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$BROKEN_SOURCE" sh "$ROOT/install.sh"
check "an incomplete bundle fails the install" test "$status" -ne 0
check "a failed install says nothing changed" contains "$stderr_file" "nothing installed was changed"
check "a failed install replaces no command" equals "$INSTALLED/bin/jamsession" stale
check "a failed install replaces no adapter" equals "$INSTALLED/adapters/jamsession_codex" stale

run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "a later complete install recovers" contains "$INSTALLED/bin/jamsession" JAMSESSION_VERSION

missing_skill=""
while IFS= read -r listed_skill; do
  listed_skill="${listed_skill%% *}"
  [ -n "$listed_skill" ] || continue
  [ -f "$ROOT/skills/$listed_skill/SKILL.md" ] || missing_skill="$listed_skill"
done < <(env JAMSESSION_SKILL_DIR="$TEMP_ROOT/none" "$ROOT/jamsession" skills)
check "every listed skill exists in the repository" test -z "$missing_skill"

missing_install=""
while IFS= read -r listed_skill; do
  listed_skill="${listed_skill%% *}"
  [ -n "$listed_skill" ] || continue
  grep -Fq -- "$listed_skill" "$ROOT/install.sh" || missing_install="$listed_skill"
done < <(env JAMSESSION_SKILL_DIR="$TEMP_ROOT/none" "$ROOT/jamsession" skills)
check "every listed skill is known to the installer" test -z "$missing_install"

# --- skills uninstall --------------------------------------------------------
# A skill directory holding bundled skills, a custom prefixed skill, and skills
# Jam Session must never remove.
SKILLS_ONLY="$TEMP_ROOT/skills-only"
build_skill_dir() {
  rm -rf "$SKILLS_ONLY"
  mkdir -p "$SKILLS_ONLY/jamsession-summon-agent" "$SKILLS_ONLY/jamsession-work-over-ssh" \
    "$SKILLS_ONLY/jamsession-my-custom" "$SKILLS_ONLY/my-own-skill" \
    "$SKILLS_ONLY/notjamsession-thing"
  printf -- '---\nname: jamsession-summon-agent\n---\n' >"$SKILLS_ONLY/jamsession-summon-agent/SKILL.md"
  printf -- '---\nname: jamsession-work-over-ssh\n---\n' >"$SKILLS_ONLY/jamsession-work-over-ssh/SKILL.md"
  printf -- '---\nname: jamsession-my-custom\n---\n' >"$SKILLS_ONLY/jamsession-my-custom/SKILL.md"
  printf -- '---\nname: my-own-skill\n---\n' >"$SKILLS_ONLY/my-own-skill/SKILL.md"
  printf -- '---\nname: notjamsession-thing\n---\n' >"$SKILLS_ONLY/notjamsession-thing/SKILL.md"
  printf '%s\n' loose >"$SKILLS_ONLY/loose-file.md"
}

run_skills() {
  run_command env JAMSESSION_SKILL_DIR="$SKILLS_ONLY" "$ROOT/jamsession" skills "$@"
}

build_skill_dir
run_skills uninstall jamsession-work-over-ssh
check "named skill uninstall succeeds" test "$status" -eq 0
check "named skill uninstall removes the directory" test ! -e "$SKILLS_ONLY/jamsession-work-over-ssh"
check "named skill uninstall reports the path" contains "$stdout_file" "jamsession-work-over-ssh"
check "named skill uninstall keeps other bundled skills" test -f "$SKILLS_ONLY/jamsession-summon-agent/SKILL.md"
check "named skill uninstall keeps unrelated skills" test -f "$SKILLS_ONLY/my-own-skill/SKILL.md"

run_skills uninstall jamsession-work-over-ssh
check "uninstalling a missing skill fails clearly" test "$status" -eq 1
check "uninstalling a missing skill says so" contains "$stderr_file" "is not installed"

run_skills uninstall jamsession-my-custom
check "a custom prefixed skill can be named" test "$status" -eq 0
check "a custom prefixed skill is removed" test ! -e "$SKILLS_ONLY/jamsession-my-custom"

# Names outside the namespace, and anything path-shaped, are refused outright.
build_skill_dir
for bad_name in my-own-skill notjamsession-thing jamsession ../../etc /etc/passwd \
  "jamsession-../escape" "jamsession-a/b" "jamsession-..";
do
  run_skills uninstall "$bad_name"
  check "skills uninstall rejects '$bad_name'" test "$status" -eq 2
done
check "a rejected name removes nothing" test -f "$SKILLS_ONLY/my-own-skill/SKILL.md"
check "a rejected name leaves bundled skills alone" test -f "$SKILLS_ONLY/jamsession-summon-agent/SKILL.md"
check "a rejected name leaves the lookalike alone" test -f "$SKILLS_ONLY/notjamsession-thing/SKILL.md"

run_skills uninstall
check "skills uninstall requires an argument" test "$status" -eq 2

run_skills uninstall jamsession-summon-agent extra
check "skills uninstall rejects extra arguments" test "$status" -eq 2

# `all` covers every prefixed directory, including custom ones, and nothing else.
build_skill_dir
printf '%s\n' notes >"$SKILLS_ONLY/jamsession-summon-agent/NOTES.md"
run_skills uninstall all
check "skills uninstall all succeeds" test "$status" -eq 0
check "all removes a bundled skill" test ! -e "$SKILLS_ONLY/jamsession-summon-agent"
check "all removes a second bundled skill" test ! -e "$SKILLS_ONLY/jamsession-work-over-ssh"
check "all removes a custom prefixed skill" test ! -e "$SKILLS_ONLY/jamsession-my-custom"
check "all announces removing extra files" contains "$stdout_file" "including files Jam Session did not install"
check "all keeps an unrelated skill" test -f "$SKILLS_ONLY/my-own-skill/SKILL.md"
check "all keeps a lookalike prefix" test -f "$SKILLS_ONLY/notjamsession-thing/SKILL.md"
check "all keeps loose files in the skill directory" equals "$SKILLS_ONLY/loose-file.md" loose
check "all keeps the skill directory itself" test -d "$SKILLS_ONLY"

run_skills uninstall all
check "a second skills uninstall all succeeds" test "$status" -eq 0
check "a second all reports nothing to remove" contains "$stdout_file" "No jamsession-* skills"
check "a second all still keeps unrelated skills" test -f "$SKILLS_ONLY/my-own-skill/SKILL.md"

# A symlink is never followed or removed as if it were a skill directory.
build_skill_dir
mkdir -p "$TEMP_ROOT/link-target"
printf '%s\n' precious >"$TEMP_ROOT/link-target/keep.txt"
ln -sfn "$TEMP_ROOT/link-target" "$SKILLS_ONLY/jamsession-linked"
run_skills uninstall all
check "all refuses a symlinked skill" test "$status" -eq 1
check "all keeps the symlink" test -L "$SKILLS_ONLY/jamsession-linked"
check "all never touches the symlink target" equals "$TEMP_ROOT/link-target/keep.txt" precious

run_command env JAMSESSION_SKILL_DIR="$TEMP_ROOT/no-such-skill-dir" \
  "$ROOT/jamsession" skills uninstall all
check "skills uninstall all tolerates a missing directory" test "$status" -eq 0

run_command env JAMSESSION_SKILL_DIR="$ROOT/skills" "$ROOT/jamsession" skills uninstall all
check "skills uninstall refuses a checkout skill directory" test "$status" -eq 2
check "the checkout skills survived" test -f "$ROOT/skills/jamsession-summon-agent/SKILL.md"

run_command env JAMSESSION_SKILL_DIR="relative/skills" "$ROOT/jamsession" skills uninstall all
check "skills uninstall refuses a relative skill directory" test "$status" -eq 2

run_command "$ROOT/jamsession" help skills
check "skill help documents uninstall" contains "$stdout_file" "uninstall <name|all>"
check "skill help states the prefix rule" contains "$stdout_file" "jamsession-"
check "skill help explains whole-directory removal" contains "$stdout_file" "removed with it"

# --- uninstall ---------------------------------------------------------------
# Every scenario gets its own private HOME holding a complete installation plus
# artifacts Jam Session must never touch.
build_installation() {
  rm -rf "$1"
  mkdir -p "$1"
  env HOME="$1" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh" >/dev/null 2>&1
  env HOME="$1" JAMSESSION_HOME="$1/.agents/jamsession" \
    JAMSESSION_SKILL_DIR="$1/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
    "$ROOT/jamsession" skills install jamsession-work-over-ssh >/dev/null 2>&1
  mkdir -p "$1/.agents/skills/my-own-skill"
  printf -- '---\nname: my-own-skill\n---\n' >"$1/.agents/skills/my-own-skill/SKILL.md"
  printf '%s\n' keep >"$1/.agents/keep-me.txt"
  printf '%s\n' custom >"$1/.agents/jamsession/adapters/jamsession_custom"
}

run_uninstall() {
  run_command env HOME="$1" JAMSESSION_HOME="$1/.agents/jamsession" \
    JAMSESSION_SKILL_DIR="$1/.agents/skills" "$ROOT/jamsession" uninstall
}

UNINSTALL_HOME="$TEMP_ROOT/uninstall-user"
build_installation "$UNINSTALL_HOME"
check "the fixture installed the command" test -x "$UNINSTALL_HOME/.agents/jamsession/bin/jamsession"
check "the fixture installed an optional skill" test -f "$UNINSTALL_HOME/.agents/skills/jamsession-work-over-ssh/SKILL.md"

run_uninstall "$UNINSTALL_HOME"
check "uninstall succeeds on a clean installation" test "$status" -eq 0
check "uninstall reports completion" contains "$stdout_file" "Jam Session is uninstalled."
check "uninstall removes the installation tree" test ! -e "$UNINSTALL_HOME/.agents/jamsession"
check "uninstall removes the command symlink" test ! -e "$UNINSTALL_HOME/.local/bin/jamsession"
check "uninstall removes the default skill" test ! -e "$UNINSTALL_HOME/.agents/skills/jamsession-summon-agent"
check "uninstall removes an installed optional skill" test ! -e "$UNINSTALL_HOME/.agents/skills/jamsession-work-over-ssh"
check "uninstall keeps an unrelated skill" contains "$UNINSTALL_HOME/.agents/skills/my-own-skill/SKILL.md" "name: my-own-skill"
check "uninstall keeps the skill directory itself" test -d "$UNINSTALL_HOME/.agents/skills"
check "uninstall keeps the agents directory" test -d "$UNINSTALL_HOME/.agents"
check "uninstall keeps unrelated files under the agents directory" equals "$UNINSTALL_HOME/.agents/keep-me.txt" keep
check "uninstall keeps the local bin directory" test -d "$UNINSTALL_HOME/.local/bin"

run_uninstall "$UNINSTALL_HOME"
check "a second uninstall succeeds" test "$status" -eq 0
check "a second uninstall reports the missing tree" contains "$stderr_file" "no installation tree"
check "a second uninstall still keeps the unrelated skill" test -f "$UNINSTALL_HOME/.agents/skills/my-own-skill/SKILL.md"

# A jamsession-* directory is Jam Session's, so files kept inside it are removed
# with it and the removal is announced.
build_installation "$UNINSTALL_HOME"
printf '%s\n' notes >"$UNINSTALL_HOME/.agents/skills/jamsession-summon-agent/NOTES.md"
run_uninstall "$UNINSTALL_HOME"
check "extra files do not block uninstall" test "$status" -eq 0
check "uninstall removes a skill directory holding other files" test ! -e "$UNINSTALL_HOME/.agents/skills/jamsession-summon-agent"
check "uninstall says the extra files went with it" contains "$stdout_file" "including files Jam Session did not install"
check "uninstall still removes the installation tree" test ! -e "$UNINSTALL_HOME/.agents/jamsession"

# Ownership is the jamsession- prefix, not the bundled list or the name field.
build_installation "$UNINSTALL_HOME"
mkdir -p "$UNINSTALL_HOME/.agents/skills/jamsession-my-custom" \
  "$UNINSTALL_HOME/.agents/skills/notjamsession-thing"
printf -- '---\nname: jamsession-my-custom\n---\n' \
  >"$UNINSTALL_HOME/.agents/skills/jamsession-my-custom/SKILL.md"
printf -- '---\nname: notjamsession-thing\n---\n' \
  >"$UNINSTALL_HOME/.agents/skills/notjamsession-thing/SKILL.md"
run_uninstall "$UNINSTALL_HOME"
check "uninstall removes a custom prefixed skill" test ! -e "$UNINSTALL_HOME/.agents/skills/jamsession-my-custom"
check "uninstall keeps a skill that only looks prefixed" contains "$UNINSTALL_HOME/.agents/skills/notjamsession-thing/SKILL.md" "name: notjamsession-thing"

# An unrelated file at the link path is never removed.
build_installation "$UNINSTALL_HOME"
rm -f "$UNINSTALL_HOME/.local/bin/jamsession"
printf '%s\n' 'my own script' >"$UNINSTALL_HOME/.local/bin/jamsession"
run_uninstall "$UNINSTALL_HOME"
check "uninstall reports the untouched bin file" test "$status" -eq 1
check "uninstall keeps a non-symlink at the link path" equals "$UNINSTALL_HOME/.local/bin/jamsession" "my own script"
check "uninstall says why the bin file was kept" contains "$stderr_file" "not a symlink"

# A symlink pointing at something else is never removed.
build_installation "$UNINSTALL_HOME"
mkdir -p "$UNINSTALL_HOME/elsewhere"
printf '%s\n' other >"$UNINSTALL_HOME/elsewhere/jamsession"
ln -sfn "$UNINSTALL_HOME/elsewhere/jamsession" "$UNINSTALL_HOME/.local/bin/jamsession"
run_uninstall "$UNINSTALL_HOME"
check "uninstall reports the untouched symlink" test "$status" -eq 1
check "uninstall keeps a symlink to another target" equals "$UNINSTALL_HOME/elsewhere/jamsession" other
check "uninstall keeps the foreign symlink itself" test -L "$UNINSTALL_HOME/.local/bin/jamsession"
check "uninstall says the symlink did not match" contains "$stderr_file" "does not point at this installation"

# Source-checkout safety. The checkout must survive every one of these.
SAFE_HOME="$TEMP_ROOT/safe-home"
mkdir -p "$SAFE_HOME"
run_command env HOME="$SAFE_HOME" "$ROOT/jamsession" uninstall
check "uninstall refuses to remove a source checkout it detected" test "$status" -eq 2
check "uninstall names the checkout marker" contains "$stderr_file" "source checkout"

run_command env HOME="$SAFE_HOME" JAMSESSION_HOME="$ROOT" "$ROOT/jamsession" uninstall
check "uninstall refuses an explicit source checkout" test "$status" -eq 2

build_installation "$UNINSTALL_HOME"
run_command env HOME="$UNINSTALL_HOME" JAMSESSION_HOME="$UNINSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$ROOT/skills" "$ROOT/jamsession" uninstall
check "uninstall refuses a checkout skills directory" test "$status" -eq 2
check "uninstall explains the refused skills directory" contains "$stderr_file" "source checkout"

# These must be stopped by the root guard itself, so they assert its wording
# rather than accepting a refusal from some later check.
run_command env HOME="$UNINSTALL_HOME" JAMSESSION_HOME="$UNINSTALL_HOME" "$ROOT/jamsession" uninstall
check "uninstall refuses a home directory as the tree" test "$status" -eq 2
check "the root guard refuses the home directory" contains "$stderr_file" "refusing to touch"

run_command env HOME="$UNINSTALL_HOME" JAMSESSION_HOME="$UNINSTALL_HOME/.agents" "$ROOT/jamsession" uninstall
check "uninstall refuses the agents directory as the tree" test "$status" -eq 2
check "the root guard refuses the agents directory" contains "$stderr_file" "refusing to touch"

# Without the guard, a skill root of $HOME would walk bundled names through the
# home directory itself.
run_command env HOME="$UNINSTALL_HOME" JAMSESSION_HOME="$UNINSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$UNINSTALL_HOME" "$ROOT/jamsession" uninstall
check "uninstall refuses a home directory as the skill root" test "$status" -eq 2
check "the root guard refuses the home skill root" contains "$stderr_file" "refusing to touch"

# The marker guard is the only thing standing between uninstall and a checkout
# that someone has also installed into.
CHECKOUT_LIKE="$TEMP_ROOT/checkout-like/jamsession"
mkdir -p "$CHECKOUT_LIKE/bin" "$CHECKOUT_LIKE/adapters"
printf '%s\n' '#!/bin/sh' >"$CHECKOUT_LIKE/bin/jamsession"
printf '%s\n' 'source' >"$CHECKOUT_LIKE/install.sh"
printf '%s\n' 'work' >"$CHECKOUT_LIKE/my-work.txt"
run_command env HOME="$SAFE_HOME" JAMSESSION_HOME="$CHECKOUT_LIKE" "$ROOT/jamsession" uninstall
check "uninstall refuses a checkout that also has bin/jamsession" test "$status" -eq 2
check "uninstall blames the checkout marker" contains "$stderr_file" "source checkout"
check "the checkout-like tree is untouched" equals "$CHECKOUT_LIKE/my-work.txt" work

run_command env HOME="$UNINSTALL_HOME" JAMSESSION_HOME="relative/path" "$ROOT/jamsession" uninstall
check "uninstall refuses a relative tree path" test "$status" -eq 2

check "the source checkout survived every refusal" test -x "$ROOT/jamsession"
check "the checkout skills survived every refusal" test -f "$ROOT/skills/jamsession-summon-agent/SKILL.md"
check "the checkout worker-task skill survived every refusal" test -f "$ROOT/skills/jamsession-agent-worker-task/SKILL.md"
check "the refused installation was left alone" test -x "$UNINSTALL_HOME/.agents/jamsession/bin/jamsession"

run_command env HOME="$UNINSTALL_HOME" "$ROOT/jamsession" help uninstall
check "uninstall help lists what it removes" contains "$stdout_file" "Removes only what the installer created"
check "uninstall help states the safety rule" contains "$stdout_file" "never removes"
run_command env HOME="$UNINSTALL_HOME" "$ROOT/jamsession" help
check "main help lists uninstall" contains "$stdout_file" "jamsession uninstall"

check "the site workflow ships the install guide linked from the home page" \
  sh -c "grep -Fq 'install.md' '$ROOT/.github/workflows/pages.yml'"
check "the test workflow runs the current test path" \
  sh -c "grep -Fq 'tests/test_jamsession.sh' '$ROOT/.github/workflows/test.yml'"
check "no workflow still refers to the old name" \
  sh -c "! grep -rqi jamwrap '$ROOT/.github/workflows/'"
check "the model recommendation skill is bundled" \
  sh -c "grep -q '^name: jamsession-model-recommendations$' '$ROOT/skills/jamsession-model-recommendations/SKILL.md'"
check "the remote-agent skill depends on no separately optional skill" \
  sh -c "! grep -Eq 'jamsession-(agent-worker-task|work-over-ssh|orchestrate-agent-work)' '$ROOT/skills/jamsession-run-remote-agents/SKILL.md'"

printf '\n%d passed, %d failed\n' "$passed" "$failed"
[ "$failed" -eq 0 ]
