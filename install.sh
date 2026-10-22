#!/bin/sh

set -eu

SOURCE_URL=${JAMSESSION_SOURCE_URL:-https://raw.githubusercontent.com/jamonholmgren/jamsession/main}
INSTALL_ROOT=${JAMSESSION_HOME:-"$HOME/.agents/jamsession"}
SKILL_ROOT=${JAMSESSION_SKILL_DIR:-"$HOME/.agents/skills"}
BIN_DIR="$INSTALL_ROOT/bin"
ADAPTER_DIR="$INSTALL_ROOT/adapters"
LINK_DIR="$HOME/.local/bin"

PROVIDERS="codex claude cursor grok copilot devin muse antigravity"
DEFAULT_SKILLS="jamsession-summon-agent jamsession-get-agent-usage"
OPTIONAL_SKILLS="jamsession-model-recommendations jamsession-ping-pong-planning
jamsession-peasant-mob
jamsession-contrarian-review jamsession-ask-agent-panel
jamsession-orchestrate-agent-work jamsession-use-agent-worksheet
jamsession-run-agent-comparison
jamsession-individual-worker-workflow
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

resource_abort() { abort "$1"; }

# resources.txt is optional for legacy packages. When present, every entry is
# required and must stay within the package's references/ or assets/ trees.
resource_path_safe() {
  case "$1" in references/*|assets/*) ;; *) return 1 ;; esac
  case "$1" in *[!a-zA-Z0-9_./-]*|*/|*//*|*/../*|*/./*|*/..|*/.) return 1 ;; esac
}

resource_no_symlinks() {
  resource_base=$1
  resource_tail=$2
  [ ! -L "$resource_base" ] || resource_abort "symlink package path: $resource_base"
  [ ! -e "$resource_base" ] || [ -d "$resource_base" ] || resource_abort "package parent is not a directory: $resource_base"
  while [ -n "$resource_tail" ]; do
    resource_part=${resource_tail%%/*}
    resource_base="$resource_base/$resource_part"
    [ ! -L "$resource_base" ] || resource_abort "symlink package path: $resource_base"
    case "$resource_tail" in
      */*)
        [ ! -e "$resource_base" ] || [ -d "$resource_base" ] || resource_abort "package parent is not a directory: $resource_base"
        resource_tail=${resource_tail#*/} ;;
      *)
        [ ! -e "$resource_base" ] || [ -f "$resource_base" ] || resource_abort "package destination is not a file: $resource_base"
        break ;;
    esac
  done
}

stage_skill_resources() {
  resource_source=$1
  resource_stage=$2
  resource_target=$3
  resource_skill=$4
  mkdir -p "$resource_stage" || resource_abort "could not stage resources"
  resource_no_symlinks "$resource_target" resources.txt
  [ ! -e "$resource_target/resources.txt" ] || [ -f "$resource_target/resources.txt" ] || resource_abort "resource manifest destination is not a file"
  case "$resource_source" in
    file://*) resource_no_symlinks "${resource_source#file://}" resources.txt ;;
  esac
  resource_status=0
  resource_http=$(curl -fsSL -w '%{http_code}' "$resource_source/resources.txt" \
    -o "$resource_stage/resources.txt" 2>"$resource_stage/resource-download-error") || resource_status=$?
  if [ "$resource_status" -ne 0 ]; then
    resource_absent=false
    [ "$resource_http" != 404 ] || resource_absent=true
    case "$resource_source" in
      file://*)
        if [ "$resource_status" -eq 37 ] && [ ! -e "${resource_source#file://}/resources.txt" ]; then resource_absent=true; fi ;;
    esac
    if [ "$resource_absent" = true ]; then
      if grep -Eq '\]\((\./)?(references|assets)/|^\[[^]]+\]:[[:space:]]*(\./)?(references|assets)/' "$resource_skill"; then
        resource_abort "skill links bundled resources but resources.txt is missing: $resource_source"
      fi
      rm -f "$resource_stage/resources.txt" "$resource_stage/resource-download-error"
      return 0
    fi
    resource_abort "could not download resource manifest: $resource_source"
  fi
  rm -f "$resource_stage/resource-download-error"
  [ -s "$resource_stage/resources.txt" ] || resource_abort "empty resource manifest: $resource_source"
  resource_seen='|'
  while IFS= read -r resource_entry || [ -n "$resource_entry" ]; do
    resource_path_safe "$resource_entry" || resource_abort "unsafe resource path: $resource_entry"
    case "$resource_seen" in *"|$resource_entry|"*) resource_abort "duplicate resource: $resource_entry" ;; esac
    resource_seen="$resource_seen$resource_entry|"
    resource_no_symlinks "$resource_target" "$resource_entry"
    resource_no_symlinks "$resource_target" "$resource_entry.jamsession-new"
    [ ! -e "$resource_target/$resource_entry" ] || [ -f "$resource_target/$resource_entry" ] || resource_abort "resource destination is not a file: $resource_entry"
    [ ! -e "$resource_target/$resource_entry.jamsession-new" ] || [ -f "$resource_target/$resource_entry.jamsession-new" ] || resource_abort "resource staging destination is not a file: $resource_entry"
    case "$resource_source" in
      file://*) resource_no_symlinks "${resource_source#file://}" "$resource_entry" ;;
    esac
    mkdir -p "$resource_stage/$(dirname "$resource_entry")" || resource_abort "could not stage resource: $resource_entry"
    curl -fsSL "$resource_source/$resource_entry" -o "$resource_stage/$resource_entry" || \
      resource_abort "could not download required resource: $resource_entry"
    [ -s "$resource_stage/$resource_entry" ] || resource_abort "empty required resource: $resource_entry"
  done < "$resource_stage/resources.txt"
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
fetch usage/jamsession_tui_usage.py usage/jamsession_tui_usage.py
fetch adapters/_jamsession_adapter_common adapters/_jamsession_adapter_common
fetch adapters/_jamsession_devin_acp.py adapters/_jamsession_devin_acp.py
fetch adapters/_jamsession_codex_control.py adapters/_jamsession_codex_control.py
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
  resource_no_symlinks "$SKILL_ROOT/$skill" SKILL.md
  resource_no_symlinks "$SKILL_ROOT/$skill" agents/openai.yaml
  resource_no_symlinks "$SKILL_ROOT/$skill" resources.txt.jamsession-new
  stage_skill_resources "$SOURCE_URL/skills/$skill" "$STAGE/skills/$skill" "$SKILL_ROOT/$skill" "$STAGE/skills/$skill/SKILL.md"
done
require_script jamsession
require_script usage/jamsession_usage
require_script usage/jamsession_tui_usage.py
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
install_file usage/jamsession_tui_usage.py "$BIN_DIR/jamsession_tui_usage.py" 755
install_file adapters/_jamsession_adapter_common "$ADAPTER_DIR/_jamsession_adapter_common" 644
install_file adapters/_jamsession_devin_acp.py "$ADAPTER_DIR/_jamsession_devin_acp.py" 644
install_file adapters/_jamsession_codex_control.py "$ADAPTER_DIR/_jamsession_codex_control.py" 644
for provider in $PROVIDERS; do
  install_file "adapters/jamsession_$provider" "$ADAPTER_DIR/jamsession_$provider" 755
done
for skill in $skills; do
  mkdir -p "$SKILL_ROOT/$skill/agents"
  install_file "skills/$skill/SKILL.md" "$SKILL_ROOT/$skill/SKILL.md" 644
  install_file "skills/$skill/agents/openai.yaml" "$SKILL_ROOT/$skill/agents/openai.yaml" 644
  if [ -f "$STAGE/skills/$skill/resources.txt" ]; then
    while IFS= read -r resource_entry || [ -n "$resource_entry" ]; do
      mkdir -p "$SKILL_ROOT/$skill/$(dirname "$resource_entry")"
      install_file "skills/$skill/$resource_entry" "$SKILL_ROOT/$skill/$resource_entry" 644
    done < "$STAGE/skills/$skill/resources.txt"
    install_file "skills/$skill/resources.txt" "$SKILL_ROOT/$skill/resources.txt" 644
  fi
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
