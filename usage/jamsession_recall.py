#!/usr/bin/env python3
"""Search agent transcripts for exact lines, and keep a worksheet's session log.

`recall` reads a provider's own transcript (located through the adapter's
`which` command) and prints exact matching lines with their entry numbers, so a
fresh session can copy what it needs instead of trusting a summary. `log`
appends one run or message to the worksheet's "## Jam Session log" section, which
`recall --worksheet` reads to search every session that worked on the task.
"""

import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

LOG_HEADING = "## Jam Session log"
LOG_ENTRY = re.compile(r"^- (\S+ \S+) (run|message|steer) (\S+) (\S+)(?: (.*))?$")
TEXT_LIMIT = 4000
LINE_LIMIT = 400
ENTRY_LIMIT = 6000
NOISE_KEYS = {"encrypted_content", "signature", "data", "usage", "token_usage", "id",
              "uuid", "parentUuid", "timestamp", "requestId", "cache_control"}


def die(message, code=2):
    print(f"jamsession recall: {message}", file=sys.stderr)
    sys.exit(code)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in NOISE_KEYS:
                yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def joined(value):
    return "\n".join(text for text in strings(value) if text.strip())


def tool_text(name, arguments):
    if not isinstance(arguments, dict):
        return "\n".join(filter(None, [name, joined(arguments)]))
    lines = [name]
    for key, value in arguments.items():
        lines.append(f"{key}: {value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines)


def claude_entries(record):
    if record.get("type") not in ("user", "assistant"):
        return
    message = record.get("message") or {}
    role = message.get("role") or record["type"]
    content = message.get("content")
    if isinstance(content, str):
        yield role, content
        return
    for block in content or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            yield role, block.get("text", "")
        elif kind == "tool_use":
            yield "tool-call", tool_text(block.get("name", ""), block.get("input"))
        elif kind == "tool_result":
            yield "tool-result", joined(block.get("content"))


def codex_entries(record):
    payload = record.get("payload") or {}
    kind = payload.get("type")
    if record.get("type") != "response_item":
        return
    if kind == "message":
        yield payload.get("role", "message"), joined(payload.get("content"))
    elif kind == "agent_message":
        yield f"agent {payload.get('author', '')}->{payload.get('recipient', '')}", joined(payload.get("content"))
    elif kind in ("function_call", "custom_tool_call", "local_shell_call"):
        arguments = payload.get("arguments") or payload.get("input") or payload.get("action")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                pass
        yield "tool-call", tool_text(payload.get("name", ""), arguments)
    elif kind in ("function_call_output", "custom_tool_call_output"):
        yield "tool-result", joined(payload.get("output"))


def generic_entries(record):
    role = "entry"
    for key in ("role", "type", "kind", "event"):
        if isinstance(record.get(key), str):
            role = record[key]
            break
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("role"), str):
        role = message["role"]
    yield role, joined(record)


def jsonl_entries(path, provider):
    reader = {"claude": claude_entries, "codex": codex_entries}.get(provider, generic_entries)
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                yield "text", line
                continue
            if isinstance(record, dict):
                for role, text in reader(record):
                    if text and text.strip():
                        yield role, text


def devin_entries(path, session):
    uri = f"file:{path}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5)
    except sqlite3.Error as error:
        die(f"cannot open Devin database read-only: {error}")
    query = ("WITH RECURSIVE chain(node_id) AS (SELECT main_chain_id FROM sessions WHERE id = ? "
             "UNION ALL SELECT m.parent_node_id FROM message_nodes m JOIN chain c ON m.node_id = c.node_id "
             "WHERE m.session_id = ? AND m.parent_node_id IS NOT NULL) "
             "SELECT chat_message FROM message_nodes WHERE session_id = ? "
             "AND node_id IN (SELECT node_id FROM chain) ORDER BY node_id")
    try:
        rows = connection.execute(query, (session, session, session)).fetchall()
    except sqlite3.Error as error:
        die(f"cannot read Devin session {session}: {error}")
    finally:
        connection.close()
    for (raw,) in rows:
        try:
            message = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            yield "entry", str(raw)
            continue
        role = message.get("role", "entry") if isinstance(message, dict) else "entry"
        content = message.get("content") if isinstance(message, dict) else message
        text = joined(content)
        for call in (message.get("tool_calls") or []) if isinstance(message, dict) else []:
            function = call.get("function", call) if isinstance(call, dict) else {}
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    pass
            text = "\n".join(filter(None, [text, tool_text(function.get("name", ""), arguments)]))
        if text.strip():
            yield role, text


def locate(provider, session):
    cli = os.environ.get("JAMSESSION_CLI") or str(Path(__file__).resolve().parent / "jamsession")
    reply = subprocess.run([cli, "which", provider, session], capture_output=True, text=True)
    if reply.returncode != 0:
        die((reply.stderr or reply.stdout).strip() or f"cannot locate {provider} session {session}")
    fields = {}
    for line in reply.stdout.splitlines():
        key, _, value = line.partition(": ")
        fields.setdefault(key, value)
    return fields.get("path", ""), fields.get("format", "")


def entries(provider, session):
    path, kind = locate(provider, session)
    if not path or not Path(path).is_file():
        die(f"no transcript file for {provider} session {session}")
    if provider == "devin":
        source = devin_entries(path, session)
    elif kind.startswith("JSONL"):
        source = jsonl_entries(path, provider)
    else:
        die(f"{provider} stores transcripts as {kind or 'an unknown format'}; recall reads JSONL and Devin only. "
            f"See `jamsession which {provider} {session}`.", 3)
    return [(index, role, text) for index, (role, text) in enumerate(source, 1)]


def clip(line, limit=LINE_LIMIT):
    return line if len(line) <= limit else line[:limit] + f" …[{len(line) - limit} more chars]"


def search(found, matches, around, limit, role_filter):
    hits = 0
    for index, role, text in found:
        if role_filter and not role.startswith(role_filter):
            continue
        lines = text.splitlines()
        shown_to = -1
        for number, line in enumerate(lines):
            if not matches(line):
                continue
            hits += 1
            if hits > limit:
                continue
            start = max(number - around, shown_to + 1)
            if shown_to < 0 or start > shown_to + 1:
                print(f"[#{index} {role}]")
            for context in range(start, min(number + around, len(lines) - 1) + 1):
                print(("> " if context == number else "  ") + clip(lines[context]))
            shown_to = min(number + around, len(lines) - 1)
    if hits > limit:
        print(f"... {hits - limit} more matching lines; narrow the query or raise --max")
    return hits


def show(found, first, last):
    for index, role, text in found:
        if first <= index <= last:
            print(f"[#{index} {role}]")
            print(clip(text, ENTRY_LIMIT))


def worksheet_sessions(path):
    sessions = []
    for line in read_log(path):
        match = LOG_ENTRY.match(line)
        if match and (match[3], match[4]) not in sessions:
            sessions.append((match[3], match[4]))
    return sessions


def read_log(path):
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as error:
        die(f"cannot read worksheet: {error}")
    inside = False
    for line in lines:
        if line.strip() == LOG_HEADING:
            inside = True
        elif inside and line.startswith("## "):
            inside = False
        elif inside:
            yield line


def recall(args):
    if args.worksheet:
        targets = worksheet_sessions(args.worksheet)
        if not targets:
            die(f"no sessions are logged in {args.worksheet}; launch with `jamsession run --worksheet`")
        if args.sessions:
            for provider, session in targets:
                print(f"{provider} {session}")
            return 0
    else:
        if not args.provider or not args.session:
            die("recall needs <provider> <session> or --worksheet <path>")
        targets = [(args.provider, args.session)]
    if args.query is None and args.entry is None and args.tail is None:
        die("recall needs a query, --entry <n> or --tail <n>")
    loaded = [(provider, session, entries(provider, session)) for provider, session in targets]
    if args.entry is not None or args.tail is not None:
        for provider, session, found in loaded:
            print(f"== {provider} {session} ({len(found)} entries)")
            if args.entry is not None:
                show(found, args.entry - args.around, args.entry + args.around)
            else:
                show(found, len(found) - args.tail + 1, len(found))
        return 0
    words = args.query.lower().split()
    if args.regex:
        try:
            pattern = re.compile(args.query, re.IGNORECASE)
        except re.error as error:
            die(f"invalid --regex pattern: {error}")
        passes = [("", pattern.search)]
    else:
        need = max(1, (len(words) + 1) // 2)
        passes = [("", lambda line: all(word in line.lower() for word in words))]
        if len(words) > 1:
            passes.append((f"no line has every word; lines with at least {need} of the {len(words)} words:",
                           lambda line: sum(word in line.lower() for word in words) >= need))
    for note, matches in passes:
        if note:
            print(note)
        total = 0
        for provider, session, found in loaded:
            print(f"== {provider} {session} ({len(found)} entries)")
            total += search(found, matches, args.around, args.max, args.role)
        if total:
            return 0
    print("no matches")
    return 1


def log(args):
    path = Path(args.worksheet)
    if not path.is_file():
        die(f"worksheet not found: {path}")
    text = sys.stdin.read() if args.text_stdin else ""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = [f"- {stamp} {args.kind} {args.provider} {args.session}" + (f" {args.detail}" if args.detail else "")]
    if text.strip():
        body = text.rstrip("\n")
        if len(body) > TEXT_LIMIT:
            body = body[:TEXT_LIMIT] + f"\n[{len(body) - TEXT_LIMIT} more chars; the full text is in the session transcript]"
        entry += ["  > " + line if line else "  >" for line in body.splitlines()]
    with open(path, "r+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        lines = handle.read().splitlines()
        heading = next((number for number, line in enumerate(lines) if line.strip() == LOG_HEADING), None)
        if heading is None:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += ["", LOG_HEADING, ""] + entry
        else:
            end = next((number for number in range(heading + 1, len(lines)) if lines[number].startswith("## ")), len(lines))
            insert = end
            while insert > heading + 1 and not lines[insert - 1].strip():
                insert -= 1
            lines[insert:insert] = entry + ([""] if end < len(lines) and insert == end else [])
        handle.seek(0)
        handle.write("\n".join(lines) + "\n")
        handle.truncate()
    return 0


def main():
    parser = argparse.ArgumentParser(prog="jamsession recall", description=__doc__.splitlines()[0])
    if len(sys.argv) > 1 and sys.argv[1] == "log":
        parser.add_argument("command")
        parser.add_argument("worksheet")
        parser.add_argument("kind", choices=["run", "message", "steer"])
        parser.add_argument("provider")
        parser.add_argument("session")
        parser.add_argument("--detail", default="")
        parser.add_argument("--text-stdin", action="store_true")
        return log(parser.parse_args())
    parser.add_argument("targets", nargs="*", help="<provider> <session> [query], or [query] with --worksheet")
    parser.add_argument("--worksheet")
    parser.add_argument("--sessions", action="store_true", help="list the worksheet's logged sessions")
    parser.add_argument("--regex", action="store_true", help="treat the query as a regular expression")
    parser.add_argument("--around", type=int, default=2, help="context lines, or entries with --entry")
    parser.add_argument("--max", type=int, default=30, help="most matching lines to print per session")
    parser.add_argument("--role", help="only entries whose role starts with this, such as user or tool-result")
    parser.add_argument("--entry", type=int, help="print entry N in full with --around entries either side")
    parser.add_argument("--tail", type=int, help="print the last N entries in full")
    args = parser.parse_intermixed_args()
    positional = list(args.targets)
    args.provider = args.session = None
    if not args.worksheet:
        if len(positional) < 2:
            die("recall needs <provider> <session> [query] or --worksheet <path> [query]")
        args.provider, args.session = positional[0], positional[1]
        positional = positional[2:]
    if len(positional) > 1:
        die("quote a query that contains spaces")
    args.query = positional[0] if positional else None
    if args.around < 0 or args.max < 1 or (args.tail is not None and args.tail < 1):
        die("--around must be 0 or more; --max and --tail must be positive")
    return recall(args)


if __name__ == "__main__":
    sys.exit(main())
