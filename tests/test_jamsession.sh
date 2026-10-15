#!/usr/bin/env bash

set -u

# A developer with Jam Session configured in their own environment must not have
# those values leak into the fixtures. Otherwise the suite writes into the
# checkout instead of its temporary directories.
unset JAMSESSION_HOME JAMSESSION_ADAPTER_DIR JAMSESSION_CONFIG JAMSESSION_SKILL_DIR \
  JAMSESSION_PACK_DIR JAMSESSION_SOURCE_URL JAMSESSION_INSTALL_URL JAMSESSION_CWD \
  JAMSESSION_CODEX_BIN JAMSESSION_CLAUDE_BIN JAMSESSION_CURSOR_BIN \
  JAMSESSION_GROK_BIN JAMSESSION_COPILOT_BIN JAMSESSION_DEVIN_BIN JAMSESSION_MUSE_BIN \
  JAMSESSION_ANTIGRAVITY_BIN \
  JAMSESSION_CODEX_CONTROL_SOCKET JAMSESSION_PYTHON_BIN

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/jamsession-test.XXXXXX")"
control_fixture_pid=""
trap '[ -z "$control_fixture_pid" ] || kill "$control_fixture_pid" 2>/dev/null; rm -rf "$TEMP_ROOT"' EXIT HUP INT TERM
JAMSESSION_CONFIG="$TEMP_ROOT/jamsession.conf"
export JAMSESSION_CONFIG
: >"$JAMSESSION_CONFIG"

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
check "the usage helper ships executable" test -x "$ROOT/usage/jamsession_usage"
non_executable_adapter=""
for adapter in "$ROOT"/adapters/jamsession_*; do
  [ -x "$adapter" ] || non_executable_adapter="$adapter"
done
check "every adapter ships executable" test -z "$non_executable_adapter"
check "the adapter helper ships non-executable" test ! -x "$ROOT/adapters/_jamsession_adapter_common"

INBOX_PROJECT="$TEMP_ROOT/inbox-project"
INBOX_DIR="$INBOX_PROJECT/.agents/jamsession/inbox"
mkdir -p "$INBOX_PROJECT/.agents" "$INBOX_PROJECT/subdir"
run_command env JAMSESSION_CWD="$INBOX_PROJECT/subdir" "$ROOT/jamsession" inbox manager write worker-123 'Implemented slice A; review remains.'
check "inbox writes succeed without a provider" test "$status" -eq 0
first_note="$(cat "$stdout_file")"
check "inbox storage belongs to the project, not the installation" test -f "$first_note"
check "inbox notes identify their sender" contains "$first_note" 'From: worker-123'
check "inbox notes identify their recipient" contains "$first_note" 'To: manager'
check "inbox notes preserve literal content" contains "$first_note" 'Implemented slice A; review remains.'
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox manager-2 write worker-456 'Do not drain me for manager.'
other_note="$(cat "$stdout_file")"
run_command env JAMSESSION_CWD="$INBOX_PROJECT/subdir" "$ROOT/jamsession" inbox manager read
check "inbox read prints the recipient's notes" contains "$stdout_file" 'Implemented slice A; review remains.'
check "inbox read archives only after printing" test -f "$INBOX_DIR/archive/${first_note##*/}"
check "inbox read removes the live copy" test ! -e "$first_note"
check "inbox IDs with a shared prefix remain distinct" test -f "$other_note"
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox manager read
check "a drained inbox does not repeat archived notes" test ! -s "$stdout_file"

for index in 1 2 3 4 5; do
  env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox parallel write "worker-$index" "parallel note $index" >/dev/null &
done
wait
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox parallel read
check "concurrent writers publish unique complete notes" test "$(grep -c '^From: worker-' "$stdout_file")" -eq 5

run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox other write source 'expired unread note'
expired_note="$(cat "$stdout_file")"
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox other write source 'not yet three days old'
recent_note="$(cat "$stdout_file")"
unrelated="$INBOX_DIR/agent-note-personal.txt"
printf '%s\n' 'unrelated file' >"$unrelated"
printf '%s\n' 'nested file' >"$INBOX_DIR/archive/NOTES.md"
ln -s "$unrelated" "$INBOX_DIR/agent-note-symlink-20200101T000000Z-ABCDEFGH.txt"
python3 - "$expired_note" "$recent_note" "$INBOX_DIR/archive/${first_note##*/}" "$unrelated" <<'PY'
import os, sys, time
for path, age in zip(sys.argv[1:], (3*86400+120, 3*86400-120, 3*86400+120, 10*86400)):
    stamp = time.time()-age
    os.utime(path, (stamp, stamp))
PY
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox nobody read
check "read expires unread notes older than three days" test ! -e "$expired_note"
check "read expires old archived notes" test ! -e "$INBOX_DIR/archive/${first_note##*/}"
check "cleanup keeps notes younger than three days" test -f "$recent_note"
check "cleanup keeps files outside its exact filename contract" equals "$unrelated" 'unrelated file'
check "cleanup does not follow note symlinks" test -L "$INBOX_DIR/agent-note-symlink-20200101T000000Z-ABCDEFGH.txt"
check "cleanup keeps unrelated archived files" test -f "$INBOX_DIR/archive/NOTES.md"

INBOX_FAKE_BIN="$TEMP_ROOT/inbox-fake-bin"
mkdir -p "$INBOX_FAKE_BIN"
printf '#!/bin/sh\nexit 7\n' >"$INBOX_FAKE_BIN/cat"
chmod 755 "$INBOX_FAKE_BIN/cat"
run_command env PATH="$INBOX_FAKE_BIN:$PATH" JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox manager-2 read
check "a failed cat is a failed drain" test "$status" -ne 0
check "a failed cat keeps the original note" test -f "$other_note"
check "a failed cat does not archive the note" test ! -e "$INBOX_DIR/archive/${other_note##*/}"
printf '%s\n' collision >"$INBOX_DIR/archive/${other_note##*/}"
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox manager-2 read
check "an archive collision fails safely" test "$status" -ne 0
check "an archive collision never overwrites the saved file" equals "$INBOX_DIR/archive/${other_note##*/}" collision
check "an archive collision leaves the unread note" test -f "$other_note"

run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox arrival write worker 'first arrival'
cat >"$INBOX_FAKE_BIN/cat" <<'EOF'
#!/bin/sh
/bin/cat "$@" || exit $?
"$INBOX_TEST_CLI" inbox arrival write late-worker 'arrived during drain' >/dev/null
EOF
run_command env PATH="$INBOX_FAKE_BIN:$PATH" INBOX_TEST_CLI="$ROOT/jamsession" \
  JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox arrival read
check "read finishes its initial snapshot" test "$status" -eq 0
check "a newly published note is not erased by the drain" test "$(find "$INBOX_DIR" -maxdepth 1 -name 'agent-note-arrival-*.txt' | wc -l | tr -d ' ')" -eq 1
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox arrival read
check "notes arriving during read are available at the next checkpoint" contains "$stdout_file" 'arrived during drain'

INBOX_LINK_PROJECT="$TEMP_ROOT/inbox-link-project"
mkdir -p "$INBOX_LINK_PROJECT/.agents/jamsession" "$TEMP_ROOT/outside-inbox"
ln -s "$TEMP_ROOT/outside-inbox" "$INBOX_LINK_PROJECT/.agents/jamsession/inbox"
run_command env JAMSESSION_CWD="$INBOX_LINK_PROJECT" "$ROOT/jamsession" inbox manager read
check "inbox refuses a symlink root" test "$status" -eq 2
rm "$INBOX_LINK_PROJECT/.agents/jamsession/inbox"
mkdir "$INBOX_LINK_PROJECT/.agents/jamsession/inbox"
ln -s "$TEMP_ROOT/outside-inbox" "$INBOX_LINK_PROJECT/.agents/jamsession/inbox/archive"
run_command env JAMSESSION_CWD="$INBOX_LINK_PROJECT" "$ROOT/jamsession" inbox manager read
check "inbox refuses a symlink archive" test "$status" -eq 2
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox ../escape write source note
check "inbox rejects recipient path traversal" test "$status" -eq 2
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox manager write ../escape note
check "inbox rejects unsafe sender IDs" test "$status" -eq 2
run_command env JAMSESSION_CWD="$INBOX_PROJECT" "$ROOT/jamsession" inbox manager write note
check "inbox requires sender identity" test "$status" -eq 2
INBOX_HOME="$TEMP_ROOT/inbox-global-home"
mkdir -p "$INBOX_HOME/.agents"
run_command env HOME="$INBOX_HOME" JAMSESSION_CWD="$INBOX_HOME" "$ROOT/jamsession" inbox manager read
check "inbox never treats global home .agents as a project" test "$status" -eq 2
check "the global home inbox was not created" test ! -e "$INBOX_HOME/.agents/jamsession/inbox"

run_command "$ROOT/jamsession" adapters
check "bundled providers are discovered" contains "$stdout_file" codex
check "adapter helper is not exposed as a provider" sh -c "! grep -Fq _jamsession '$stdout_file'"

run_command "$ROOT/jamsession" providers
check "providers lists the bundled adapters" contains "$stdout_file" claude
check "providers lists Devin" contains "$stdout_file" devin
check "providers lists Muse" contains "$stdout_file" muse
check "providers lists Antigravity" contains "$stdout_file" antigravity
cp "$stdout_file" "$TEMP_ROOT/providers-output"
run_command "$ROOT/jamsession" adapters
check "adapters is an exact alias for providers" sh -c "diff -q '$TEMP_ROOT/providers-output' '$stdout_file' >/dev/null"
run_command "$ROOT/jamsession" agents
check "agents remains an exact alias" sh -c "diff -q '$TEMP_ROOT/providers-output' '$stdout_file' >/dev/null"
run_command "$ROOT/jamsession" providers extra
check "providers rejects arguments" test "$status" -eq 2

run_command "$ROOT/jamsession" help
check "main help documents providers" contains "$stdout_file" "jamsession providers"
check "main help documents transcript discovery" contains "$stdout_file" "jamsession which <provider> [session]"
check "main help notes the adapters alias" contains "$stdout_file" "\`adapters\` is an exact alias"
check "main help does not present adapters as the primary name" sh -c "! grep -q '^  jamsession adapters\$' '$stdout_file'"
check "main help documents skills uninstall" contains "$stdout_file" "uninstall <name|all>"
check "main help no longer documents recommendation packs" sh -c "! grep -Eq 'jamsession (packs|recommend)' '$stdout_file'"

run_command "$ROOT/jamsession" packs
check "the removed packs command is rejected" test "$status" -eq 2

run_command "$ROOT/jamsession" help providers
check "provider help explains the listing" contains "$stdout_file" "Usage: jamsession providers"
check "provider help names the alias" contains "$stdout_file" "exact alias"

run_command "$ROOT/jamsession" help which
check "which help documents its optional session" contains "$stdout_file" "jamsession which <provider> [session]"
check "which help explains read-only transcript discovery" contains "$stdout_file" "read-only discovery"

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
if [ "${1:-}" = debug ] && [ "${2:-}" = models ]; then
  printf '%s\n' '{"models":[{"slug":"codex-current","display_name":"Codex Current","description":"Workhorse.","default_reasoning_level":"low","supported_reasoning_levels":[{"effort":"low"},{"effort":"high"}],"visibility":"list"},{"slug":"codex-hidden","visibility":"hide","supported_reasoning_levels":[]}]}'
  exit 0
fi
if [ "${1:-}" = queue ]; then
  printf '%s\n' queue >>"$FAKE_LOG.calls"
  printf '%s\n' "$@" >"$FAKE_LOG"
  printf '%s\n' CODEX_QUEUED
  exit "${FAKE_EXIT:-0}"
fi
last=
printf '%s\n' run >>"$FAKE_LOG.calls"
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
if [ "${1:-}" = agents ]; then
  printf '%s\n' "${FAKE_ACTIVE_CLAUDE:-[]}"
  exit "${FAKE_AGENTS_EXIT:-0}"
fi
printf '%s\n' "$*" >"$FAKE_LOG"
for last_argument do :; done
printf '%s' "$last_argument" >"$FAKE_LOG.last"
case " $* " in
  *" --model invalid-model "*)
    printf '%s\n' 'There is an issue with the selected model. It may not exist.'
    printf '%s\n' '[claude-code:unrecognized_model]' >&2
    exit 1
    ;;
  *" --model synthetic-error "*)
    printf '%s\n' "There's an issue with the selected model (synthetic-error). It may not exist."
    exit 0
    ;;
  *" --model logged-out "*)
    printf '%s\n' 'Not logged in · Please run /login'
    exit 0
    ;;
esac
printf '%s\n' CLAUDE_RESULT
exit "${FAKE_EXIT:-0}"
EOF

cat >"$FAKE_BIN/claude-slow-usage" <<'EOF'
#!/usr/bin/env bash
IFS= read -r command || exit 1
[ "$command" = /usage ] || exit 1
for _ in {1..7}; do
  if IFS= read -rsn1 -t 1 key && [ "$key" = $'\033' ]; then exit 0; fi
done
printf '%s\n' \
  'Current session' '6% used' 'Resets 4:30pm' \
  'Current week (all models)' '15% used' 'Resets Sep 7 at 7am' \
  'Current week (Fable)' '24% used' 'Resets Sep 7 at 7am'
EOF

cat >"$FAKE_BIN/claude-model-reader" <<'EOF'
#!/bin/sh
printf '%s\n' 'default - Opus 5' 'opus 5 - Best for everyday tasks' 'fable 5.1 - Fable 5.1 for the hardest tasks' 'haiku 4.5 - Fastest'
EOF

cat >"$FAKE_BIN/cursor-agent" <<'EOF'
#!/bin/sh
if [ "${1:-}" = create-chat ]; then printf '%s\n' cursor-session; exit 0; fi
if [ "${1:-}" = --list-models ]; then
  printf '%s\n' 'Available models' \
    'cursor-model - Cursor Model' \
    'cursor-grok-4.6-low - Cursor Grok 4.6 Low' \
    'cursor-grok-4.6-high - Cursor Grok 4.6' \
    'cursor-grok-4.6-high-fast - Cursor Grok 4.6 Fast' \
    'gpt-5.5-extra-high - GPT-5.5 Extra High'
  exit 0
fi
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

cat >"$FAKE_BIN/devin" <<'EOF'
#!/bin/sh
case "${1:-}" in
  --version) printf '%s\n' DEVIN_VERSION; exit 0 ;;
  auth) printf '%s\n' 'Logged in'; exit 0 ;;
  doctor) printf '%s\n' DEVIN_DOCTOR_OK; exit 0 ;;
  acp)
    [ -z "${FAKE_ACP_FAIL:-}" ] || exit 1
    exec python3 "$FAKE_DEVIN_ACP" ;;
  models)
    printf '%s\n' 'Available models' 'Grok 4.6 (grok-4.6)' \
      '  grok-4-6-medium  Grok Medium' '  grok-4-6-high  Grok High'
    exit 0 ;;
  list)
    printf '%s\n' 'id,short_id,working_directory,last_activity_at,last_activity_ago,title'
    [ -f "$FAKE_DEVIN_STATE" ] && printf '%s\n' 'new-devin-session,new-devin-session,./,1,now,Prompt'
    exit 0 ;;
esac
printf '%s\n' "$*" >"$FAKE_LOG"
case " $* " in
  *' --resume '*) ;;
  *) : >"$FAKE_DEVIN_STATE" ;;
esac
printf '%s\n' DEVIN_RESULT
exit "${FAKE_EXIT:-0}"
EOF

cat >"$FAKE_BIN/muse" <<'EOF'
#!/bin/sh
if [ "${1:-}" = --version ]; then printf '%s\n' MUSE_VERSION; exit 0; fi
if [ "${1:-}" = session-message ]; then
  printf '%s\n' "$@" >"$FAKE_LOG"
  cat >"$FAKE_LOG.body"
  printf '%s\n' MUSE_SENT
  exit "${FAKE_EXIT:-0}"
fi
printf '%s\n' "$*" >"$FAKE_LOG"
printf '%s\n' '{"stream":{"kind":"session","id":"muse-session"},"payload_type":"runtime.command.accepted"}'
printf '%s\n' '{"payload_type":"run.terminal.completed","payload":{"text":"MUSE_RESULT"}}'
exit "${FAKE_EXIT:-0}"
EOF
chmod 755 "$FAKE_BIN"/*

LOG="$TEMP_ROOT/args"

JAMSESSION_CODEX_CONTROL_SOCKET="$TEMP_ROOT/control.sock"
export JAMSESSION_CODEX_CONTROL_SOCKET
python3 "$ROOT/tests/test_codex_control.py" --serve "$JAMSESSION_CODEX_CONTROL_SOCKET" >"$TEMP_ROOT/control-ready" &
control_fixture_pid=$!
for _ in {1..100}; do
  [ ! -S "$JAMSESSION_CODEX_CONTROL_SOCKET" ] || break
  sleep 0.02
done
check "native Codex ownership fixture is ready" test -S "$JAMSESSION_CODEX_CONTROL_SOCKET"
run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" message codex target-session 'Question with "quotes" and $literal'
check "Codex messages use native queue" contains "$LOG" queue
check "Codex messages target the exact session" contains "$LOG" target-session
check "Codex messages preserve literal text" contains "$LOG" 'Question with "quotes" and $literal'
check "Codex message acknowledgement passes through" equals "$stdout_file" CODEX_QUEUED
run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" codex target-session message 'alias question'
check "provider-first messaging alias works" equals "$stdout_file" CODEX_QUEUED
run_command env FAKE_LOG="$LOG" FAKE_EXIT=7 JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" message codex target-session question
check "message preserves provider failure" test "$status" -eq 7
run_command env FAKE_LOG="$LOG" JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" \
  "$ROOT/jamsession" message muse target-session 'Muse question'
check "Muse messages use native send" contains "$LOG" session-message
check "Muse messages target the exact session" contains "$LOG" target-session
check "Muse message text goes through stdin" equals "$LOG.body" 'Muse question'
run_command sh -c 'printf "%s\n%s" "line one" "line two" | env FAKE_LOG="$1" JAMSESSION_MUSE_BIN="$2" "$3" message muse target-session -' \
  sh "$LOG" "$FAKE_BIN/muse" "$ROOT/jamsession"
check "message accepts multiline stdin" contains "$LOG.body" 'line two'
run_command "$ROOT/jamsession" message claude target-session question
check "unsupported messaging reports unavailable" test "$status" -eq 3
run_command "$ROOT/jamsession" message codex target-session ''
check "message rejects empty text" test "$status" -eq 2
run_command "$ROOT/jamsession" message codex -x question
check "message rejects option-like session" test "$status" -eq 2

run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" message codex new question --resume-with default default read
check "messaging cannot create a new session" test "$status" -eq 2
run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" message codex target question --resume-with model high maybe
check "messaging rejects invalid fallback access before sending" test "$status" -eq 2
rm -f "$LOG.calls"
run_command env FAKE_LOG="$LOG" FAKE_EXIT=3 JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" message codex target question --resume-with model high read
check "native exit 3 remains a delivery error" test "$status" -eq 3
check "native failure never launches a resume" equals "$LOG.calls" queue
check "native delivery explains unused fallback settings" contains "$stderr_file" "--resume-with ignored"
check "native queue receives no model override" sh -c "! grep -Fxq -- '-m' '$LOG'"
run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/jamsession" message claude target question --resume-with model high read
check "explicit Claude fallback succeeds" test "$status" -eq 0
check "fallback resumes the exact session" contains "$LOG" "--resume target"
check "fallback enforces the requested read access" contains "$LOG" "--permission-mode plan"
check "fallback passes chosen model" contains "$LOG" "--model model"
check "fallback is visibly synchronous" contains "$stderr_file" "resume (not queued)"
run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/jamsession" claude target message 'alias reply' --resume-with model high read
check "provider-first alias supports explicit fallback" equals "$LOG.last" 'alias reply'
run_command sh -c 'printf "%s\n%s" "line one" "line two" | env FAKE_LOG="$1" JAMSESSION_CLAUDE_BIN="$2" "$3" message claude target - --resume-with default default read' \
  sh "$LOG" "$FAKE_BIN/claude" "$ROOT/jamsession"
check "resume fallback reads caller stdin once" equals "$LOG.last" $'line one\nline two'
run_command sh -c 'printf "%s" "-" | env FAKE_LOG="$1" JAMSESSION_CLAUDE_BIN="$2" "$3" message claude target - --resume-with default default read' \
  sh "$LOG" "$FAKE_BIN/claude" "$ROOT/jamsession"
check "fallback preserves a literal dash reply" equals "$LOG.last" '-'
run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/jamsession" message claude target $'reply\n\n' --resume-with default default read
printf 'reply\n\n' >"$TEMP_ROOT/literal-message"
check "fallback preserves literal trailing newlines" cmp -s "$LOG.last" "$TEMP_ROOT/literal-message"
run_command sh -c 'printf "%s" "stdin body" | env JAMSESSION_PROMPT_LITERAL=1 FAKE_LOG="$1" JAMSESSION_CLAUDE_BIN="$2" "$3" message claude target - --resume-with default default read' \
  sh "$LOG" "$FAKE_BIN/claude" "$ROOT/jamsession"
check "private literal flag cannot disable caller stdin" equals "$LOG.last" 'stdin body'
rm -f "$LOG"
run_command env FAKE_LOG="$LOG" FAKE_ACTIVE_CLAUDE='[{"sessionId":"target","status":"idle"}]' \
  JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" "$ROOT/jamsession" message claude target question --resume-with model high read
check "an idle but open Claude session is refused" test "$status" -eq 2
check "busy Claude fallback launches no provider turn" test ! -e "$LOG"
run_command env FAKE_LOG="$LOG" FAKE_AGENTS_EXIT=1 JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/jamsession" message claude target question --resume-with model high read
check "Claude ownership discovery failure refuses fallback" test "$status" -eq 2
run_command env FAKE_LOG="$LOG" GROK_SESSION_ID=target JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  "$ROOT/jamsession" message grok target question --resume-with default high edit
check "known own Grok session cannot be resumed for messaging" test "$status" -eq 2
run_command env FAKE_LOG="$LOG" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  "$ROOT/jamsession" message grok another-session question --resume-with default high read
check "fallback never weakens Grok read access" test "$status" -eq 2
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/jamsession" message cursor target question --resume-with default default read
check "Cursor fallback retains its existing read adapter" test "$status" -eq 0
check "Cursor fallback targets an existing chat" contains "$LOG" "--resume target"
run_command env FAKE_LOG="$LOG" JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" \
  "$ROOT/jamsession" message copilot target question --resume-with auto default edit
check "Copilot fallback targets the existing session" contains "$LOG" "--session-id target"
run_command env FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$TEMP_ROOT/message-devin-state" \
  JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" "$ROOT/jamsession" message devin target question --resume-with default default edit
check "Devin fallback targets the existing session" contains "$LOG" "--resume target"

SIZE_HOME="$TEMP_ROOT/size-home"
mkdir -p "$SIZE_HOME/.claude/projects/workspace" "$SIZE_HOME/.codex/sessions/2026" \
  "$SIZE_HOME/.copilot/session-state/copilot-size" "$SIZE_HOME/.grok/sessions/workspace/grok-size" \
  "$SIZE_HOME/.local/share/muse/sessions/2026/muse-session"
cat >"$SIZE_HOME/.claude/projects/workspace/claude-size.jsonl" <<'JSONL'
{"type":"assistant","message":{"content":[{"type":"text","text":"\"usage\":{\"input_tokens\":9}"}],"usage":{"input_tokens":2,"cache_creation_input_tokens":20000,"cache_read_input_tokens":240000,"output_tokens":800,"iterations":[{"input_tokens":1}]}}}
{"type":"user","toolUseResult":{"usage":{"input_tokens":5,"output_tokens":5}}}
{"type":"assistant","isSidechain":true,"message":{"usage":{"input_tokens":7,"output_tokens":7}}}
JSONL
cat >"$SIZE_HOME/.codex/sessions/2026/rollout-codex-session.jsonl" <<'JSONL'
{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"total_tokens":999999},"last_token_usage":{"input_tokens":1200,"output_tokens":34,"total_tokens":1234}}}}
JSONL
printf '%s\n' '{"data":{"currentTokens":100}}' '{"data":{"currentTokens":200}}' \
  >"$SIZE_HOME/.copilot/session-state/copilot-size/events.jsonl"
printf '%s\n' '{"turnCount":1,"contextTokensUsed":300,"contextWindowTokens":256000}' \
  >"$SIZE_HOME/.grok/sessions/workspace/grok-size/signals.json"
printf '%s\n' '{"payload":{"event":{"kind":"model_completed","usage":{"input_tokens":400,"output_tokens":5,"cached_tokens":390}}}}' \
  >"$SIZE_HOME/.local/share/muse/sessions/2026/muse-session/session.jsonl"

run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/jamsession" run claude claude-size default default read prompt
check "Claude resume reports the latest main-thread context size" contains "$stderr_file" "session-size: 260802 tokens"
check "a session past 250K tokens suggests a worksheet hand-off" contains "$stderr_file" "consider a fresh session"
check "the size report stays off stdout" equals "$stdout_file" CLAUDE_RESULT
run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/jamsession" run claude new default default read prompt
check "a session without token data says so plainly" contains "$stderr_file" "session-size: unavailable"
run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" run codex new default default read prompt
check "Codex reports the latest call, not cumulative usage" contains "$stderr_file" "session-size: 1234 tokens"
check "a small session gets no hand-off advice" sh -c "! grep -Fq 'fresh session' '$stderr_file'"
run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" \
  "$ROOT/jamsession" run copilot copilot-size default default edit prompt
check "Copilot reports its latest context count" contains "$stderr_file" "session-size: 200 tokens"
run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  "$ROOT/jamsession" run grok grok-size default default edit prompt
check "Grok reports its context count" contains "$stderr_file" "session-size: 300 tokens"
run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" \
  "$ROOT/jamsession" run muse new default default read prompt
check "Muse reports its latest model call" contains "$stderr_file" "session-size: 405 tokens"
run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/jamsession" run cursor new default default read prompt
check "Cursor explains why its size is unavailable" contains "$stderr_file" "session-size: unavailable (Cursor"
if command -v sqlite3 >/dev/null 2>&1; then
  mkdir -p "$SIZE_HOME/.local/share/devin/cli"
  sqlite3 "$SIZE_HOME/.local/share/devin/cli/sessions.db" \
    "CREATE TABLE message_nodes (session_id TEXT, node_id INTEGER, metadata TEXT);
     INSERT INTO message_nodes VALUES ('devin-size', 1, '{\"num_tokens_preceding\":100}'),
       ('devin-size', 2, NULL), ('devin-size', 3, '{\"num_tokens_preceding\":600}');"
  run_command env HOME="$SIZE_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$TEMP_ROOT/size-devin-state" \
    JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" "$ROOT/jamsession" run devin devin-size default default edit prompt
  check "Devin resume reports its latest recorded context" contains "$stderr_file" "session-size: 600 tokens"
fi

WATCH_REPLY="$TEMP_ROOT/watch reply.txt"
printf 'literal [ready].\n\n' >"$WATCH_REPLY"
run_command "$ROOT/jamsession" watch "$WATCH_REPLY" '[ready].' --timeout 0
check "watch accepts a reply that arrived before it started" test "$status" -eq 0
check "watch returns the exact matched snapshot including trailing newlines" cmp -s "$WATCH_REPLY" "$stdout_file"
run_command "$ROOT/jamsession" watch "$WATCH_REPLY" '[missing].' --timeout 0
check "watch matches literal text rather than regex syntax" test "$status" -eq 124
check "timeout never prints unmatched file contents" test ! -s "$stdout_file"
check "watch timeout explains the watched file" contains "$stderr_file" 'Timeout after 0 seconds'
for bad_timeout in -1 NaN 86401 999999999999999999999; do
  run_command "$ROOT/jamsession" watch "$WATCH_REPLY" ready --timeout "$bad_timeout"
  check "watch rejects timeout $bad_timeout" test "$status" -eq 2
done
run_command "$ROOT/jamsession" watch "$WATCH_REPLY" $'line one\nline two' --timeout 0
check "watch rejects multiline grep patterns" test "$status" -eq 2
run_command "$ROOT/jamsession" watch "$TEMP_ROOT" ready --timeout 0
check "watch refuses a directory" test "$status" -eq 2
mkfifo "$TEMP_ROOT/watch-fifo"
run_command "$ROOT/jamsession" watch "$TEMP_ROOT/watch-fifo" ready --timeout 0
check "watch refuses streams without blocking" test "$status" -eq 2
run_command "$ROOT/jamsession" watch "$WATCH_REPLY" ready --resume-with default default read
check "watch requires a target for fallback settings" test "$status" -eq 2
run_command "$ROOT/jamsession" watch "$WATCH_REPLY" ready codex
check "watch rejects a partial target" test "$status" -eq 2
run_command "$ROOT/jamsession" watch "$WATCH_REPLY" ready --timeout 0 --timeout 0
check "watch rejects duplicate timeout decisions" test "$status" -eq 2
rm -f "$WATCH_REPLY"
(sleep 0.2; printf 'request-42-DONE\nfull reply\n' >"$WATCH_REPLY.new"; mv "$WATCH_REPLY.new" "$WATCH_REPLY") &
writer_pid=$!
run_command "$ROOT/jamsession" watch "$WATCH_REPLY" request-42-DONE --timeout 3
wait "$writer_pid"
check "watch sees a file published later by another process" test "$status" -eq 0
check "delayed reply is printed whole" cmp -s "$WATCH_REPLY" "$stdout_file"
FAULT_BIN="$TEMP_ROOT/watch-fault-tools"
mkdir -p "$FAULT_BIN"
cat >"$FAULT_BIN/cp" <<'EOF'
#!/bin/sh
if [ "${WATCH_COPY_ERROR:-0}" = 1 ]; then
  printf 'cp: snapshot: No space left on device\n' >&2
  exit 1
fi
if [ -n "${WATCH_COPY_ONCE:-}" ] && [ ! -f "$WATCH_COPY_ONCE" ]; then
  : >"$WATCH_COPY_ONCE"
  printf 'cp: reply: No such file or directory\n' >&2
  exit 1
fi
exec "$REAL_CP" "$@"
EOF
cat >"$FAULT_BIN/grep" <<'EOF'
#!/bin/sh
if [ "${WATCH_SEARCH_ERROR:-0}" = 1 ]; then exit 2; fi
exec "$REAL_GREP" "$@"
EOF
chmod 755 "$FAULT_BIN/cp" "$FAULT_BIN/grep"
REAL_CP="$(command -v cp)"; REAL_GREP="$(command -v grep)"
rm -f "$LOG.calls"
run_command env PATH="$FAULT_BIN:$PATH" REAL_CP="$REAL_CP" REAL_GREP="$REAL_GREP" WATCH_COPY_ERROR=1 \
  FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" watch "$WATCH_REPLY" request-42-DONE codex target --timeout 0
check "snapshot I/O failure is not a timeout" test "$status" -eq 2
check "snapshot failure sends no misleading timeout notification" test ! -e "$LOG.calls"
run_command env PATH="$FAULT_BIN:$PATH" REAL_CP="$REAL_CP" REAL_GREP="$REAL_GREP" WATCH_SEARCH_ERROR=1 \
  "$ROOT/jamsession" watch "$WATCH_REPLY" request-42-DONE --timeout 0
check "search I/O failure is not a timeout" test "$status" -eq 2
run_command env PATH="$FAULT_BIN:$PATH" REAL_CP="$REAL_CP" REAL_GREP="$REAL_GREP" WATCH_COPY_ONCE="$TEMP_ROOT/disappeared-once" \
  "$ROOT/jamsession" watch "$WATCH_REPLY" request-42-DONE --timeout 2
check "disappearance during snapshot retries a recreated readable file" test "$status" -eq 0
run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" watch "$WATCH_REPLY" request-42-DONE codex target --timeout 0
check "notifying watch keeps stdout as the reply" cmp -s "$WATCH_REPLY" "$stdout_file"
check "watch routes acknowledgement separately" contains "$stderr_file" CODEX_QUEUED
check "watch notifies the exact target" contains "$LOG" target
check "watch notification does not copy the reply body" sh -c "! grep -Fq 'full reply' '$LOG'"
rm -f "$LOG.calls"
run_command env FAKE_LOG="$LOG" FAKE_EXIT=7 JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" watch "$WATCH_REPLY" request-42-DONE codex target --timeout 0 --resume-with model high read
check "watch propagates notification failure" test "$status" -eq 7
check "watch does not retry failed notification" equals "$LOG.calls" queue
check "delivery outcome is reported separately" contains "$stderr_file" 'delivery-result: 7'
run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/jamsession" watch "$WATCH_REPLY" missing codex target --timeout 0
check "delivered timeout retains watch timeout status" test "$status" -eq 124
check "timeout sends an explicit notification" contains "$LOG" 'Timeout after 0 seconds'
run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/jamsession" watch "$WATCH_REPLY" request-42-DONE claude target --timeout 0 --resume-with model high read
check "watch uses explicit resume fallback" test "$status" -eq 0
check "watch fallback message locates the reply" contains "$LOG.last" 'has contents containing'
run_command "$ROOT/jamsession" watch "$TEMP_ROOT/never-created" missing --timeout 1
check "watch deadline expires when a file never arrives" test "$status" -eq 124
"$ROOT/jamsession" watch "$TEMP_ROOT/never-created" missing --timeout 30 >"$TEMP_ROOT/cancel.out" 2>"$TEMP_ROOT/cancel.err" &
watch_pid=$!
cancel_started=$SECONDS
while ! grep -Fq 'watching:' "$TEMP_ROOT/cancel.err" && [ $((SECONDS - cancel_started)) -lt 10 ]; do
  kill -0 "$watch_pid" 2>/dev/null || break
  sleep 0.05
done
kill -TERM "$watch_pid"
cancel_status=0; wait "$watch_pid" || cancel_status=$?
check "polling watch is cancellable" test "$cancel_status" -eq 130
check "cancelling is not reported as a timeout" sh -c "! grep -Fq 'watch-result: timeout' '$TEMP_ROOT/cancel.err'"

USAGE_FIXTURES="$TEMP_ROOT/usage-fixtures"
mkdir -p "$USAGE_FIXTURES"
cat >"$USAGE_FIXTURES/codex.json" <<'EOF'
{"id":2,"result":{"rateLimitsByLimitId":{"codex":{"limitId":"codex","limitName":"Codex","primary":{"usedPercent":25,"windowDurationMins":10080,"resetsAt":1788973081},"secondary":null},"spark":{"limitId":"spark","limitName":"Spark","primary":{"usedPercent":10,"windowDurationMins":300,"resetsAt":1788654830},"secondary":{"usedPercent":20,"windowDurationMins":10080,"resetsAt":1788919635}}}}}
EOF
cat >"$USAGE_FIXTURES/claude.txt" <<'EOF'
Current session
6% used
Resets 4:30pm
Current week (all models)
15% used
Resets Sep 7 at 7am
Current week (Fable)
24% used
Resets Sep 7 at 7am
EOF
printf '%s\n' 'plan 68% left' >"$USAGE_FIXTURES/cursor.txt"
printf '%s\n' 'Weekly limit (Pro) 35% used Resets: Sep 8, 09:00' >"$USAGE_FIXTURES/grok.txt"
printf '%s\n' 'Monthly AI credits 40% used' >"$USAGE_FIXTURES/copilot.txt"
printf '%s\n' 'Subscription (Max)' '4% used' 'Resets: in 5d 8h' >"$USAGE_FIXTURES/devin.txt"
printf '%s\n' 'Observed at: 2026-10-05T12:00:00+00:00' 'Subscription window' '12% used' 'Resets: 2100-01-01T00:00:00+00:00' \
  'Subscription weekly' '25% used' 'Resets: 2100-01-02T00:00:00+00:00' >"$USAGE_FIXTURES/muse.txt"
printf '%s\n' 'Model quota: Gemini Models' '12% used' 'Resets: 2026-10-20T06:59:20Z' \
  'Model quota: Claude and GPT models' '0% used' 'Resets: 2026-10-20T07:24:31Z' >"$USAGE_FIXTURES/antigravity.txt"

run_command env JAMSESSION_USAGE_FIXTURE_DIR="$USAGE_FIXTURES" "$ROOT/jamsession" usage --json
check "aggregate usage stays complete for providers with readable quota" contains "$stdout_file" '"status":"complete"'
check "Codex usage includes multiple rate-limit buckets" contains "$stdout_file" '"bucket_id":"spark:secondary"'
check "Cursor usage reports remaining plan percentage" contains "$stdout_file" '"remaining_percent":68'
check "aggregate usage succeeds when every fixture parses" test "$status" -eq 0
check "aggregate usage includes Muse subscription windows" contains "$stdout_file" '"bucket_id":"subscription_weekly"'
check "aggregate usage includes Antigravity" contains "$stdout_file" '"agent":"antigravity","status":"ok"'
run_command env JAMSESSION_USAGE_FIXTURE_DIR="$USAGE_FIXTURES" "$ROOT/jamsession" usage gemini --json
check "Gemini usage alias resolves to Antigravity" contains "$stdout_file" '"agent":"antigravity","status":"ok"'
check "Antigravity reports separate model group quota" contains "$stdout_file" '"label":"Claude and GPT models","used_percent":0,"remaining_percent":100'

cat >"$FAKE_BIN/agy" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  --version) printf '1.3.4\n'; exit 0 ;;
  models)
    [ "${FAKE_AGY_AUTH_ERROR:-0}" -eq 0 ] || { printf 'authentication failed\n'; exit 1; }
    printf '%s\n' 'gemini-3.8-flash-high Gemini 3.8 Flash (High)' 'gemini-3.8-flash-medium Gemini 3.8 Flash (Medium)' 'gemini-3.8-flash-low Gemini 3.8 Flash (Low)' 'claude-opus-4-6-thinking Claude Opus 4.6'; exit 0 ;;
esac
printf '%s\n' "$@" >"$FAKE_LOG"
if [ "$2" = /usage ]; then
  printf 'Gemini Models\tWeekly Limit Remaining\t88%%\t2026-10-20T06:59:20Z\nClaude and GPT models\tWeekly Limit Remaining\t100%%\t2026-10-20T07:24:31Z\n'
  exit 0
fi
if [ "${FAKE_AGY_NO_SESSION:-0}" -eq 1 ]; then
  printf '%s\n' '{"status":"SUCCESS","response":"must fail"}'; exit 0
fi
printf '{"conversation_id":"agy-session","status":"%s","response":"AGY_RESULT","usage":{"total_tokens":12345}}\n' "${FAKE_AGY_STATUS:-SUCCESS}"
exit "${FAKE_EXIT:-0}"
EOF
chmod 755 "$FAKE_BIN/agy"
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" usage agy --json
check "Antigravity reads native print-mode quota without a model turn" contains "$stdout_file" '"remaining_percent":88'
check "Antigravity usage sends only native /usage" sh -c "grep -Fxq '/usage' '$LOG' && ! grep -Eq -- 'conversation|skip-permissions' '$LOG'"
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" status agy
check "Antigravity status combines readiness and quota" contains "$stdout_file" 'Gemini Models'
check "Antigravity status succeeds" test "$status" -eq 0

run_command env JAMSESSION_USAGE_FIXTURE_DIR="$TEMP_ROOT/no-usage-fixtures" "$ROOT/jamsession" usage devin --json
check "Devin usage reports unavailable instead of an invented quota" contains "$stdout_file" '"agent":"devin","status":"unavailable"'
run_command env JAMSESSION_USAGE_FIXTURE_DIR="$TEMP_ROOT/no-usage-fixtures" "$ROOT/jamsession" usage muse --json
check "Muse usage reports unavailable instead of an invented quota" contains "$stdout_file" '"agent":"muse","status":"unavailable"'
run_command env JAMSESSION_USAGE_FIXTURE_DIR="$USAGE_FIXTURES" "$ROOT/adapters/jamsession_devin" usage --json
check "Devin adapter usage reaches the shared collector" contains "$stdout_file" '"remaining_percent":96'
run_command env JAMSESSION_USAGE_FIXTURE_DIR="$USAGE_FIXTURES" "$ROOT/adapters/jamsession_muse" usage --json
check "Muse adapter usage reaches the shared collector" contains "$stdout_file" '"remaining_percent":88'
check "Muse observations retain their as-of stamp" contains "$stdout_file" '"observed_at":"2026-10-05T12:00:00+00:00"'
run_command env FAKE_LOG="$LOG" JAMSESSION_USAGE_FIXTURE_DIR="$USAGE_FIXTURES" \
  JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" status
check "aggregate status includes readable Muse quota" contains "$stdout_file" 'Subscription weekly'
check "aggregate status collects all eight fixture providers" contains "$stdout_file" 'Jam Session usage (complete)'

DEVIN_USAGE_TUI="$TEMP_ROOT/devin-usage-tui"
cat >"$DEVIN_USAGE_TUI" <<'EOF'
#!/usr/bin/env python3
import select, sys, time
sys.stdout.write('\033[2J\033[8;3HMax · 84.5% remaining (resets in 4d 2h)\n')
sys.stdout.flush()
# Startup reading must not submit even a slash command or model prompt.
if select.select([sys.stdin], [], [], 3)[0]:
    sys.stdout.write('UNEXPECTED_INPUT\n')
    sys.stdout.flush()
time.sleep(30)
EOF
chmod 755 "$DEVIN_USAGE_TUI"
run_command env JAMSESSION_DEVIN_BIN="$DEVIN_USAGE_TUI" "$ROOT/jamsession" usage devin --json
check "Devin startup quota is read without a prompt" contains "$stdout_file" '"agent":"devin","status":"ok"'
check "Devin remaining quota is not mistaken for used quota" contains "$stdout_file" '"remaining_percent":84.5'
check "Devin reset countdown stays provider-reported" contains "$stdout_file" '"reset_display":"in 4d 2h"'

MUSE_USAGE_HOST="$TEMP_ROOT/muse-usage-host"
cat >"$MUSE_USAGE_HOST" <<'EOF'
#!/usr/bin/env python3
import json, os, sys, time
for line in sys.stdin:
    request = json.loads(line)
    method = request['method']
    with open(os.environ['FAKE_MUSE_REQUESTS'], 'a') as log:
        log.write(method + '\n')
    if method == 'initialize':
        result = {'schema': {'version': 1}}
    elif method == 'initialized':
        initialized = True
        continue
    elif method == 'usage/read':
        assert initialized
        mode = os.environ.get('FAKE_MUSE_USAGE', 'quota')
        if mode == 'stall': time.sleep(30)
        if mode == 'empty': result = {}
        else:
            used = 'bad' if mode == 'malformed' else (0.000001 if mode == 'tiny' else 18.5)
            reset = 1 if mode == 'expired' else 4102444800000
            result = {'usage': {'observedAtMs': 1791201600000, 'tier': 'power',
                'window': {'usedPercent': used, 'resetsAtMs': reset, 'windowDurationMins': 300},
                'weekly': {'usedPercent': 32, 'resetsAtMs': reset}}}
    else:
        raise AssertionError('Quota reader must never start a session or model turn')
    print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}), flush=True)
EOF
chmod 755 "$MUSE_USAGE_HOST"
MUSE_REQUESTS="$TEMP_ROOT/muse-usage-requests"
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_HOST" FAKE_MUSE_REQUESTS="$MUSE_REQUESTS" "$ROOT/jamsession" usage muse --json
check "Muse usage is read through its native protocol" contains "$stdout_file" '"agent":"muse","status":"ok"'
check "Muse window quota is normalized" contains "$stdout_file" '"remaining_percent":81.5'
check "Muse weekly quota is normalized" contains "$stdout_file" '"remaining_percent":68'
check "Muse handshake precedes quota reading" equals "$MUSE_REQUESTS" $'initialize\ninitialized\nusage/read'
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_HOST" FAKE_MUSE_REQUESTS="$MUSE_REQUESTS" FAKE_MUSE_USAGE=empty "$ROOT/jamsession" usage muse --json
check "Muse empty observations are not fabricated as unused quota" contains "$stdout_file" '"code":"usage_not_observed"'
check "Muse missing observations preserve unavailable status" test "$status" -eq 1
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_HOST" FAKE_MUSE_REQUESTS="$MUSE_REQUESTS" FAKE_MUSE_USAGE=malformed "$ROOT/jamsession" usage muse --json
check "Muse malformed quota is rejected" contains "$stdout_file" '"status":"unavailable"'
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_HOST" FAKE_MUSE_REQUESTS="$MUSE_REQUESTS" FAKE_MUSE_USAGE=expired "$ROOT/jamsession" usage muse --json
check "Muse expired observations are not reported as current quota" contains "$stdout_file" '"code":"usage_not_observed"'
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_HOST" FAKE_MUSE_REQUESTS="$MUSE_REQUESTS" FAKE_MUSE_USAGE=tiny "$ROOT/jamsession" usage muse --json
check "Muse small percentages are not misparsed from exponent notation" contains "$stdout_file" '"used_percent":0.000001'
run_command env JAMSESSION_USAGE_TIMEOUT=1 JAMSESSION_MUSE_BIN="$MUSE_USAGE_HOST" FAKE_MUSE_REQUESTS="$MUSE_REQUESTS" FAKE_MUSE_USAGE=stall "$ROOT/jamsession" usage muse --json
check "Muse quota read is bounded by its timeout" test "$status" -eq 1

MUSE_USAGE_TUI="$TEMP_ROOT/muse-usage-tui"
cat >"$MUSE_USAGE_TUI" <<'EOF'
#!/usr/bin/env python3
import json, os, sys, time, tty
if sys.argv[1] == '--version':
    print('Muse Code fixture')
elif sys.argv[1] == 'serve':
    for line in sys.stdin:
        request = json.loads(line)
        if request['method'] == 'initialized': continue
        result = {'schema': {'version': 1}} if request['method'] == 'initialize' else {}
        print(json.dumps({'id': request['id'], 'result': result}), flush=True)
else:
    assert {'--no-session-log', '--disable-write', '--disable-shell', '--trust-workspace'} <= set(sys.argv)
    assert os.getcwd().split('/')[-1].startswith('jamsession-usage-')
    # Like native Muse, read the controlling terminal, not the stdin pipe.
    with open('/dev/tty', 'rb', buffering=0) as terminal:
        tty.setraw(terminal.fileno())
        if os.environ.get('FAKE_MUSE_QUERIES') == 'split':
            for fragment in ('\033[?', 'u\033[', 'c'):
                sys.stdout.write(fragment); sys.stdout.flush(); time.sleep(0.1)
        else:
            sys.stdout.write('\033[?u\033[c'); sys.stdout.flush()
        reply = b'\033[?0u\033[?1;2c'
        received = b''
        while len(received) < len(reply): received += terminal.read(1)
        assert received == reply, received
        message = b''
        while not message.endswith(b'\r'): message += terminal.read(1)
    assert message == b'/usage\r', message
    print('Session usage\r\n  Input 999\r\n  Output 777\r\n  Turns 0\r', flush=True)
    if os.environ.get('FAKE_MUSE_PANEL') != 'missing':
        print('Subscription · Muse Code High Usage\r\n'
              'Current 0% used · Resets at 10:00 PM\r\n'
              'Weekly 1% used · Resets Oct 11 at 5:00 PM\r\n'
              'as of 6:09 PM\r', flush=True)
    time.sleep(30)
EOF
chmod 755 "$MUSE_USAGE_TUI"
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_TUI" "$ROOT/jamsession" usage muse --json
check "Muse missing MSP quota falls back to local usage command" contains "$stdout_file" '"status":"ok"'
check "Muse subscription screen preserves current quota" contains "$stdout_file" '"remaining_percent":100'
check "Muse subscription screen preserves weekly quota" contains "$stdout_file" '"remaining_percent":99'
check "Muse screen preserves provider as-of text" contains "$stdout_file" '"observed_at":"6:09 PM"'
check "Muse screen preserves provider reset text" contains "$stdout_file" '"reset_display":"Oct 11 at 5:00 PM"'
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_TUI" FAKE_MUSE_QUERIES=split "$ROOT/jamsession" usage muse --json
check "Muse terminal queries survive split PTY reads" contains "$stdout_file" '"status":"ok"'
run_command env JAMSESSION_MUSE_BIN="$MUSE_USAGE_TUI" "$ROOT/jamsession" status muse
check "Muse status combines readiness and real reader quota" contains "$stdout_file" 'Muse Code fixture'
check "Muse status includes the current subscription window" contains "$stdout_file" 'Subscription window'
check "Muse status includes the weekly subscription window" contains "$stdout_file" 'Subscription weekly'
check "Muse status preserves the provider observation time" contains "$stdout_file" 'usage as of 6:09 PM'
check "Muse status succeeds when quota is readable" test "$status" -eq 0
run_command env JAMSESSION_USAGE_TIMEOUT=6 JAMSESSION_MUSE_BIN="$MUSE_USAGE_TUI" FAKE_MUSE_PANEL=missing "$ROOT/jamsession" usage muse --json
check "Muse session tokens alone never become subscription quota" contains "$stdout_file" '"code":"usage_not_observed"'
run_command env JAMSESSION_USAGE_TIMEOUT=6 JAMSESSION_MUSE_BIN="$MUSE_USAGE_TUI" FAKE_MUSE_PANEL=missing "$ROOT/jamsession" status muse
check "Muse status keeps readiness when quota is missing" test "$status" -eq 0
check "Muse status explains missing quota without inventing a balance" contains "$stdout_file" 'session tokens are not quota'

GROK_USAGE_TUI="$TEMP_ROOT/grok-usage-tui"
cat >"$GROK_USAGE_TUI" <<'EOF'
#!/usr/bin/env python3
import sys
import time
sys.stdin.read(7)
sys.stdout.write('\033[2J\033[9;24HWeekly \033[9;33Himit (SuperGrok Heavy)\033[11;24H████░░░░░░ 14%\033[12;24HResets: September 13, 22:12')
sys.stdout.flush()
time.sleep(30)
EOF
chmod 755 "$GROK_USAGE_TUI"
run_command env JAMSESSION_GROK_BIN="$GROK_USAGE_TUI" "$ROOT/jamsession" usage grok --json
check "Grok usage renders its cursor-addressed modal" contains "$stdout_file" '"agent":"grok","status":"ok"'
check "Grok usage reads the modal percentage" contains "$stdout_file" '"remaining_percent":86'
check "Grok usage reads the modal reset" contains "$stdout_file" '"reset_display":"September 13, 22:12"'

COPILOT_USAGE_TUI="$TEMP_ROOT/copilot-usage-tui"
cat >"$COPILOT_USAGE_TUI" <<'EOF'
#!/usr/bin/env python3
import sys
import time
sys.stdout.write('\033[2J\033[12;3HPlan       1% used\033[13;15H15 / 1,500 AIC')
sys.stdout.flush()
time.sleep(30)
EOF
chmod 755 "$COPILOT_USAGE_TUI"
run_command env JAMSESSION_COPILOT_BIN="$COPILOT_USAGE_TUI" "$ROOT/jamsession" usage copilot --json
check "Copilot usage renders its cursor-addressed screen" contains "$stdout_file" '"agent":"copilot","status":"ok"'
check "Copilot usage reads the plan percentage" contains "$stdout_file" '"remaining_percent":99'

chmod 755 "$FAKE_BIN/claude-slow-usage"
run_command env JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude-slow-usage" JAMSESSION_USAGE_TIMEOUT=12 \
  "$ROOT/jamsession" usage claude --json
check "Claude usage waits for the delayed Fable window" contains "$stdout_file" '"bucket_id":"weekly_fable"'

ANSI_FIXTURES="$TEMP_ROOT/ansi-usage-fixtures"
cp -R "$USAGE_FIXTURES" "$ANSI_FIXTURES"
printf '\033[1mCurrent session\033[0m\n\033[1m6%%\033[0m used\nResets \033[1m4:30pm \\ local\033[0m\n' >"$ANSI_FIXTURES/claude.txt"
run_command env JAMSESSION_USAGE_FIXTURE_DIR="$ANSI_FIXTURES" "$ROOT/jamsession" usage claude --json
check "usage strips terminal escapes" sh -c "! grep -q $'\033' '$stdout_file'"
check "usage JSON escapes provider backslashes" contains "$stdout_file" '4:30pm \\ local'
check "usage parses percentages wrapped in terminal styling" contains "$stdout_file" '"bucket_id":"current_session"'

CONFIG_CODEX="$TEMP_ROOT/configured-codex"
cat >"$CONFIG_CODEX" <<EOF
#!/bin/sh
printf '%s\n' '$(cat "$USAGE_FIXTURES/codex.json")'
EOF
chmod 755 "$CONFIG_CODEX"
CONFIG_ONLY="$TEMP_ROOT/usage-path.conf"
printf 'JAMSESSION_CODEX_BIN=%q\n' "$CONFIG_CODEX" >"$CONFIG_ONLY"
run_command env PATH="/usr/bin:/bin" JAMSESSION_CONFIG="$CONFIG_ONLY" "$ROOT/jamsession" usage codex --json
check "usage honors the provider path recorded by init" contains "$stdout_file" '"agent":"codex","status":"ok"'

run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  JAMSESSION_USAGE_FIXTURE_DIR="$USAGE_FIXTURES" "$ROOT/jamsession" status codex
check "status combines readiness and usage" contains "$stdout_file" "Jam Session usage (complete)"
check "status keeps the provider diagnostic" contains "$stdout_file" CODEX_AUTH_OK
check "status renders the provider's usage windows" contains "$stdout_file" "Spark secondary"
check "status does not mislabel available usage" sh -c "! grep -Fq unavailable '$stdout_file'"

mkdir -p "$TEMP_ROOT/partial-usage"
run_command env FAKE_LOG="$LOG" JAMSESSION_GROK_BIN="$FAKE_BIN/grok" \
  JAMSESSION_USAGE_FIXTURE_DIR="$TEMP_ROOT/partial-usage" "$ROOT/jamsession" status grok
check "status succeeds when readiness passes but usage is unavailable" test "$status" -eq 0
check "status reports unavailable usage without hiding readiness" contains "$stdout_file" unavailable

run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" \
  "$ROOT/adapters/jamsession_codex" run new default high read prompt
check "Codex final response is normalized" equals "$stdout_file" CODEX_RESULT
check "Codex new session ID is reported" contains "$stderr_file" "session: codex-session"
check "Codex read mode uses native read-only sandbox" contains "$LOG" "-s read-only"

run_command env FAKE_LOG="$LOG" JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" JAMSESSION_CODEX_SANDBOX=off \
  "$ROOT/adapters/jamsession_codex" run new default high read prompt
check "Codex read wins over legacy sandbox-off" contains "$LOG" "-s read-only"
check "Codex read selects the named read-only profile too" contains "$LOG" 'default_permissions=":read-only"'
check "Codex read never passes the bypass flag" sh -c "! grep -Fq -- '--dangerously-bypass-approvals-and-sandbox' '$LOG'"

run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/adapters/jamsession_claude" run new default high read prompt
check "Claude response passes through" contains "$stdout_file" CLAUDE_RESULT
check "Claude read mode uses plan permissions" contains "$LOG" "--permission-mode plan"
check "Claude session ID is a UUID" grep -Eq 'session: [0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}' "$stderr_file"

run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  JAMSESSION_PYTHON_BIN="$FAKE_BIN/claude-model-reader" \
  "$ROOT/adapters/jamsession_claude" models
check "Claude models reads the interactive picker" contains "$stdout_file" "Fable 5.1"
check "Claude models prefixes picker names with CLI IDs" contains "$stdout_file" "claude-fable-5-1 - fable 5.1 - "

run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  JAMSESSION_PYTHON_BIN="$FAKE_BIN/claude-model-reader" \
  "$ROOT/adapters/jamsession_claude" run new invalid-model medium read prompt
check "Claude preserves an invalid-model failure" test "$status" -eq 1
check "Claude invalid-model failures print picker choices" contains "$stderr_file" "Fable 5.1"

run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
  "$ROOT/adapters/jamsession_claude" run new "Opus 5.5" high read prompt
check "Claude maps a picker name to its CLI model ID" contains "$LOG" "--model claude-opus-5-5 "

for synthetic_model in synthetic-error logged-out; do
  run_command env FAKE_LOG="$LOG" JAMSESSION_CLAUDE_BIN="$FAKE_BIN/claude" \
    JAMSESSION_PYTHON_BIN="$FAKE_BIN/claude-model-reader" \
    "$ROOT/adapters/jamsession_claude" run new "$synthetic_model" high read prompt
  check "Claude $synthetic_model reply exits nonzero" test "$status" -eq 1
  check "Claude $synthetic_model reply names provider unavailable" contains "$stderr_file" "provider unavailable"
done

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

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new cursor-grok-4.6-high high read prompt
check "Cursor accepts a matching effort-qualified model" contains "$LOG" "--model cursor-grok-4.6-high"
check "Cursor does not append a duplicate effort override" sh -c "! grep -Fq -- '[effort=' '$LOG'"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new grok-4.6 high read prompt
check "Cursor resolves a shorthand model from its live catalog" contains "$LOG" "--model cursor-grok-4.6-high"
check "Cursor shorthand resolution does not append an override" sh -c "! grep -Fq -- '[effort=' '$LOG'"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new gpt-5.5 xhigh read prompt
check "Cursor maps xhigh to Cursor's extra-high model suffix" contains "$LOG" "--model gpt-5.5-extra-high"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new grok-4.6 medium read prompt
check "Cursor rejects a shorthand effort absent from the catalog" test "$status" -eq 2
check "Cursor shows available exact variants after a shorthand mismatch" contains "$stderr_file" "cursor-grok-4.6-high"
check "an unavailable shorthand variant creates no chat" sh -c "! grep -Fq 'session:' '$stderr_file'"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_CURSOR_BIN="$FAKE_BIN/cursor-agent" \
  "$ROOT/adapters/jamsession_cursor" run new cursor-grok-4.6-high medium read prompt
check "Cursor rejects a mismatched effort-qualified model" test "$status" -eq 2
check "Cursor names the encoded effort mismatch" contains "$stderr_file" "already encodes effort 'high'"
check "a mismatched effort-qualified model creates no chat" sh -c "! grep -Fq 'session:' '$stderr_file'"

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
check "Copilot auto model sends no effort flag" sh -c "! grep -Fq -- '-effort' '$LOG'"

run_command env FAKE_LOG="$LOG" JAMSESSION_COPILOT_BIN="$FAKE_BIN/copilot" \
  "$ROOT/adapters/jamsession_copilot" run new copilot-model high edit prompt
check "Copilot passes explicit effort with a named model" contains "$LOG" "--reasoning-effort high"

DEVIN_STATE="$TEMP_ROOT/devin-session-state"
rm -f "$LOG" "$DEVIN_STATE"
run_command env FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$DEVIN_STATE" \
  JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" run new grok-4.6 high edit prompt
check "Devin returns its response" equals "$stdout_file" DEVIN_RESULT
check "Devin reports the newly listed native session" contains "$stderr_file" "session: new-devin-session"
check "Devin resolves model and effort to an available ID" contains "$LOG" "--model grok-4-6-high"
check "Devin uses unattended edit permission" contains "$LOG" "--permission-mode dangerous"

run_command env FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$DEVIN_STATE" \
  JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" run saved-devin-session default default edit prompt
check "Devin resumes the exact requested session" contains "$LOG" "--resume saved-devin-session"
check "Devin reports the resumed session" contains "$stderr_file" "session: saved-devin-session"

rm -f "$LOG"
run_command env FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$DEVIN_STATE" \
  JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" run new grok-4.6 high read prompt
check "Devin rejects unenforceable read access" test "$status" -eq 2
check "rejected Devin read creates no session" test ! -e "$LOG"

run_command env FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$DEVIN_STATE" \
  JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" run new grok-4.6 xhigh edit prompt
check "Devin rejects an unavailable effort before launch" test "$status" -eq 2
check "Devin points to its live model list" contains "$stderr_file" "jamsession models devin"

run_command env FAKE_DEVIN_STATE="$DEVIN_STATE" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" list 1
check "Devin lists provider-native sessions" contains "$stdout_file" new-devin-session

run_command env FAKE_DEVIN_STATE="$DEVIN_STATE" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" doctor
check "Devin doctor checks native authentication" contains "$stdout_file" "authentication: ready"

# --- Devin automation marking over ACP ---------------------------------------
FAKE_ACP="$TEMP_ROOT/fake-devin-acp.py"
cat >"$FAKE_ACP" <<'EOF'
import json, os, sys
log = os.environ["FAKE_LOG"] + ".acp"
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    with open(log, "a") as f:
        f.write(json.dumps(msg) + "\n")
    if "id" not in msg:
        continue
    method = msg.get("method")
    result = {"sessionId": os.environ.get("FAKE_ACP_ID", "fake-acp-session")} \
        if method == "session/new" else \
        {"stopReason": "cancelled"} if method == "session/prompt" else {}
    sys.stdout.write(json.dumps(
        {"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\n")
    sys.stdout.flush()
EOF

DEVIN_ACP_HOME="$TEMP_ROOT/devin-acp-home"
mkdir -p "$DEVIN_ACP_HOME/.local/share/devin/cli"
if command -v python3 >/dev/null 2>&1; then
  rm -f "$LOG" "$LOG.acp"
  run_command env HOME="$DEVIN_ACP_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_ACP="$FAKE_ACP" \
    FAKE_DEVIN_STATE="$DEVIN_STATE" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
    "$ROOT/adapters/jamsession_devin" run new grok-4.6 high edit prompt
  check "Devin ACP run returns its response" equals "$stdout_file" DEVIN_RESULT
  check "Devin ACP run reports the pre-created session" contains "$stderr_file" "session: fake-acp-session"
  check "Devin ACP run resumes the pre-created session" contains "$LOG" "--resume fake-acp-session"
  check "Devin ACP pre-create marks automation" contains "$LOG.acp" '"cognition.ai/isAutomation": true'
  check "Devin ACP pre-create cancels the setup turn" contains "$LOG.acp" '"method": "session/cancel"'
  check "Devin ACP setup prompt points at the real task" contains "$LOG.acp" 'Jam Session created this session. Your task arrives in the next message; do that task fully.'
fi

if command -v python3 >/dev/null 2>&1 && command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DEVIN_ACP_HOME/.local/share/devin/cli/sessions.db" \
    "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT);
     CREATE TABLE IF NOT EXISTS message_nodes (session_id TEXT, node_id INTEGER, metadata TEXT);
     INSERT OR REPLACE INTO sessions VALUES ('fake-acp-session', 'Fake task title');"
  rm -f "$LOG" "$LOG.acp"
  run_command env HOME="$DEVIN_ACP_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_ACP="$FAKE_ACP" \
    FAKE_DEVIN_STATE="$DEVIN_STATE" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
    "$ROOT/adapters/jamsession_devin" run new grok-4.6 high edit prompt
  check "Devin ACP run attempts the [auto] rename" contains "$LOG.acp" '"[auto] Fake task title"'
  check "Devin ACP rename loads the session first" contains "$LOG.acp" '"method": "session/load"'

  sqlite3 "$DEVIN_ACP_HOME/.local/share/devin/cli/sessions.db" \
    "UPDATE sessions SET title = 'Jam Session created this session. Your task arrives in the next message; do t...' WHERE id = 'fake-acp-session';"
  rm -f "$LOG" "$LOG.acp"
  run_command env HOME="$DEVIN_ACP_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_ACP="$FAKE_ACP" \
    FAKE_DEVIN_STATE="$DEVIN_STATE" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
    "$ROOT/adapters/jamsession_devin" run new grok-4.6 high edit 'rename from this prompt'
  check "Devin ACP rename prefers the task text over a truncated setup title" contains "$LOG.acp" '"[auto] rename from this prompt"'
fi

DEVIN_STATE_OPTOUT="$TEMP_ROOT/devin-session-state-optout"
rm -f "$LOG" "$LOG.acp" "$DEVIN_STATE_OPTOUT"
run_command env HOME="$DEVIN_ACP_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_ACP="$FAKE_ACP" \
  FAKE_DEVIN_STATE="$DEVIN_STATE_OPTOUT" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  JAMSESSION_DEVIN_AUTOMATION=0 \
  "$ROOT/adapters/jamsession_devin" run new grok-4.6 high edit prompt
check "Devin automation opt-out skips ACP" test ! -e "$LOG.acp"
check "Devin automation opt-out uses the listed-session diff" contains "$stderr_file" "session: new-devin-session"

if command -v python3 >/dev/null 2>&1; then
  DEVIN_STATE_FAIL="$TEMP_ROOT/devin-session-state-fail"
  rm -f "$LOG" "$LOG.acp" "$DEVIN_STATE_FAIL"
  run_command env HOME="$DEVIN_ACP_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_ACP="$FAKE_ACP" \
    FAKE_ACP_FAIL=1 FAKE_DEVIN_STATE="$DEVIN_STATE_FAIL" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
    "$ROOT/adapters/jamsession_devin" run new grok-4.6 high edit prompt
  check "Devin ACP pre-create failure still runs" test "$status" -eq 0
  check "Devin ACP pre-create failure hints the fallback" contains "$stderr_file" "starting unflagged"
  check "Devin ACP pre-create failure uses the listed-session diff" contains "$stderr_file" "session: new-devin-session"

  rm -f "$LOG" "$LOG.acp"
  run_command env HOME="$DEVIN_ACP_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_ACP="$FAKE_ACP" \
    FAKE_DEVIN_STATE="$DEVIN_STATE" JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
    "$ROOT/adapters/jamsession_devin" run saved-devin-session default default edit prompt
  check "Devin resumed sessions skip ACP entirely" test ! -e "$LOG.acp"
  check "Devin resumed sessions still resume exactly" contains "$LOG" "--resume saved-devin-session"
fi

run_command env FAKE_LOG="$LOG" JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" \
  "$ROOT/adapters/jamsession_muse" run new muse-model medium read prompt
check "Muse returns its final response" equals "$stdout_file" MUSE_RESULT
check "Muse reports its native session ID" contains "$stderr_file" "session: muse-session"
check "Muse passes the explicit model" contains "$LOG" "--model muse-model"
check "Muse passes the explicit effort" contains "$LOG" "--reasoning-effort medium"
check "Muse read mode disables shell execution" contains "$LOG" "--disable-shell"
check "Muse read mode disables workspace writes" contains "$LOG" "--disable-write"

run_command env FAKE_LOG="$LOG" JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" \
  "$ROOT/adapters/jamsession_muse" run muse-session default default edit prompt
check "Muse resumes the requested session" contains "$LOG" "--session-id muse-session"
check "Muse edit mode omits read-only restrictions" sh -c "! grep -Eq -- '--disable-(shell|write)' '$LOG'"
check "Muse reports a resumed session" contains "$stderr_file" "session: muse-session"

MUSE_HOME="$TEMP_ROOT/muse-home"
mkdir -p "$MUSE_HOME/.local/share/muse/model-catalog" \
  "$MUSE_HOME/.local/share/muse/sessions/2026/09/24/older-session" \
  "$MUSE_HOME/.local/share/muse/sessions/2026/09/25/newer-session" \
  "$MUSE_HOME/.local/share/muse/sessions/2026/09/25/newer-session/subagent/child-session"
cat >"$MUSE_HOME/.local/share/muse/model-catalog/meta.json" <<'JSON'
{"rows":[
  {"model_id":"muse-current","visibility":"visible"},
  {"model_id":"muse-hidden","visibility":"hidden"},
  {"model_id":"muse-older","visibility":"visible"}
]}
JSON
: >"$MUSE_HOME/.local/share/muse/sessions/2026/09/24/older-session/session.jsonl"
: >"$MUSE_HOME/.local/share/muse/sessions/2026/09/25/newer-session/session.jsonl"
: >"$MUSE_HOME/.local/share/muse/sessions/2026/09/25/newer-session/subagent/child-session/session.jsonl"
run_command env JAMSESSION_CODEX_BIN="$FAKE_BIN/codex" "$ROOT/adapters/jamsession_codex" models
check "Codex models reads codex debug models" contains "$stdout_file" "codex-current - Codex Current - Workhorse. (efforts: low, high; default low)"
check "Codex models excludes hidden models" sh -c "! grep -Fq codex-hidden '$stdout_file'"
run_command env HOME="$MUSE_HOME" JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" "$ROOT/adapters/jamsession_muse" models
check "Muse lists cached visible models" contains "$stdout_file" muse-current
check "Muse excludes hidden models" sh -c "! grep -Fq muse-hidden '$stdout_file'"
run_command env HOME="$MUSE_HOME" JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" "$ROOT/adapters/jamsession_muse" list 1
check "Muse lists its newest local session" equals "$stdout_file" newer-session
check "Muse excludes child sessions" sh -c "! grep -Fq child-session '$stdout_file'"
run_command env HOME="$MUSE_HOME" JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" "$ROOT/adapters/jamsession_muse" list 0
check "Muse rejects a zero list count" test "$status" -eq 2
run_command env JAMSESSION_MUSE_BIN="$FAKE_BIN/muse" "$ROOT/adapters/jamsession_muse" doctor
check "Muse doctor does not claim authentication was verified" contains "$stdout_file" "authentication: not checked"

WHICH_HOME="$TEMP_ROOT/which-home"
mkdir -p \
  "$WHICH_HOME/.codex/sessions/2026/09/19" \
  "$WHICH_HOME/.claude/projects/project" \
  "$WHICH_HOME/.cursor/chats/workspace/cursor-session" \
  "$WHICH_HOME/.grok/sessions/project/grok-session" \
  "$WHICH_HOME/.copilot/session-state/copilot-session" \
  "$WHICH_HOME/.local/share/devin/cli" \
  "$WHICH_HOME/.local/share/muse/sessions/2026/09/19/muse-session"
: >"$WHICH_HOME/.codex/sessions/2026/09/19/rollout-test-codex-session.jsonl"
: >"$WHICH_HOME/.claude/projects/project/claude-session.jsonl"
: >"$WHICH_HOME/.cursor/chats/workspace/cursor-session/store.db"
: >"$WHICH_HOME/.grok/sessions/project/grok-session/events.jsonl"
: >"$WHICH_HOME/.copilot/session-state/copilot-session/events.jsonl"
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$WHICH_HOME/.local/share/devin/cli/sessions.db" <<'SQL'
CREATE TABLE sessions (id TEXT PRIMARY KEY, working_directory TEXT, last_activity_at INTEGER, title TEXT, main_chain_id INTEGER, hidden INTEGER DEFAULT 0);
CREATE TABLE message_nodes (session_id TEXT, node_id INTEGER, parent_node_id INTEGER, chat_message TEXT);
INSERT INTO sessions VALUES ('devin-session', '/tmp/work', 1, 'Test', 2, 0);
INSERT INTO message_nodes VALUES ('devin-session', 1, NULL, '{"role":"user","content":"hello"}');
INSERT INTO message_nodes VALUES ('devin-session', 2, 1, '{"role":"assistant","content":"hi"}');
SQL
else
  : >"$WHICH_HOME/.local/share/devin/cli/sessions.db"
fi
: >"$WHICH_HOME/.local/share/muse/sessions/2026/09/19/muse-session/session.jsonl"

run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which codex codex-session
check "Codex which resolves an exact transcript" contains "$stdout_file" "rollout-test-codex-session.jsonl"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which claude claude-session
check "Claude which resolves an exact transcript" contains "$stdout_file" "claude-session.jsonl"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which cursor cursor-session
check "Cursor which resolves its session store" contains "$stdout_file" "cursor-session/store.db"
check "Cursor which names its internal transcript limitation" contains "$stdout_file" "no stable raw transcript export"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which grok grok-session
check "Grok which recommends its native export" contains "$stdout_file" "grok export grok-session"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which copilot copilot-session
check "Copilot which resolves events JSONL" contains "$stdout_file" "copilot-session/events.jsonl"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which devin devin-session
check "Devin which resolves its SQLite store" contains "$stdout_file" ".local/share/devin/cli/sessions.db"
check "Devin which uses immutable mode without WAL sidecars" contains "$stdout_file" "immutable=1"
check "Devin which walks the live transcript chain" contains "$stdout_file" "WITH\\ RECURSIVE"
check "Devin which filters the requested session" contains "$stdout_file" "devin-session"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which devin
check "Devin which lists sessions from its SQLite store" contains "$stdout_file" "hidden\\ =\\ 0"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which muse muse-session
check "Muse which resolves session JSONL" contains "$stdout_file" "muse-session/session.jsonl"
check "Muse which recommends redacted native export" contains "$stdout_file" "muse export --session muse-session --redacted"
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which devin "bad' OR 1=1"
check "which rejects unsafe session characters" test "$status" -eq 2
run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which devin -x
check "which rejects option-like session IDs" test "$status" -eq 2
if command -v sqlite3 >/dev/null 2>&1; then
  run_command env HOME="$WHICH_HOME" "$ROOT/jamsession" which devin missing-session
  check "Devin which rejects an unknown session" test "$status" -eq 2
fi

mkdir -p "$WHICH_HOME/.local/share/devin/cli/session_locks"
printf '%s\n' "$$" >"$WHICH_HOME/.local/share/devin/cli/session_locks/locked-session.lock"
rm -f "$LOG"
run_command env HOME="$WHICH_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$DEVIN_STATE" \
  JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" run locked-session default default edit prompt
check "Devin rejects a resume held by a live process" test "$status" -eq 2
check "locked Devin guidance points to which" contains "$stderr_file" "jamsession which devin locked-session"
check "locked Devin resume does not invoke the provider" test ! -e "$LOG"

printf '%s\n' 99999999 >"$WHICH_HOME/.local/share/devin/cli/session_locks/stale-session.lock"
run_command env HOME="$WHICH_HOME" FAKE_LOG="$LOG" FAKE_DEVIN_STATE="$DEVIN_STATE" \
  JAMSESSION_DEVIN_BIN="$FAKE_BIN/devin" \
  "$ROOT/adapters/jamsession_devin" run stale-session default default edit prompt
check "Devin leaves stale-lock handling to the provider" contains "$LOG" "--resume stale-session"

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
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy new gemini-3.8-flash xhigh edit prompt
check "Antigravity returns the response" equals "$stdout_file" AGY_RESULT
check "Antigravity reports the native ID from its own launch" contains "$stderr_file" 'session: agy-session'
check "Antigravity prints native cumulative token usage" contains "$stderr_file" 'session-size: 12345 tokens'
check "Antigravity maps xhigh to high loudly" contains "$stderr_file" 'using high instead of xhigh'
check "Antigravity selects the effort-qualified Gemini model" contains "$LOG" 'gemini-3.8-flash-high'
check "Antigravity edit is explicitly unattended" contains "$LOG" '--dangerously-skip-permissions'
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run gemini agy-session gemini-3.8-flash-high medium edit prompt
check "Gemini provider alias resumes the exact session" contains "$LOG" 'agy-session'
check "Antigravity replaces the model effort suffix" contains "$LOG" 'gemini-3.8-flash-medium'
check "Antigravity never doubles effort suffixes" sh -c "! grep -Fq 'high-medium' '$LOG'"
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy new flash low edit prompt
check "Antigravity flash shorthand selects low variant" contains "$LOG" 'gemini-3.8-flash-low'
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy new default max edit prompt
check "Antigravity default model remains Gemini" contains "$LOG" 'gemini-3.8-flash-high'
check "Antigravity max downgrade warns" contains "$stderr_file" 'using high instead of max'
rm -f "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy new gemini high read prompt
check "Antigravity rejects unenforceable read-only access before launch" test "$status" -eq 2
check "Antigravity read rejection performs no provider call" test ! -e "$LOG"
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy new nonexistent high edit prompt
check "Antigravity validates against the live model catalog" test "$status" -eq 2
check "Antigravity rejected model prints available models" contains "$stderr_file" 'Available Antigravity models:'
check "Antigravity rejected model never starts a turn" test ! -e "$LOG"
run_command env FAKE_LOG="$LOG" FAKE_AGY_NO_SESSION=1 JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy new gemini medium edit prompt
check "Antigravity success without a resumable ID is a failure" test "$status" -ne 0
run_command env FAKE_LOG="$LOG" FAKE_AGY_STATUS=WAITING JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy new gemini high edit prompt
check "Antigravity waiting is not treated as completed work" test "$status" -ne 0
run_command env FAKE_LOG="$LOG" FAKE_EXIT=17 JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" run agy agy-session gemini medium edit prompt
check "Antigravity preserves provider failure status" test "$status" -eq 17
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" message agy agy-session question
check "Antigravity does not pretend to queue messages" test "$status" -eq 3
run_command env FAKE_LOG="$LOG" JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" message agy agy-session question --resume-with gemini high edit
check "Antigravity supports explicit message resume fallback" equals "$stdout_file" AGY_RESULT
check "Antigravity names the exited-owner requirement" contains "$stderr_file" 'target must have no owning process'
run_command env FAKE_LOG="$LOG" FAKE_AGY_AUTH_ERROR=1 JAMSESSION_ANTIGRAVITY_BIN="$FAKE_BIN/agy" "$ROOT/jamsession" doctor agy
check "Antigravity failed authentication is not ready" test "$status" -ne 0

AGY_HOME="$TEMP_ROOT/agy-home"
mkdir -p "$AGY_HOME/.gemini/antigravity-cli/conversations"
: >"$AGY_HOME/.gemini/antigravity-cli/conversations/agy-session.db"
run_command env HOME="$AGY_HOME" "$ROOT/jamsession" list agy 1
check "Antigravity lists local conversation IDs without an index dependency" equals "$stdout_file" agy-session
run_command env HOME="$AGY_HOME" "$ROOT/jamsession" which gemini agy-session
check "Antigravity which locates the native SQLite store" contains "$stdout_file" 'conversations/agy-session.db'
check "Antigravity which does not claim binary payloads are text" contains "$stdout_file" 'internal binary step payloads'
check "Antigravity which keeps inspection read-only" contains "$stdout_file" 'immutable=1'
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$AGY_HOME/.gemini/antigravity-cli/conversation_summaries.db" <<'SQL'
CREATE TABLE conversation_summaries (conversation_id TEXT, workspace_uris TEXT, parent_conversation_id TEXT, last_modified_time INTEGER);
INSERT INTO conversation_summaries VALUES ('scoped-session', '/tmp/Jamon''s_100%project', '', 1);
INSERT INTO conversation_summaries VALUES ('other-session', '/elsewhere', '', 2);
INSERT INTO conversation_summaries VALUES ('child-session', '/tmp/Jamon''s_100%project', 'scoped-session', 3);
SQL
  run_command env HOME="$AGY_HOME" JAMSESSION_CWD="/tmp/Jamon's_100%project" "$ROOT/jamsession" list agy 1
  check "Antigravity session index safely scopes quote and wildcard paths" equals "$stdout_file" scoped-session
fi
run_command env HOME="$TEMP_ROOT/user" JAMSESSION_HOME="$INIT_HOME" JAMSESSION_CONFIG="$INIT_HOME/jamsession.conf" \
  PATH="$FAKE_BIN:/usr/bin:/bin" "$ROOT/jamsession" init
check "init creates shell configuration" test -f "$INIT_HOME/jamsession.conf"
check "init records discovered Codex path" contains "$INIT_HOME/jamsession.conf" JAMSESSION_CODEX_BIN
check "init records discovered Muse path" contains "$INIT_HOME/jamsession.conf" JAMSESSION_MUSE_BIN
check "init records discovered agy path" contains "$INIT_HOME/jamsession.conf" JAMSESSION_ANTIGRAVITY_BIN
before="$(cat "$INIT_HOME/jamsession.conf")"
run_command env HOME="$TEMP_ROOT/user" JAMSESSION_HOME="$INIT_HOME" JAMSESSION_CONFIG="$INIT_HOME/jamsession.conf" \
  PATH="$FAKE_BIN:/usr/bin:/bin" "$ROOT/jamsession" init
check "init is idempotent" test "$(cat "$INIT_HOME/jamsession.conf")" = "$before"

INSTALL_HOME="$TEMP_ROOT/install-user"
mkdir -p "$INSTALL_HOME/.agents/jamsession/adapters"
printf '%s\n' custom >"$INSTALL_HOME/.agents/jamsession/adapters/jamsession_custom"
chmod 755 "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_custom"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "installer installs the command" test -x "$INSTALL_HOME/.agents/jamsession/bin/jamsession"
check "installer installs Devin's adapter" test -x "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_devin"
check "installer installs Muse's adapter" test -x "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_muse"
check "installer installs Antigravity's adapter" test -x "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_antigravity"
check "installer includes Codex's native control helper" test -f "$INSTALL_HOME/.agents/jamsession/adapters/_jamsession_codex_control.py"
check "installer links the command" test -L "$INSTALL_HOME/.local/bin/jamsession"
run_command env HOME="$INSTALL_HOME" JAMSESSION_USAGE_FIXTURE_DIR="$USAGE_FIXTURES" \
  "$INSTALL_HOME/.local/bin/jamsession" usage codex --json
check "the installed symlink finds its usage helper" contains "$stdout_file" '"agent":"codex"'
check "installer preserves unknown adapters" equals "$INSTALL_HOME/.agents/jamsession/adapters/jamsession_custom" custom
check "installer installs the summon-agent skill" test -f "$INSTALL_HOME/.agents/skills/jamsession-summon-agent/SKILL.md"
check "installer installs summon-agent metadata" test -f "$INSTALL_HOME/.agents/skills/jamsession-summon-agent/agents/openai.yaml"
check "installer installs the agent-usage skill" test -f "$INSTALL_HOME/.agents/skills/jamsession-get-agent-usage/SKILL.md"
check "installer installs agent-usage metadata" test -f "$INSTALL_HOME/.agents/skills/jamsession-get-agent-usage/agents/openai.yaml"
run_command env HOME="$INSTALL_HOME" JAMSESSION_CWD="$INBOX_PROJECT" \
  "$INSTALL_HOME/.local/bin/jamsession" inbox installed-reader write installed-sender 'installed inbox note'
check "the installed CLI writes project-local inbox notes" test "$status" -eq 0
run_command env HOME="$INSTALL_HOME" JAMSESSION_CWD="$INBOX_PROJECT" \
  "$INSTALL_HOME/.local/bin/jamsession" inbox installed-reader read
check "the installed CLI drains attributed inbox notes" contains "$stdout_file" 'From: installed-sender'

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install jamsession-work-over-ssh
check "optional skill installs on request" test -f "$INSTALL_HOME/.agents/skills/jamsession-work-over-ssh/SKILL.md"
check "optional skill installs its metadata" test -f "$INSTALL_HOME/.agents/skills/jamsession-work-over-ssh/agents/openai.yaml"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" "$ROOT/jamsession" skills
check "skills lists installed state" contains "$stdout_file" "jamsession-work-over-ssh"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install jamsession-model-recommendations
check "model-recommendations skill installs on request" test -f "$INSTALL_HOME/.agents/skills/jamsession-model-recommendations/SKILL.md"
check "model recommendations install the current source bytes" cmp -s "$ROOT/skills/jamsession-model-recommendations/SKILL.md" "$INSTALL_HOME/.agents/skills/jamsession-model-recommendations/SKILL.md"

run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install jamsession-use-agent-worksheet
check "agent-worksheet skill installs on request" test -f "$INSTALL_HOME/.agents/skills/jamsession-use-agent-worksheet/SKILL.md"
check "agent-worksheet skill installs its metadata" test -f "$INSTALL_HOME/.agents/skills/jamsession-use-agent-worksheet/agents/openai.yaml"

# --- Skill resource bundles: isolated local downloads, no provider calls ---
RESOURCE_SOURCE="$TEMP_ROOT/resource-source"
RESOURCE_SKILL=jamsession-work-over-ssh
RESOURCE_PACKAGE="$RESOURCE_SOURCE/skills/$RESOURCE_SKILL"
RESOURCE_TARGET="$INSTALL_HOME/.agents/skills/$RESOURCE_SKILL"
mkdir -p "$RESOURCE_SOURCE"
cp "$ROOT/jamsession" "$RESOURCE_SOURCE/"
cp -R "$ROOT/adapters" "$ROOT/usage" "$ROOT/skills" "$RESOURCE_SOURCE/"
mkdir -p "$RESOURCE_PACKAGE/references" "$RESOURCE_PACKAGE/assets"
printf '%s\n' references/guide.md assets/template.json >"$RESOURCE_PACKAGE/resources.txt"
printf '%s\n' 'resource v1' >"$RESOURCE_PACKAGE/references/guide.md"
printf '%s\n' '{"template":1}' >"$RESOURCE_PACKAGE/assets/template.json"
resource_install() {
  env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
    JAMSESSION_SKILL_DIR="$INSTALL_HOME/.agents/skills" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" \
    "$ROOT/jamsession" skills install "$RESOURCE_SKILL"
}
run_command resource_install
check "skill install stages resource bundle" test "$status" -eq 0
check "skill install copies references" equals "$RESOURCE_TARGET/references/guide.md" 'resource v1'
check "skill install copies assets" equals "$RESOURCE_TARGET/assets/template.json" '{"template":1}'
check "skill install records resource manifest" cmp -s "$RESOURCE_PACKAGE/resources.txt" "$RESOURCE_TARGET/resources.txt"
printf '%s\n' 'resource v2' >"$RESOURCE_PACKAGE/references/guide.md"
run_command resource_install
check "skill reinstall refreshes resources" equals "$RESOURCE_TARGET/references/guide.md" 'resource v2'
printf '%s\n' 'resource v3' >"$RESOURCE_PACKAGE/references/guide.md"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" sh "$ROOT/install.sh"
check "standalone installer refreshes installed optional resources" equals "$RESOURCE_TARGET/references/guide.md" 'resource v3'
printf '%s\n' 'resource v4' >"$RESOURCE_PACKAGE/references/guide.md"
run_command env HOME="$INSTALL_HOME" JAMSESSION_HOME="$INSTALL_HOME/.agents/jamsession" \
  JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" JAMSESSION_INSTALL_URL="file://$ROOT/install.sh" \
  "$ROOT/jamsession" update
check "CLI update refreshes installed skill resources" equals "$RESOURCE_TARGET/references/guide.md" 'resource v4'
printf '%s\n' 'resource v3' >"$RESOURCE_PACKAGE/references/guide.md"
run_command resource_install
mkdir -p "$INSTALL_HOME/.agents/skills/custom-skill"
printf '%s\n' custom >"$INSTALL_HOME/.agents/skills/custom-skill/SKILL.md"
cp "$RESOURCE_TARGET/SKILL.md" "$TEMP_ROOT/resource-old-skill"
cp "$INSTALL_HOME/.agents/jamsession/bin/jamsession" "$TEMP_ROOT/resource-old-cli"
# Different source bytes make preservation assertions capable of detecting replacement.
printf '%s\n' '# newer source marker' >>"$RESOURCE_SOURCE/jamsession"
printf '%s\n' 'Newer skill source marker.' >>"$RESOURCE_PACKAGE/SKILL.md"
for unsafe in '../escape.md' '/absolute.md' 'references/../escape.md' 'references//bad.md' 'references/./bad.md' 'assets/' ''; do
  printf '%s\n' "$unsafe" >"$RESOURCE_PACKAGE/resources.txt"
  run_command resource_install
  check "skill install rejects unsafe manifest [$unsafe]" test "$status" -ne 0
  check "unsafe manifest preserves old skill [$unsafe]" cmp -s "$TEMP_ROOT/resource-old-skill" "$RESOURCE_TARGET/SKILL.md"
  check "unsafe manifest preserves old resource [$unsafe]" equals "$RESOURCE_TARGET/references/guide.md" 'resource v3'
done
printf '%s\n' '../escape.md' >"$RESOURCE_PACKAGE/resources.txt"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" sh "$ROOT/install.sh"
check "installer rejects unsafe resource manifest" test "$status" -ne 0
check "unsafe installer bundle preserves prior CLI" cmp -s "$TEMP_ROOT/resource-old-cli" "$INSTALL_HOME/.agents/jamsession/bin/jamsession"
printf '%s\n' references/guide.md assets/missing.json >"$RESOURCE_PACKAGE/resources.txt"
printf '%s\n' 'must not replace old resource' >"$RESOURCE_PACKAGE/references/guide.md"
run_command resource_install
check "missing required resource fails skill installation" test "$status" -ne 0
check "missing resource preserves prior resource" equals "$RESOURCE_TARGET/references/guide.md" 'resource v3'
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" sh "$ROOT/install.sh"
check "missing required resource fails entire installer staging" test "$status" -ne 0
check "missing installer resource preserves prior CLI" cmp -s "$TEMP_ROOT/resource-old-cli" "$INSTALL_HOME/.agents/jamsession/bin/jamsession"
check "missing installer resource preserves prior guide" equals "$RESOURCE_TARGET/references/guide.md" 'resource v3'
check "missing installer resource preserves prior skill" cmp -s "$TEMP_ROOT/resource-old-skill" "$RESOURCE_TARGET/SKILL.md"
printf '%s\n' references/guide.md >"$RESOURCE_PACKAGE/resources.txt"
rm "$RESOURCE_PACKAGE/references/guide.md"
ln -s "$TEMP_ROOT/resource-old-skill" "$RESOURCE_PACKAGE/references/guide.md"
run_command resource_install
check "local resource source symlink is rejected" test "$status" -ne 0
rm "$RESOURCE_PACKAGE/references/guide.md"
printf '%s\n' safe >"$RESOURCE_PACKAGE/references/guide.md"
mv "$RESOURCE_TARGET/references" "$RESOURCE_TARGET/references-held"
ln -s "$RESOURCE_TARGET/references-held" "$RESOURCE_TARGET/references"
run_command resource_install
check "resource destination directory symlink is rejected" test "$status" -ne 0
check "destination symlink target remains unchanged" equals "$RESOURCE_TARGET/references-held/guide.md" 'resource v3'
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" sh "$ROOT/install.sh"
check "installer rejects destination resource symlink before replacement" test "$status" -ne 0
check "destination symlink rejection preserves installed CLI" cmp -s "$TEMP_ROOT/resource-old-cli" "$INSTALL_HOME/.agents/jamsession/bin/jamsession"
rm "$RESOURCE_TARGET/references"
mv "$RESOURCE_TARGET/references-held" "$RESOURCE_TARGET/references"
# Non-directory parents must fail during staging, before changing the old skill.
mv "$RESOURCE_TARGET/references" "$RESOURCE_TARGET/references-held"
printf '%s\n' not-a-directory >"$RESOURCE_TARGET/references"
run_command resource_install
check "CLI rejects non-directory resource parent during staging" test "$status" -ne 0
check "bad resource parent preserves old skill" cmp -s "$TEMP_ROOT/resource-old-skill" "$RESOURCE_TARGET/SKILL.md"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" sh "$ROOT/install.sh"
check "installer rejects non-directory resource parent" test "$status" -ne 0
check "bad resource parent preserves installed CLI" cmp -s "$TEMP_ROOT/resource-old-cli" "$INSTALL_HOME/.agents/jamsession/bin/jamsession"
rm "$RESOURCE_TARGET/references"
mv "$RESOURCE_TARGET/references-held" "$RESOURCE_TARGET/references"

# Commit-time filesystem errors must return failure, never print success.
RESOURCE_FAIL_BIN="$TEMP_ROOT/resource-fail-bin"
mkdir -p "$RESOURCE_FAIL_BIN"
for failing_command in mkdir chmod mv; do
  if [ "$failing_command" = mkdir ]; then
    cat >"$RESOURCE_FAIL_BIN/mkdir" <<'SH'
#!/bin/sh
case "$*" in *'/skills/jamsession-work-over-ssh/agents'*) exit 17 ;; esac
exec /bin/mkdir "$@"
SH
  else
    printf '#!/bin/sh\nexit 17\n' >"$RESOURCE_FAIL_BIN/$failing_command"
  fi
  chmod 755 "$RESOURCE_FAIL_BIN/$failing_command"
  PATH="$RESOURCE_FAIL_BIN:$PATH" run_command resource_install
  check "CLI reports $failing_command installation failure" test "$status" -ne 0
  check "CLI does not claim success after $failing_command failure" sh -c '! grep -q "^Installed " "$1"' sh "$stdout_file"
  check "$failing_command failure before replacement preserves old skill" cmp -s "$TEMP_ROOT/resource-old-skill" "$RESOURCE_TARGET/SKILL.md"
  rm "$RESOURCE_FAIL_BIN/$failing_command"
done

rm "$RESOURCE_PACKAGE/resources.txt"
run_command resource_install
check "legacy package without manifest still installs" test "$status" -eq 0
check "legacy reinstall leaves unrelated package files alone" equals "$RESOURCE_TARGET/references/guide.md" 'resource v3'
check "resource installs preserve custom skills" equals "$INSTALL_HOME/.agents/skills/custom-skill/SKILL.md" custom

# Install the real kit and verify its resource manifest matches its local links.
COMPARISON_SKILL=jamsession-run-agent-comparison
COMPARISON_SOURCE="$ROOT/skills/$COMPARISON_SKILL"
COMPARISON_ROOT="$TEMP_ROOT/comparison-skills"
COMPARISON_LINK="$TEMP_ROOT/comparison-skills-link"
mkdir -p "$COMPARISON_ROOT"
ln -s "$COMPARISON_ROOT" "$COMPARISON_LINK"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SKILL_DIR="$COMPARISON_LINK" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install "$COMPARISON_SKILL"
check "CLI installs actual comparison kit through symlinked skills root" test "$status" -eq 0
check "actual comparison resources match links and installed bytes" python3 - "$COMPARISON_SOURCE" "$COMPARISON_ROOT/$COMPARISON_SKILL" <<'PY'
from pathlib import Path
import re, sys
source, installed = map(Path, sys.argv[1:])
manifest = source.joinpath('resources.txt').read_text().splitlines()
links = re.findall(r'\]\((?:\./)?((?:references|assets)/[^)#\s]+)(?:#[^)]*)?\)', source.joinpath('SKILL.md').read_text())
assert len(manifest) == len(set(manifest))
assert set(links) == set(manifest), (links, manifest)
actual = {str(p.relative_to(source)) for folder in ('references', 'assets') for p in source.joinpath(folder).rglob('*') if p.is_file()}
assert actual == set(manifest), (actual, manifest)
for name in ['SKILL.md'] + [p for p in manifest if p.endswith('.md')]:
    for link in re.findall(r'\]\(([^)]+)\)', source.joinpath(name).read_text()):
        if '://' in link or link.startswith(('#', 'mailto:')):
            continue
        target = source.joinpath(name).parent.joinpath(link.split('#')[0]).resolve()
        assert target.is_relative_to(source.resolve()) and target.is_file(), (name, link)
for name in ['SKILL.md', 'agents/openai.yaml', 'resources.txt'] + manifest:
    assert source.joinpath(name).read_bytes() == installed.joinpath(name).read_bytes(), name
PY
printf '%s\n' stale >"$COMPARISON_ROOT/$COMPARISON_SKILL/assets/coordinator-prompt.md"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SKILL_DIR="$COMPARISON_LINK" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "installer refreshes comparison kit through symlinked skills root" test "$status" -eq 0
check "installer restores actual comparison asset" cmp -s "$COMPARISON_SOURCE/assets/coordinator-prompt.md" "$COMPARISON_ROOT/$COMPARISON_SKILL/assets/coordinator-prompt.md"
mv "$COMPARISON_ROOT/$COMPARISON_SKILL" "$COMPARISON_ROOT/held-package"
ln -s "$COMPARISON_ROOT/held-package" "$COMPARISON_ROOT/$COMPARISON_SKILL"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SKILL_DIR="$COMPARISON_LINK" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install "$COMPARISON_SKILL"
check "individual package symlink remains rejected" test "$status" -ne 0
rm "$COMPARISON_ROOT/$COMPARISON_SKILL"
mv "$COMPARISON_ROOT/held-package" "$COMPARISON_ROOT/$COMPARISON_SKILL"
# Losing the manifest of a resource-linked skill must not turn it into a legacy package.
cp -R "$COMPARISON_SOURCE" "$RESOURCE_SOURCE/skills/kit-without-manifest"
rm "$RESOURCE_SOURCE/skills/kit-without-manifest/resources.txt"
mv "$RESOURCE_SOURCE/skills/$COMPARISON_SKILL" "$RESOURCE_SOURCE/skills/kit-original"
mv "$RESOURCE_SOURCE/skills/kit-without-manifest" "$RESOURCE_SOURCE/skills/$COMPARISON_SKILL"
printf '%s\n' '# newer source marker' >>"$RESOURCE_SOURCE/skills/$COMPARISON_SKILL/SKILL.md"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SKILL_DIR="$COMPARISON_LINK" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" \
  "$ROOT/jamsession" skills install "$COMPARISON_SKILL"
check "resource-linked skill rejects missing manifest" test "$status" -ne 0
check "missing linked manifest preserves old skill" cmp -s "$COMPARISON_SOURCE/SKILL.md" "$COMPARISON_ROOT/$COMPARISON_SKILL/SKILL.md"
run_command env HOME="$INSTALL_HOME" JAMSESSION_SKILL_DIR="$COMPARISON_LINK" JAMSESSION_SOURCE_URL="file://$RESOURCE_SOURCE" sh "$ROOT/install.sh"
check "installer rejects missing manifest for linked resources" test "$status" -ne 0
check "missing linked manifest preserves old bundle" cmp -s "$COMPARISON_SOURCE/SKILL.md" "$COMPARISON_ROOT/$COMPARISON_SKILL/SKILL.md"

# Simulate an HTTP404 specifically for the manifest while other fetches succeed.
cat >"$RESOURCE_FAIL_BIN/curl" <<'SH'
#!/bin/sh
case "$*" in */resources.txt*) printf 404; exit 22 ;; esac
exec /usr/bin/curl "$@"
SH
chmod 755 "$RESOURCE_FAIL_BIN/curl"
run_command env PATH="$RESOURCE_FAIL_BIN:$PATH" HOME="$INSTALL_HOME" JAMSESSION_SKILL_DIR="$COMPARISON_LINK" JAMSESSION_SOURCE_URL="file://$ROOT" \
  "$ROOT/jamsession" skills install "$COMPARISON_SKILL"
check "HTTP404 cannot silently omit a linked resource kit" test "$status" -ne 0
check "HTTP404 linked manifest preserves old skill" cmp -s "$COMPARISON_SOURCE/SKILL.md" "$COMPARISON_ROOT/$COMPARISON_SKILL/SKILL.md"
rm "$RESOURCE_FAIL_BIN/curl"

# --- Second run: recognized files refresh, everything else survives ---
INSTALLED="$INSTALL_HOME/.agents/jamsession"
INSTALLED_SKILLS="$INSTALL_HOME/.agents/skills"
mkdir -p "$INSTALLED_SKILLS/jamsession-agent-worker-task" "$INSTALLED_SKILLS/jamsession-run-remote-agents"
printf '%s\n' old >"$INSTALLED_SKILLS/jamsession-agent-worker-task/SKILL.md"
printf '%s\n' old >"$INSTALLED_SKILLS/jamsession-run-remote-agents/SKILL.md"
printf '%s\n' stale >"$INSTALLED/bin/jamsession"
printf '%s\n' stale >"$INSTALLED/adapters/jamsession_codex"
printf '%s\n' stale >"$INSTALLED/adapters/_jamsession_adapter_common"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-summon-agent/SKILL.md"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-summon-agent/agents/openai.yaml"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-get-agent-usage/SKILL.md"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-work-over-ssh/SKILL.md"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-use-agent-worksheet/SKILL.md"
printf '%s\n' stale >"$INSTALLED_SKILLS/jamsession-use-agent-worksheet/agents/openai.yaml"
printf '%s\n' 'JAMSESSION_CUSTOM_SETTING=kept' >>"$INSTALLED/jamsession.conf"

run_command env HOME="$INSTALL_HOME" JAMSESSION_SOURCE_URL="file://$ROOT" sh "$ROOT/install.sh"
check "a second install succeeds" test "$status" -eq 0
check "second install refreshes the command" contains "$INSTALLED/bin/jamsession" JAMSESSION_VERSION
check "second install refreshes a bundled adapter" contains "$INSTALLED/adapters/jamsession_codex" jamsession_validate_run
check "second install refreshes the adapter helper" contains "$INSTALLED/adapters/_jamsession_adapter_common" jamsession_adapter_setup
check "second install refreshes the default skill" contains "$INSTALLED_SKILLS/jamsession-summon-agent/SKILL.md" "name: jamsession-summon-agent"
check "second install refreshes default skill metadata" contains "$INSTALLED_SKILLS/jamsession-summon-agent/agents/openai.yaml" "interface:"
check "second install refreshes the default usage skill" contains "$INSTALLED_SKILLS/jamsession-get-agent-usage/SKILL.md" "name: jamsession-get-agent-usage"
check "second install migrates the worker skill name" test -f "$INSTALLED_SKILLS/jamsession-individual-worker-workflow/SKILL.md"
check "second install removes the retired worker identifier" test ! -e "$INSTALLED_SKILLS/jamsession-agent-worker-task"
check "second install migrates the remote-agent skill name" test -f "$INSTALLED_SKILLS/jamsession-use-remote-agent-over-ssh/SKILL.md"
check "second install removes the retired remote-agent identifier" test ! -e "$INSTALLED_SKILLS/jamsession-run-remote-agents"
check "second install refreshes an installed optional skill" contains "$INSTALLED_SKILLS/jamsession-work-over-ssh/SKILL.md" "name: jamsession-work-over-ssh"
check "second install refreshes the worksheet skill" contains "$INSTALLED_SKILLS/jamsession-use-agent-worksheet/SKILL.md" "name: jamsession-use-agent-worksheet"
check "second install refreshes worksheet metadata" contains "$INSTALLED_SKILLS/jamsession-use-agent-worksheet/agents/openai.yaml" "interface:"
check "second install preserves configuration" contains "$INSTALLED/jamsession.conf" JAMSESSION_CUSTOM_SETTING=kept
check "second install preserves a custom adapter" equals "$INSTALLED/adapters/jamsession_custom" custom
check "second install leaves uninstalled optional skills absent" test ! -e "$INSTALLED_SKILLS/jamsession-ask-agent-panel/SKILL.md"
check "second install leaves no staging files behind" sh -c "! ls '$INSTALLED/bin/'*.jamsession-new '$INSTALLED/adapters/'*.jamsession-new >/dev/null 2>&1"
check "installed command stays executable" test -x "$INSTALLED/bin/jamsession"
check "installed usage helper stays executable" test -x "$INSTALLED/bin/jamsession_usage"
check "installed terminal usage reader stays executable" test -x "$INSTALLED/bin/jamsession_tui_usage.py"
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
missing_metadata=""
while IFS= read -r listed_skill; do
  listed_skill="${listed_skill%% *}"
  [ -n "$listed_skill" ] || continue
  [ -f "$ROOT/skills/$listed_skill/SKILL.md" ] || missing_skill="$listed_skill"
  [ -f "$ROOT/skills/$listed_skill/agents/openai.yaml" ] || missing_metadata="$listed_skill"
done < <(env JAMSESSION_SKILL_DIR="$TEMP_ROOT/none" "$ROOT/jamsession" skills)
check "every listed skill exists in the repository" test -z "$missing_skill"
check "every listed skill has agent metadata" test -z "$missing_metadata"

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
check "the checkout worker skill survived every refusal" test -f "$ROOT/skills/jamsession-individual-worker-workflow/SKILL.md"
check "the refused installation was left alone" test -x "$UNINSTALL_HOME/.agents/jamsession/bin/jamsession"

run_command env HOME="$UNINSTALL_HOME" "$ROOT/jamsession" help uninstall
check "uninstall help lists what it removes" contains "$stdout_file" "Removes only what the installer created"
check "uninstall help states the safety rule" contains "$stdout_file" "never removes"
run_command env HOME="$UNINSTALL_HOME" "$ROOT/jamsession" help
check "main help lists uninstall" contains "$stdout_file" "jamsession uninstall"

check "the site workflow ships the install guide linked from the home page" \
  sh -c "grep -Fq 'install.md' '$ROOT/.github/workflows/pages.yml'"
check "the site workflow ships image assets" \
  sh -c "grep -Fq 'cp -R assets _site/' '$ROOT/.github/workflows/pages.yml'"
check "the home page demotes manual installation" \
  sh -c "grep -Fq '<details class=\"manual-install\">' '$ROOT/index.html'"
check "the install prompt is presented as an agent message" \
  sh -c "grep -Fq '<div class=\"prompt-card agent-message\">' '$ROOT/index.html'"
check "the home page uses the orchestration screenshot" \
  sh -c "grep -Fq 'assets/jamsession-orchestration-example.png' '$ROOT/index.html'"
check "the orchestration screenshot ships with the site" \
  test -s "$ROOT/assets/jamsession-orchestration-example.png"
check "the test workflow runs the current test path" \
  sh -c "grep -Fq 'tests/test_jamsession.sh' '$ROOT/.github/workflows/test.yml'"
check "no workflow still refers to the old name" \
  sh -c "! grep -rqi jamwrap '$ROOT/.github/workflows/'"
check "the model recommendation skill is bundled" \
  sh -c "grep -q '^name: jamsession-model-recommendations$' '$ROOT/skills/jamsession-model-recommendations/SKILL.md'"
check "model recommendations install their current UI metadata" \
  cmp -s "$ROOT/skills/jamsession-model-recommendations/agents/openai.yaml" "$INSTALL_HOME/.agents/skills/jamsession-model-recommendations/agents/openai.yaml"
check "the agent-usage skill requests structured usage" \
  sh -c "grep -Fq 'jamsession usage --json' '$ROOT/skills/jamsession-get-agent-usage/SKILL.md'"
check "the remote-agent skill depends on no separately optional skill" \
  sh -c "! grep -Eq 'jamsession-(individual-worker-workflow|work-over-ssh|orchestrate-agent-work)' '$ROOT/skills/jamsession-use-remote-agent-over-ssh/SKILL.md'"
check "retired skill identifiers are absent from active source" \
  sh -c "! grep -R -E 'jamsession-(agent-worker-task|run-remote-agents)' '$ROOT/skills' '$ROOT/jamsession' '$ROOT/README.md' '$ROOT/index.html'"
check "the website summarizes orchestrator support skills" \
  grep -Fq 'supporting skills for worksheets, worker discipline, and SSH' "$ROOT/index.html"

check "Codex native control delivery and resume contracts" python3 "$ROOT/tests/test_codex_control.py"
check "Codex launch settings preserve native configuration" python3 "$ROOT/tests/test_codex_launch_settings.py"
check "parallel adapter sessions keep independent OS-backed IDs" python3 "$ROOT/tests/test_adapter_sessions.py"
check "quota reader process cleanup always has a deadline" python3 "$ROOT/tests/test_tui_usage.py"

printf '\n%d passed, %d failed\n' "$passed" "$failed"
[ "$failed" -eq 0 ]
