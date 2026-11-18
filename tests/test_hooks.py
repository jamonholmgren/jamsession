"""Inbox hook: merge-only install, refusal when unwired, delivery to the recipient's project, silent no-op."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / "jamsession")
HELPER = str(ROOT / "usage" / "jamsession_hooks.py")
SESSION = "11111111-2222-3333-4444-555555555555"


class HookHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jamsession-hooks-test-")
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.project = self.root / "recipient"
        self.sender = self.root / "sender"
        for path in (self.home, self.project / ".git", self.sender / ".git"):
            path.mkdir(parents=True)
        transcripts = self.home / ".claude" / "projects" / "-recipient"
        transcripts.mkdir(parents=True)
        (transcripts / f"{SESSION}.jsonl").write_text(json.dumps({"type": "user", "cwd": str(self.project / "sub")}) + "\n")
        (self.project / "sub").mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("JAMSESSION_", "CLAUDE_"))}
        self.env.update(HOME=str(self.home), JAMSESSION_CONFIG=str(self.root / "none.conf"),
                        JAMSESSION_ACCOUNTS=str(self.root / "none.toml"),
                        JAMSESSION_SESSION_ACCOUNTS=str(self.root / "none.json"))

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, cwd=None, stdin=None, command=None):
        return subprocess.run(command or [CLI, *args], cwd=cwd or self.sender, env=self.env, input=stdin,
                              capture_output=True, text=True, timeout=30)

    def notes(self):
        inbox = self.project / ".agents" / "jamsession" / "inbox"
        return sorted(inbox.glob("agent-note-*.txt")) if inbox.is_dir() else []

    def test_install_merges_existing_settings_and_is_idempotent(self):
        settings = self.project / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "true"}]}],
                                                                "PostToolUse": [{"matcher": "Edit", "hooks": []}]}}))
        (self.home / ".grok").mkdir()
        for _ in range(2):
            self.assertEqual(self.run_cli("hooks", "install", str(self.project)).returncode, 0)
        data = json.loads(settings.read_text())
        self.assertEqual(data["model"], "x")
        self.assertEqual(len(data["hooks"]["Stop"]), 1)
        self.assertEqual(len(data["hooks"]["PostToolUse"]), 2)
        self.assertTrue((self.home / ".grok" / "hooks" / "jamsession-inbox.json").is_file())
        self.assertEqual(self.run_cli("hooks", "check", str(self.project)).returncode, 0)

    def test_install_refuses_invalid_settings_without_changing_them(self):
        settings = self.project / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text("{not json")
        self.assertNotEqual(self.run_cli("hooks", "install", str(self.project)).returncode, 0)
        self.assertEqual(settings.read_text(), "{not json")

    def test_message_to_unwired_project_is_refused_and_writes_nothing(self):
        result = self.run_cli("message", "claude", SESSION, "hello")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(self.notes(), [])

    def test_message_lands_in_the_recipients_project_and_the_hook_delivers_it(self):
        self.assertEqual(self.run_cli("hooks", "install", str(self.project)).returncode, 0)
        result = self.run_cli("message", "claude", SESSION, "the codeword is PELICAN")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.notes()), 1)
        self.assertFalse((self.sender / ".agents").exists())
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "jamsession").symlink_to(CLI)
        self.env["PATH"] = f"{bin_dir}:{self.env['PATH']}"
        payload = json.dumps({"session_id": SESSION, "cwd": str(self.project / "sub"), "hook_event_name": "PostToolUse"})
        hook = self.run_cli(command=["python3", HELPER, "run"], cwd=self.project / "sub", stdin=payload)
        self.assertEqual(hook.returncode, 0)
        self.assertIn("PELICAN", json.loads(hook.stdout)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.notes(), [])

    def test_legacy_wiring_counts_for_claude_only(self):
        settings = self.project / ".claude" / "settings.json"
        settings.parent.mkdir()
        legacy = {"type": "command", "command": 'python3 "${CLAUDE_PROJECT_DIR}/hooks/jamsession_inbox.py"'}
        settings.write_text(json.dumps({"hooks": {"PostToolUse": [{"hooks": [legacy]}]}}))
        db = self.home / ".local/share/devin/cli/sessions.db"
        db.parent.mkdir(parents=True)
        import sqlite3
        with sqlite3.connect(db) as connection:
            connection.execute("CREATE TABLE sessions (id TEXT, working_directory TEXT)")
            connection.execute("INSERT INTO sessions VALUES ('devin-a', ?)", (str(self.project),))
        self.assertEqual(self.run_cli("message", "devin", "devin-a", "hello").returncode, 3)
        self.assertEqual(self.notes(), [])
        self.assertEqual(self.run_cli("message", "claude", SESSION, "hello").returncode, 0)
        self.run_cli("hooks", "install", str(self.project))
        self.assertEqual(len(json.loads(settings.read_text())["hooks"]["PostToolUse"]), 2)

    def test_subagent_tool_calls_leave_the_note_for_the_parent(self):
        self.assertEqual(self.run_cli("hooks", "install", str(self.project)).returncode, 0)
        self.assertEqual(self.run_cli("message", "claude", SESSION, "for the parent").returncode, 0)
        payload = json.dumps({"session_id": SESSION, "cwd": str(self.project), "agent_id": "a1"})
        result = self.run_cli(command=["python3", HELPER, "run"], cwd=self.project, stdin=payload)
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual(len(self.notes()), 1)

    def test_hook_is_silent_without_notes_helper_or_valid_payload(self):
        installed = 'f="$HOME/.agents/jamsession/bin/jamsession_hooks.py"; [ ! -f "$f" ] || python3 "$f" run; exit 0'
        for command, stdin in ((["sh", "-c", installed], "{}"), (["python3", HELPER, "run"], "not json"),
                               (["python3", HELPER, "run"], json.dumps({"session_id": SESSION, "cwd": str(self.project)}))):
            result = self.run_cli(command=command, cwd=self.project, stdin=stdin)
            self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
