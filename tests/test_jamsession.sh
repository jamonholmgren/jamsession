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
check "the bundled pack ships non-executable" test ! -x "$ROOT/packs/jamon.tsv"

run_command "$ROOT/jamsession" adapters
check "bundled providers are discovered" contains "$stdout_file" codex
check "adapter helper is not exposed as a provider" sh -c "! grep -Fq _jamsession '$stdout_file'"

run_command "$ROOT/jamsession" providers
check "providers is an adapter-list alias" contains "$stdout_file" claude
run_command "$ROOT/jamsession" agents
check "agents is an adapter-list alias" contains "$stdout_file" copilot

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
mkdir -p "$INSTALL_HOME/.agents/jamsession/packs"
printf '%s\n' custom-pack >"$INSTALL_HOME/.agents/jamsession/packs/mine.tsv"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "installer installs the command" test -x "$INSTALL_HOME/.agents/jamsession/bin/jamsession"
check "installer links the command" test -L "$INSTALL_HOME/.local/bin/jamsession"
check "installer preserves unknown adapters" equals "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_custom" custom
check "installer installs the summon-agent skill" test -f "$INSTALL_HOME/.agents/skills/jamsession-summon-agent/SKILL.md"
check "installer installs the bundled pack" contains "$INSTALL_HOME/.agents/jamsession/packs/jamon.tsv" "# pack: jamon"
check "installer preserves unknown packs" equals "$INSTALL_HOME/.agents/jamsession/packs/mine.tsv" custom-pack

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install jamsession-work-over-ssh
check "optional skill installs on request" test -f "$INSTALL_HOME/.agents/skills/jamsession-work-over-ssh/SKILL.md"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" "$ROOT/jamsession" skills
check "skills lists installed state" contains "$stdout_file" "jamsession-work-over-ssh"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install jamsession-select-agent-model
check "model-selection skill installs on request" test -f "$INSTALL_HOME/.agents/skills/jamsession-select-agent-model/SKILL.md"

# --- Second run: recognized files refresh, everything else survives ---
INSTALLED="$INSTALL_HOME/.agents/jamsession"
INSTALLED_SKILLS="$INSTALL_HOME/.agents/skills"
printf '%s\n' stale >"$INSTALLED/bin/jamsession"
printf '%s\n' stale >"$INSTALLED/adapters/jamsession_codex"
printf '%s\n' stale >"$INSTALLED/adapters/_jamsession_adapter_common"
printf '%s\n' stale >"$INSTALLED/packs/jamon.tsv"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-summon-agent/SKILL.md"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-work-over-ssh/SKILL.md"
printf '%s\n' 'JAMSESSION_CUSTOM_SETTING=kept' >>"$INSTALLED/jamsession.conf"

run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "a second install succeeds" test "$status" -eq 0
check "second install refreshes the command" contains "$INSTALLED/bin/jamsession" JAMSESSION_VERSION
check "second install refreshes a bundled adapter" contains "$INSTALLED/adapters/jamsession_codex" jamsession_validate_run
check "second install refreshes the adapter helper" contains "$INSTALLED/adapters/_jamsession_adapter_common" jamsession_adapter_setup
check "second install refreshes the bundled pack" contains "$INSTALLED/packs/jamon.tsv" "# pack: jamon"
check "second install refreshes the default skill" contains "$INSTALLED_SKILLS/jamsession-summon-agent/SKILL.md" "name: jamsession-summon-agent"
check "second install refreshes an installed optional skill" contains "$INSTALLED_SKILLS/jamsession-work-over-ssh/SKILL.md" "name: jamsession-work-over-ssh"
check "second install preserves configuration" contains "$INSTALLED/jamsession.conf" JAMSESSION_CUSTOM_SETTING=kept
check "second install preserves a custom adapter" equals "$INSTALLED/adapters/jamsession_custom" custom
check "second install preserves a custom pack" equals "$INSTALLED/packs/mine.tsv" custom-pack
check "second install leaves uninstalled optional skills absent" test ! -e "$INSTALLED_SKILLS/jamsession-ask-agent-panel/SKILL.md"
check "second install leaves no staging files behind" sh -c "! ls '$INSTALLED/bin/'*.jamsession-new '$INSTALLED/adapters/'*.jamsession-new >/dev/null 2>&1"
check "installed command stays executable" test -x "$INSTALLED/bin/jamsession"
check "installed adapters stay executable" test -x "$INSTALLED/adapters/jamsession_codex"
check "installed adapter helper stays non-executable" test ! -x "$INSTALLED/adapters/_jamsession_adapter_common"
check "installed pack stays non-executable" test ! -x "$INSTALLED/packs/jamon.tsv"

# --- An incomplete bundle must replace nothing ---
BROKEN_SOURCE="$TEMP_ROOT/broken-source"
mkdir -p "$BROKEN_SOURCE"
cp "$ROOT/jamsession" "$BROKEN_SOURCE/jamsession"
cp -R "$ROOT/adapters" "$ROOT/skills" "$BROKEN_SOURCE/"
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

run_command "$ROOT/jamsession" packs
check "packs lists the bundled pack" equals "$stdout_file" jamon

run_command "$ROOT/jamsession" recommend jamon
check "recommend reads the named pack" test "$status" -eq 0
check "recommend prints the update date" contains "$stdout_file" "# updated:"
check "recommend prints stated limitations" contains "$stdout_file" "# limitations:"
check "recommend prints every role by default" contains "$stdout_file" premium-default
check "recommend writes nothing to stderr on success" test ! -s "$stderr_file"

# A tripwire home: every adapter records that it ran, and a second pack holds a
# token that must never appear when a different pack was named.
TRIPWIRE="$TEMP_ROOT/tripwire"
mkdir -p "$TRIPWIRE/adapters" "$TRIPWIRE/packs"
cat >"$TRIPWIRE/adapters/jamsession_codex" <<'EOF'
#!/bin/sh
printf '%s\n' ADAPTER_EXECUTED >"$FAKE_LOG"
EOF
chmod 755 "$TRIPWIRE/adapters/jamsession_codex"
cp "$ROOT/packs/jamon.tsv" "$TRIPWIRE/packs/jamon.tsv"
printf '# pack: other\nplanning\tcodex\tOTHER_PACK_MODEL\thigh\t1\tnote\n' \
  >"$TRIPWIRE/packs/other.tsv"
rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_HOME="$TRIPWIRE" "$ROOT/jamsession" recommend jamon
check "recommend still prints the named pack from a custom home" contains "$stdout_file" premium-default
check "recommend never executes an adapter" test ! -e "$LOG"
check "recommend reads no other installed pack" sh -c "! grep -Fq OTHER_PACK_MODEL '$stdout_file'"
check "recommend starts no provider session" sh -c "! grep -Fq 'session:' '$stdout_file' '$stderr_file'"
check "recommend writes no configuration" test ! -e "$TRIPWIRE/jamsession.conf"
check "recommend creates no temporary directory in the home" test ! -e "$TRIPWIRE/bin"

run_command "$ROOT/jamsession" recommend jamon discovery grok
check "recommend filters by role and provider" contains "$stdout_file" "grok-4.6"
check "recommend omits non-matching roles" sh -c "! grep -q '^premium-default' '$stdout_file'"
check "recommend omits non-matching providers" sh -c "! grep -q '^discovery.cursor' '$stdout_file'"

run_command "$ROOT/jamsession" recommend
check "recommend requires an explicit pack" test "$status" -eq 2

run_command "$ROOT/jamsession" recommend ../../etc/passwd
check "recommend rejects a path as a pack name" test "$status" -eq 2

run_command "$ROOT/jamsession" recommend nosuchpack
check "recommend fails on a missing pack" test "$status" -ne 0
check "recommend does not substitute another pack" sh -c "! grep -Fq jamon '$stdout_file'"

run_command "$ROOT/jamsession" recommend jamon nosuchrole
check "recommend fails when no row matches" test "$status" -ne 0
check "recommend names the unmatched filters" contains "$stderr_file" "nosuchrole"

check "the site workflow ships the install guide linked from the home page" \
  sh -c "grep -Fq 'install.md' '$ROOT/.github/workflows/pages.yml'"
check "the test workflow runs the current test path" \
  sh -c "grep -Fq 'tests/test_jamsession.sh' '$ROOT/.github/workflows/test.yml'"
check "no workflow still refers to the old name" \
  sh -c "! grep -rqi jamwrap '$ROOT/.github/workflows/'"
check "the documented planning recommendation exists" \
  sh -c "grep -q '^planning' '$ROOT/packs/jamon.tsv'"
check "the remote-agent skill depends on no separately optional skill" \
  sh -c "! grep -Eq 'jamsession-(execute-agent-slice|work-over-ssh|orchestrate-agent-work)' '$ROOT/skills/jamsession-run-remote-agents/SKILL.md'"

run_command "$ROOT/jamsession" help packs
check "help documents the pack schema" contains "$stdout_file" "role,"
check "help states that recommend never runs an agent" contains "$stdout_file" "never runs an agent"

printf '\n%d passed, %d failed\n' "$passed" "$failed"
[ "$failed" -eq 0 ]
