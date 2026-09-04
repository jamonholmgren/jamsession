#!/bin/sh

set -eu

SOURCE_URL=${JAMSESSION_SOURCE_URL:-https://raw.githubusercontent.com/jamonholmgren/jamsession/main}
INSTALL_ROOT=${JAMSESSION_HOME:-"$HOME/.agents/jamsession"}
SKILL_ROOT=${JAMSESSION_SKILL_DIR:-"$HOME/.agents/skills"}
BIN_DIR="$INSTALL_ROOT/bin"
ADAPTER_DIR="$INSTALL_ROOT/adapters"
PACK_DIR="$INSTALL_ROOT/packs"
LINK_DIR="$HOME/.local/bin"

PROVIDERS="codex claude cursor grok copilot"
DEFAULT_SKILL=jamsession-summon-agent
OPTIONAL_SKILLS="jamsession-select-agent-model jamsession-ping-pong-planning
jamsession-contrarian-review jamsession-ask-agent-panel
jamsession-orchestrate-agent-work jamsession-execute-agent-slice
jamsession-work-over-ssh jamsession-run-remote-agents"

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
fetch adapters/_jamsession_adapter_common adapters/_jamsession_adapter_common
for provider in $PROVIDERS; do
  fetch "adapters/jamsession_$provider" "adapters/jamsession_$provider"
done
fetch packs/jamon.tsv packs/jamon.tsv

# The default skill is always refreshed. Optional skills are refreshed only when
# the user has already installed them.
skills=$DEFAULT_SKILL
for skill in $OPTIONAL_SKILLS; do
  if [ -f "$SKILL_ROOT/$skill/SKILL.md" ]; then
    skills="$skills $skill"
  fi
done
for skill in $skills; do
  fetch "skills/$skill/SKILL.md" "skills/$skill/SKILL.md"
done

require_script jamsession
for provider in $PROVIDERS; do
  require_script "adapters/jamsession_$provider"
done
require_line packs/jamon.tsv '^# pack:' "its pack metadata"
for skill in $skills; do
  require_line "skills/$skill/SKILL.md" "^name: $skill\$" "its skill name"
done

mkdir -p "$BIN_DIR" "$ADAPTER_DIR" "$PACK_DIR" "$SKILL_ROOT" "$LINK_DIR"

# Rename into place so a reader never sees a half-written file.
install_file() {
  temporary="$2.jamsession-new"
  cp "$STAGE/$1" "$temporary"
  chmod "$3" "$temporary"
  mv "$temporary" "$2"
}

install_file jamsession "$BIN_DIR/jamsession" 755
install_file adapters/_jamsession_adapter_common "$ADAPTER_DIR/_jamsession_adapter_common" 644
for provider in $PROVIDERS; do
  install_file "adapters/jamsession_$provider" "$ADAPTER_DIR/jamsession_$provider" 755
done
install_file packs/jamon.tsv "$PACK_DIR/jamon.tsv" 644
for skill in $skills; do
  mkdir -p "$SKILL_ROOT/$skill"
  install_file "skills/$skill/SKILL.md" "$SKILL_ROOT/$skill/SKILL.md" 644
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
echo "Run: jamsession doctor" >&2
