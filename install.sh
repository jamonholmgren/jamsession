#!/bin/sh

set -eu

SOURCE_URL=${JAMSESSION_SOURCE_URL:-https://raw.githubusercontent.com/jamonholmgren/jamsession/main}
INSTALL_ROOT=${JAMSESSION_HOME:-"$HOME/.agents/jamsession"}
SKILL_ROOT=${JAMSESSION_SKILL_DIR:-"$HOME/.agents/skills"}
BIN_DIR="$INSTALL_ROOT/bin"
ADAPTER_DIR="$INSTALL_ROOT/adapters"
LINK_DIR="$HOME/.local/bin"

PROVIDERS="codex claude cursor grok copilot"
DEFAULT_SKILLS="jamsession-summon-agent jamsession-get-agent-usage"
OPTIONAL_SKILLS="jamsession-model-recommendations jamsession-ping-pong-planning
jamsession-contrarian-review jamsession-ask-agent-panel
jamsession-orchestrate-agent-work jamsession-individual-worker-workflow
jamsession-work-over-ssh jamsession-use-remote-agent-over-ssh"
RENAMED_SKILLS="jamsession-agent-worker-task:jamsession-individual-worker-workflow
jamsession-run-remote-agents:jamsession-use-remote-agent-over-ssh"

command -v curl >/dev/null 2>&1 || {
  echo "jamsession installer: curl is required" >&2
  exit 1
}

STAGE=$(mktemp -d "${TMPDIR:-/tmp}/jamsession-install.XXXXXX") || {
  echo "jamsession installer: could not create a private temporary directory" >&2
  exit 1
}
trap 'rm -rf "$STAGE"' EXIT
trap 'rm -rf "$STAGE"; exit 130' HUP INT TERM

abort() {
  echo "jamsession installer: $1" >&2
  echo "jamsession installer: nothing installed was changed" >&2
  exit 1
}

fetch() {
  staged="$STAGE/$2"
  mkdir -p "$(dirname "$staged")"
  curl -fsSL "$SOURCE_URL/$1" -o "$staged" || abort "could not download $1"
  [ -s "$staged" ] || abort "$1 downloaded empty"
}

require_script() {
  case "$(head -n 1 "$STAGE/$1")" in
    '#!'*) ;;
    *) abort "staged $1 is not a script" ;;
  esac
}

require_line() {
  grep -q "$2" "$STAGE/$1" || abort "staged $1 is missing $3"
}

# Stage the complete recognized bundle before replacing anything. A download
# that fails partway must not leave a mix of old and new versions installed.
fetch jamsession jamsession
fetch usage/jamsession_usage usage/jamsession_usage
fetch adapters/_jamsession_adapter_common adapters/_jamsession_adapter_common
for provider in $PROVIDERS; do
  fetch "adapters/jamsession_$provider" "adapters/jamsession_$provider"
done

# The default skills are always refreshed. Optional skills are refreshed only when
# the user has already installed them.
skills=$DEFAULT_SKILLS
for skill in $OPTIONAL_SKILLS; do
  if [ -f "$SKILL_ROOT/$skill/SKILL.md" ]; then
    skills="$skills $skill"
  fi
done
for rename in $RENAMED_SKILLS; do
  old=${rename%%:*}
  new=${rename#*:}
  if [ -f "$SKILL_ROOT/$old/SKILL.md" ]; then
    skills="$skills $new"
  fi
done
for skill in $skills; do
  fetch "skills/$skill/SKILL.md" "skills/$skill/SKILL.md"
  fetch "skills/$skill/agents/openai.yaml" "skills/$skill/agents/openai.yaml"
done
require_script jamsession
require_script usage/jamsession_usage
for provider in $PROVIDERS; do
  require_script "adapters/jamsession_$provider"
done
for skill in $skills; do
  require_line "skills/$skill/SKILL.md" "^name: $skill\$" "its skill name"
  require_line "skills/$skill/agents/openai.yaml" '^interface:' "its agent metadata"
done

mkdir -p "$BIN_DIR" "$ADAPTER_DIR" "$SKILL_ROOT" "$LINK_DIR"

# Rename into place so a reader never sees a half-written file.
install_file() {
  temporary="$2.jamsession-new"
  cp "$STAGE/$1" "$temporary"
  chmod "$3" "$temporary"
  mv "$temporary" "$2"
}

install_file jamsession "$BIN_DIR/jamsession" 755
install_file usage/jamsession_usage "$BIN_DIR/jamsession_usage" 755
install_file adapters/_jamsession_adapter_common "$ADAPTER_DIR/_jamsession_adapter_common" 644
for provider in $PROVIDERS; do
  install_file "adapters/jamsession_$provider" "$ADAPTER_DIR/jamsession_$provider" 755
done
for skill in $skills; do
  mkdir -p "$SKILL_ROOT/$skill/agents"
  install_file "skills/$skill/SKILL.md" "$SKILL_ROOT/$skill/SKILL.md" 644
  install_file "skills/$skill/agents/openai.yaml" "$SKILL_ROOT/$skill/agents/openai.yaml" 644
done
for rename in $RENAMED_SKILLS; do
  old=${rename%%:*}
  new=${rename#*:}
  if [ -d "$SKILL_ROOT/$old" ] && [ ! -L "$SKILL_ROOT/$old" ]; then
    rm -rf "$SKILL_ROOT/$old"
    echo "Renamed $old to $new" >&2
  fi
done

link="$LINK_DIR/jamsession"
if [ -e "$link" ] && [ ! -L "$link" ]; then
  echo "jamsession installer: leaving existing non-symlink at $link" >&2
  echo "jamsession installer: add $BIN_DIR to PATH or move that file yourself" >&2
else
  ln -sfn "$BIN_DIR/jamsession" "$link"
fi

JAMSESSION_HOME="$INSTALL_ROOT" JAMSESSION_SKILL_DIR="$SKILL_ROOT" "$BIN_DIR/jamsession" init

case ":${PATH:-}:" in
  *":$LINK_DIR:"*) ;;
  *)
    echo >&2
    echo "Add this directory to PATH:" >&2
    echo "  $LINK_DIR" >&2
    ;;
esac

echo >&2
echo "Installed Jam Session in $INSTALL_ROOT" >&2
echo "Run: jamsession status" >&2
