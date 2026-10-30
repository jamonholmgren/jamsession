"""Transcript recall and worksheet session logs through the public CLI, without real agent calls."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SESSION = "11111111-2222-4333-8444-555555555555"
CODEX_SESSION = "01a1aaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee"


def claude_record(role, content):
    return {"type": role, "message": {"role": role, "content": content}}


class RecallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jamsession-recall-test-")
        self.home = Path(self.temp.name)
        config = self.home / "config"
        config.write_text("")
        self.env = dict(os.environ, HOME=str(self.home), JAMSESSION_CONFIG=str(config), JAMSESSION_CWD=str(self.home))
        for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR", "CODEX_HOME"):
            self.env.pop(name, None)
        claude = self.home / ".claude/projects/project" / f"{CLAUDE_SESSION}.jsonl"
        claude.parent.mkdir(parents=True)
        records = [
            claude_record("user", "Keep the door code; Jamon will re-add it."),
            claude_record("assistant", [{"type": "thinking", "thinking": "secret reasoning", "signature": "abc"},
                                        {"type": "text", "text": "Running the focused test."},
                                        {"type": "tool_use", "name": "Bash", "input": {"command": "./start --run-test=TestDoor --headless", "description": "Run door test"}}]),
            claude_record("user", [{"type": "tool_result", "content": "line one\nSCRIPT ERROR: Parse Error: Identifier \"flown\" not declared\nline three"}]),
            {"type": "summary", "summary": "ignored"},
            claude_record("assistant", "Fixed it (exit 0)."),
        ]
        claude.write_text("\n".join(json.dumps(record) for record in records) + "\n")
        codex = self.home / ".codex/sessions/2026/10/29" / f"rollout-2026-10-29T01-02-03-{CODEX_SESSION}.jsonl"
        codex.parent.mkdir(parents=True)
        codex_records = [
            {"type": "session_meta", "payload": {"id": CODEX_SESSION}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Use the Agent3 checkout."}]}},
            {"type": "response_item", "payload": {"type": "reasoning", "encrypted_content": "Agent3 hidden"}},
            {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": "git -C /x/Agent3 status"})}},
            {"type": "response_item", "payload": {"type": "function_call_output", "output": "nothing to commit"}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {"Agent3": 1}}},
        ]
        codex.write_text("\n".join(json.dumps(record) for record in codex_records) + "\n")

    def tearDown(self):
        self.temp.cleanup()

    def jam(self, *args, stdin=None):
        return subprocess.run([str(ROOT / "jamsession"), *args], env=self.env, input=stdin,
                              capture_output=True, text=True, timeout=30)

    def test_claude_recall_prints_exact_lines_with_entry_and_role(self):
        reply = self.jam("recall", "claude", CLAUDE_SESSION, "parse error: identifier")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("[#4 tool-result]", reply.stdout)
        self.assertIn('> SCRIPT ERROR: Parse Error: Identifier "flown" not declared', reply.stdout)
        self.assertIn("  line one", reply.stdout)
        reply = self.jam("recall", "claude", CLAUDE_SESSION, "--role", "tool-call", "--", "--run-test=TestDoor")
        self.assertIn("> command: ./start --run-test=TestDoor --headless", reply.stdout)
        self.assertEqual(self.jam("recall", "claude", CLAUDE_SESSION, "secret reasoning").returncode, 1)
        self.assertEqual(self.jam("recall", "claude", CLAUDE_SESSION, "ignored").returncode, 1)

    def test_entry_tail_regex_and_max(self):
        reply = self.jam("recall", "claude", CLAUDE_SESSION, "--entry", "1", "--around", "0")
        self.assertEqual(reply.stdout.splitlines()[1:], ["[#1 user]", "Keep the door code; Jamon will re-add it."])
        reply = self.jam("recall", "claude", CLAUDE_SESSION, "--tail", "1")
        self.assertIn("[#5 assistant]\nFixed it (exit 0).", reply.stdout)
        reply = self.jam("recall", "claude", CLAUDE_SESSION, r"exit \d", "--regex")
        self.assertIn("> Fixed it (exit 0).", reply.stdout)
        reply = self.jam("recall", "claude", CLAUDE_SESSION, "line", "--max", "1", "--around", "0")
        self.assertIn("more matching lines", reply.stdout)

    def test_query_words_match_in_any_order_then_fall_back_to_closest_lines(self):
        reply = self.jam("recall", "claude", CLAUDE_SESSION, "jamon door", "--around", "0")
        self.assertIn("> Keep the door code; Jamon will re-add it.", reply.stdout)
        self.assertNotIn("no line has every word", reply.stdout)
        reply = self.jam("recall", "claude", CLAUDE_SESSION, "door code rules", "--around", "0")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("no line has every word; lines with at least 2 of the 3 words:", reply.stdout)
        self.assertIn("> Keep the door code; Jamon will re-add it.", reply.stdout)
        self.assertEqual(self.jam("recall", "claude", CLAUDE_SESSION, "zebra quartz").returncode, 1)

    def test_codex_recall_skips_reasoning_and_token_events(self):
        reply = self.jam("recall", "codex", CODEX_SESSION, "agent3", "--around", "0")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("[#1 user]\n> Use the Agent3 checkout.", reply.stdout)
        self.assertIn("[#2 tool-call]\n> cmd: git -C /x/Agent3 status", reply.stdout)
        self.assertNotIn("hidden", reply.stdout)
        self.assertEqual(reply.stdout.count("> "), 2)

    def test_unknown_session_and_bad_arguments_fail_clearly(self):
        reply = self.jam("recall", "claude", "missing-session", "x")
        self.assertNotEqual(reply.returncode, 0)
        self.assertIn("was not found", reply.stderr)
        self.assertEqual(self.jam("recall", "claude", CLAUDE_SESSION).returncode, 2)
        self.assertEqual(self.jam("recall", "claude", CLAUDE_SESSION, "two", "words").returncode, 2)

    def fake_claude(self):
        binary = self.home / "claude"
        binary.write_text("#!" + sys.executable + "\nimport sys\nprint('[]' if sys.argv[1:2] == ['agents'] else 'done')\n")
        binary.chmod(0o755)
        self.env["JAMSESSION_CLAUDE_BIN"] = str(binary)

    def test_worksheet_logs_runs_and_messages_inside_its_section(self):
        self.fake_claude()
        worksheet = self.home / "worksheet.md"
        worksheet.write_text("# Task\n\nStatus: ACTIVE\n")
        reply = self.jam("run", "--worksheet", str(worksheet), "claude", "new", "haiku-5.5", "low", "edit", "First line\nSecond line")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(reply.stdout, "done\n")
        session = re.search(r"^session: (\S+)$", reply.stderr, re.MULTILINE)[1]
        text = worksheet.read_text()
        self.assertIn(f"## Jam Session log\n\n- ", text)
        self.assertRegex(text, rf"- \S+ \S+ run claude {session} new haiku-5.5 low edit in {re.escape(str(self.home))}\n  > First line\n  > Second line\n")
        worksheet.write_text(worksheet.read_text() + "\n## Handoff\n\nNext steps.\n")
        reply = self.jam("message", "--worksheet", str(worksheet), "claude", session, "-", "--resume-with", "default", "low", "read", stdin="Stop and report.\n")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        text = worksheet.read_text()
        log, handoff = text.split("## Handoff")
        self.assertRegex(log, rf"message claude {session}\n  > Stop and report.\n\n$")
        self.assertEqual(handoff, "\n\nNext steps.\n")
        reply = self.jam("recall", "--worksheet", str(worksheet), "--sessions")
        self.assertEqual(reply.stdout, f"claude {session}\n")

    def test_worksheet_recall_searches_every_logged_session(self):
        worksheet = self.home / "worksheet.md"
        worksheet.write_text(f"# Task\n\n## Jam Session log\n\n- 2026-10-29 01:00 run claude {CLAUDE_SESSION} new\n"
                             f"- 2026-10-29 02:00 run codex {CODEX_SESSION} new\n  > Agent3 prompt\n")
        reply = self.jam("recall", "--worksheet", str(worksheet), "checkout|door code", "--regex", "--around", "0")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertLess(reply.stdout.index(f"== claude {CLAUDE_SESSION}"), reply.stdout.index(f"== codex {CODEX_SESSION}"))
        self.assertIn("> Keep the door code; Jamon will re-add it.", reply.stdout)
        self.assertIn("> Use the Agent3 checkout.", reply.stdout)

    def test_missing_worksheet_stops_before_the_agent_runs(self):
        self.fake_claude()
        reply = self.jam("run", "--worksheet", str(self.home / "missing.md"), "claude", "new", "default", "low", "edit", "x")
        self.assertEqual(reply.returncode, 2)
        self.assertIn("worksheet not found", reply.stderr)
        self.assertNotIn("done", reply.stdout)


if __name__ == "__main__":
    unittest.main()
