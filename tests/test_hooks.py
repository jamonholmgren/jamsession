"""Inbox hook: merge-only install, refusal when unwired, one per-user inbox, fork-versus-parent delivery, silent no-op."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Launches must never start a real background usage refresh.
os.environ["JAMSESSION_USAGE_REFRESH"] = "0"

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
        inbox = self.home / ".agents" / "jamsession" / "inbox"
        return sorted(inbox.glob("agent-note-*.txt")) if inbox.is_dir() else []

    def hook(self, session, transcript=None, **extra):
        payload = {"session_id": session, "cwd": str(self.project), "hook_event_name": "PostToolUse", **extra}
        if transcript is not None:
            payload["transcript_path"] = str(transcript)
        result = self.run_cli(command=["python3", HELPER, "run"], cwd=self.project, stdin=json.dumps(payload))
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] if result.stdout else ""

    def use_cli_on_path(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        if not (bin_dir / "jamsession").exists():
            (bin_dir / "jamsession").symlink_to(CLI)
        self.env["PATH"] = f"{bin_dir}:{self.env['PATH']}"

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
        self.assertFalse((self.project / ".agents").exists())
        self.use_cli_on_path()
        payload = json.dumps({"session_id": SESSION, "cwd": str(self.project / "sub"), "hook_event_name": "PostToolUse"})
        hook = self.run_cli(command=["python3", HELPER, "run"], cwd=self.project / "sub", stdin=payload)
        self.assertEqual(hook.returncode, 0)
        self.assertIn("PELICAN", json.loads(hook.stdout)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.notes(), [])

    def test_install_replaces_legacy_project_inbox_wiring(self):
        settings = self.project / ".claude" / "settings.json"
        settings.parent.mkdir()
        legacy = {"type": "command", "command": 'python3 "${CLAUDE_PROJECT_DIR}/hooks/jamsession_inbox.py"'}
        other = {"matcher": "Edit", "hooks": [{"type": "command", "command": "true"}]}
        settings.write_text(json.dumps({"hooks": {"PostToolUse": [other, {"hooks": [legacy]}]}}))
        # The old hook reads <project>/.agents/jamsession/inbox, which no longer gets notes.
        self.assertEqual(self.run_cli("message", "claude", SESSION, "hello").returncode, 3)
        self.assertEqual(self.notes(), [])
        for _ in range(2):
            self.assertEqual(self.run_cli("hooks", "install", str(self.project)).returncode, 0)
        groups = json.loads(settings.read_text())["hooks"]["PostToolUse"]
        commands = [h["command"] for g in groups for h in g["hooks"]]
        self.assertEqual(groups[0], other)
        self.assertEqual(len(groups), 2)
        self.assertFalse(any("jamsession_inbox" in c for c in commands))
        self.assertEqual(self.run_cli("message", "claude", SESSION, "hello").returncode, 0)

    def test_inbox_path_is_fixed_under_home_whatever_the_working_directory(self):
        for cwd in (self.project / "sub", self.sender, self.root):
            result = self.run_cli("inbox", SESSION, "write", "tester", f"from {cwd.name}", cwd=cwd)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(result.stdout.strip()).parent, self.home / ".agents" / "jamsession" / "inbox")
        self.assertEqual(len(self.notes()), 3)
        self.assertFalse((self.project / ".agents").exists())

    def test_label_and_unknown_recipients_are_refused_and_nothing_is_queued(self):
        for recipient in ("perf-team-lead", "99999999-0000-4000-8000-000000000000"):
            result = self.run_cli("inbox", recipient, "write", "tester", "hello")
            self.assertEqual(result.returncode, 2)
            self.assertIn("not a session ID", result.stderr)
        self.assertEqual(self.notes(), [])
        self.assertNotEqual(self.run_cli("message", "claude", "perf-team-lead", "hello").returncode, 0)
        self.assertEqual(self.notes(), [])

    def test_fork_and_parent_each_receive_only_their_own_notes(self):
        parent, fork = SESSION, "99999999-8888-7777-6666-555555555555"
        transcripts = self.home / ".claude" / "projects" / "-recipient"
        copied = [{"type": "user", "sessionId": parent, "cwd": str(self.project)},
                  {"type": "custom-title", "sessionId": parent, "customTitle": "Performance"}]
        own = [{"type": "custom-title", "sessionId": fork, "customTitle": "Side chat"},
               {"type": "user", "sessionId": fork, "cwd": str(self.project)}]
        (transcripts / f"{parent}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in copied))
        (transcripts / f"{fork}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in copied + own))
        self.assertEqual(self.run_cli("hooks", "install", str(self.project)).returncode, 0)
        self.use_cli_on_path()

        # Writing straight to the inbox names the fork too, so a sender sees the mix-up.
        direct = self.run_cli("inbox", fork, "write", "tester", "direct to the side chat")
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertIn("('Side chat'), a fork of " + parent + " ('Performance')", direct.stderr)
        self.assertIn("direct to the side chat", self.hook(fork, transcripts / f"{fork}.jsonl"))

        to_fork = self.run_cli("message", "claude", fork, "for the side chat")
        self.assertEqual(to_fork.returncode, 0, to_fork.stderr)
        self.assertIn("('Side chat'), a fork of " + parent + " ('Performance')", to_fork.stderr)
        self.assertEqual(self.run_cli("message", "claude", parent, "for performance").returncode, 0)

        # A payload naming the parent but carrying the fork's transcript is not the parent.
        self.assertEqual(self.hook(parent, transcripts / f"{fork}.jsonl"), "")
        fork_context = self.hook(fork, transcripts / f"{fork}.jsonl")
        self.assertIn("for the side chat", fork_context)
        self.assertNotIn("for performance", fork_context)
        parent_context = self.hook(parent, transcripts / f"{parent}.jsonl")
        self.assertIn("for performance", parent_context)
        self.assertNotIn("for the side chat", parent_context)
        self.assertEqual(self.notes(), [])

    def test_subagent_tool_calls_leave_the_note_for_the_parent(self):
        self.assertEqual(self.run_cli("hooks", "install", str(self.project)).returncode, 0)
        self.assertEqual(self.run_cli("message", "claude", SESSION, "for the parent").returncode, 0)
        self.use_cli_on_path()
        self.assertEqual(self.hook(SESSION, agent_id="a1"), "")
        self.assertEqual(len(self.notes()), 1)

    def test_hook_accepts_a_transcript_kept_in_a_folder_named_for_the_session(self):
        self.use_cli_on_path()
        self.assertEqual(self.run_cli("inbox", SESSION, "write", "tester", "grok-shaped").returncode, 0)
        grok_path = self.home / ".grok" / "sessions" / "%2Frecipient" / SESSION / "messages.jsonl"
        self.assertIn("grok-shaped", self.hook(SESSION, grok_path))

    def test_hook_is_silent_without_notes_helper_or_valid_payload(self):
        installed = 'f="$HOME/.agents/jamsession/bin/jamsession_hooks.py"; [ ! -f "$f" ] || python3 "$f" run; exit 0'
        for command, stdin in ((["sh", "-c", installed], "{}"), (["python3", HELPER, "run"], "not json"),
                               (["python3", HELPER, "run"], json.dumps({"session_id": SESSION, "cwd": str(self.project)}))):
            result = self.run_cli(command=command, cwd=self.project, stdin=stdin)
            self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
