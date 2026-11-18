"""Named provider accounts through the public CLI, with fake adapters and usage fixtures."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]

FAKE_ADAPTER = """#!/bin/sh
printf '%s %s\\n' "$1" "${TEST_ACCOUNT_MARKER:-none}" >>"$ACCOUNT_LOG"
case "$1" in
  run)
    printf 'session: sess-%s\\n' "${TEST_ACCOUNT_MARKER:-none}" >&2
    ;;
  message|steer) ;;
  *) printf 'unexpected %s\\n' "$1" >&2; exit 99 ;;
esac
printf 'MARKER=%s\\n' "${TEST_ACCOUNT_MARKER:-none}"
printf 'CLAUDE_CONFIG_DIR=%s\\n' "${CLAUDE_CONFIG_DIR:-}"
printf 'CODEX_HOME=%s\\n' "${CODEX_HOME:-}"
"""


def claude_record(text):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": text}}) + "\n"


class AccountCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jamsession-accounts-test-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.log = self.root / "launches"
        self.sessions = self.root / "session-accounts.json"
        self.accounts_path = self.root / "accounts.toml"
        self.config = self.root / "jamsession.conf"
        self.config.write_text("")
        adapters = self.root / "adapters"
        adapters.mkdir()
        for name in ("claude", "codex"):
            adapter = adapters / f"jamsession_{name}"
            adapter.write_text(FAKE_ADAPTER)
            adapter.chmod(0o755)
        self.personal_dir = self.root / "personal-claude"
        self.env = os.environ.copy()
        for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR", "JAMSESSION_CLAUDE_ACCOUNT",
                     "JAMSESSION_CODEX_ACCOUNT", "CLAUDE_CONFIG_DIR", "CODEX_HOME",
                     "TEST_ACCOUNT_MARKER", "JAMSESSION_USAGE_JSON", "JAMSESSION_TIERS",
                     "JAMSESSION_USAGE_FIXTURE_DIR", "JAMSESSION_LATEST_CACHE"):
            self.env.pop(name, None)
        self.env.update({
            "HOME": str(self.home),
            "JAMSESSION_CONFIG": str(self.config),
            "JAMSESSION_ADAPTER_DIR": str(adapters),
            "JAMSESSION_ACCOUNTS": str(self.accounts_path),
            "JAMSESSION_SESSION_ACCOUNTS": str(self.sessions),
            "JAMSESSION_CWD": str(self.root),
            "ACCOUNT_LOG": str(self.log),
            "CLAUDE_CONFIG_DIR": "/ambient/claude",
        })

    def tearDown(self):
        self.temp.cleanup()

    def write_accounts(self, text):
        self.accounts_path.write_text(text)

    def jam(self, *args, extra=None):
        env = dict(self.env)
        if extra:
            env.update(extra)
        return subprocess.run([str(ROOT / "jamsession"), *args], env=env,
                              capture_output=True, text=True, timeout=30)

    def launches(self):
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text().splitlines() if line]

    def claude_accounts(self):
        self.write_accounts(
            "[claude.work]\n"
            'env = { CLAUDE_CONFIG_DIR = "~/work-claude", TEST_ACCOUNT_MARKER = "work" }\n'
            "\n"
            "[claude.personal]\n"
            f'env = {{ CLAUDE_CONFIG_DIR = "{self.personal_dir}", TEST_ACCOUNT_MARKER = "personal" }}\n'
            "\n"
            "[codex.work]\n"
            'env = { CODEX_HOME = "~/codex-work", TEST_ACCOUNT_MARKER = "codex-work" }\n'
        )

    def test_an_accounts_env_applies_to_one_run_only(self):
        self.claude_accounts()
        self.assertNotIn("TEST_ACCOUNT_MARKER", os.environ)
        personal = self.jam("run", "claude:personal", "new", "default", "default", "edit", "hi")
        self.assertEqual(personal.returncode, 0, personal.stderr)
        self.assertIn("MARKER=personal", personal.stdout)
        self.assertNotIn("MARKER=work", personal.stdout)
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.personal_dir}", personal.stdout)
        self.assertNotIn("/ambient/claude", personal.stdout)
        self.assertNotIn("TEST_ACCOUNT_MARKER", os.environ)

        work = self.jam("run", "claude:work", "new", "default", "default", "edit", "hi")
        self.assertEqual(work.returncode, 0, work.stderr)
        self.assertIn("MARKER=work", work.stdout)
        self.assertNotIn("MARKER=personal", work.stdout)
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.home / 'work-claude'}", work.stdout)
        self.assertNotIn("~", work.stdout)
        self.assertNotIn("/ambient/claude", work.stdout)

        plain = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertIn("MARKER=work", plain.stdout)

        selected = self.jam("run", "claude", "new", "default", "default", "edit", "hi",
                            extra={"JAMSESSION_CLAUDE_ACCOUNT": "personal"})
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertIn("MARKER=personal", selected.stdout)

        clash = self.jam("run", "claude:work", "new", "default", "default", "edit", "hi",
                         extra={"JAMSESSION_CLAUDE_ACCOUNT": "personal"})
        self.assertEqual(clash.returncode, 2, clash.stderr)
        self.assertIn("does not match", clash.stderr)
        self.assertNotIn("run work", self.launches()[-1:])

        codex = self.jam("run", "codex:work", "new", "default", "default", "edit", "hi")
        self.assertEqual(codex.returncode, 0, codex.stderr)
        self.assertIn("MARKER=codex-work", codex.stdout)
        self.assertIn(f"CODEX_HOME={self.home / 'codex-work'}", codex.stdout)
        self.assertNotIn("TEST_ACCOUNT_MARKER", os.environ)

        recorded = json.loads(self.sessions.read_text())
        self.assertEqual(recorded["claude"]["sess-personal"], "personal")
        self.assertEqual(recorded["claude"]["sess-work"], "work")
        self.assertEqual(self.sessions.stat().st_mode & 0o777, 0o600)

    def test_resume_message_and_steer_reuse_the_recorded_account(self):
        self.claude_accounts()
        started = self.jam("run", "claude:personal", "new", "default", "default", "edit", "hi")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("session: sess-personal", started.stderr)
        self.assertEqual(json.loads(self.sessions.read_text())["claude"]["sess-personal"], "personal")

        resumed = self.jam("run", "claude", "sess-personal", "default", "default", "edit", "again")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertIn("MARKER=personal", resumed.stdout)
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.personal_dir}", resumed.stdout)

        refused = self.jam("run", "claude:work", "sess-personal", "default", "default", "edit", "nope")
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("refusing account", refused.stderr)
        self.assertEqual(self.launches(), ["run personal", "run personal"])

        message = self.jam("message", "claude", "sess-personal", "hello")
        self.assertEqual(message.returncode, 0, message.stderr)
        self.assertIn("MARKER=personal", message.stdout)

        steer_refused = self.jam("steer", "claude:work", "sess-personal", "stop")
        self.assertEqual(steer_refused.returncode, 2, steer_refused.stderr)
        self.assertIn("refusing account", steer_refused.stderr)
        self.assertEqual(self.launches(), ["run personal", "run personal", "message personal"])

        steer = self.jam("steer", "claude", "sess-personal", "continue")
        self.assertEqual(steer.returncode, 0, steer.stderr)
        self.assertIn("MARKER=personal", steer.stdout)
        self.assertEqual(self.launches(),
                         ["run personal", "run personal", "message personal", "steer personal"])
        self.assertEqual(json.loads(self.sessions.read_text())["claude"]["sess-personal"], "personal")

    def test_failover_moves_from_a_low_account_to_the_next(self):
        self.claude_accounts()
        tiers = self.root / "tiers.toml"
        tiers.write_text(
            'tiers = [\n  { name = "A", models = ["opus-test"] },\n]\n\n'
            "[model.opus-test]\n"
            "via = [\n"
            '  { harness = "claude", account = "work", id = "opus-test" },\n'
            '  { harness = "claude", account = "personal", id = "opus-test" },\n'
            "]\n"
        )
        usage = self.root / "usage.json"
        usage.write_text(json.dumps({"providers": [
            {"agent": "claude", "account": "work", "status": "ok",
             "windows": [{"remaining_percent": 10}]},
            {"agent": "claude", "account": "personal", "status": "ok",
             "windows": [{"remaining_percent": 80}]},
        ]}))
        reply = self.jam("run", "--failover", "claude:work", "new", "opus-test", "high", "edit", "hi",
                         extra={
                             "JAMSESSION_TIERS": str(tiers),
                             "JAMSESSION_USAGE_JSON": str(usage),
                             "JAMSESSION_LATEST_CACHE": str(self.root / "latest.json"),
                         })
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("skipping claude:work", reply.stderr)
        self.assertIn("usage 10% left", reply.stderr)
        self.assertIn("ran: provider=claude:personal", reply.stderr)
        self.assertIn("MARKER=personal", reply.stdout)
        self.assertNotIn("MARKER=work", reply.stdout)
        self.assertEqual(self.launches(), ["run personal"])
        self.assertEqual(json.loads(self.sessions.read_text())["claude"]["sess-personal"], "personal")


class UsageAccountTests(unittest.TestCase):
    def test_each_account_is_reported_from_its_own_env(self):
        temp = tempfile.TemporaryDirectory(prefix="jamsession-account-usage-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        work = root / "work"
        personal = root / "personal"
        work.mkdir()
        personal.mkdir()
        (work / "claude.txt").write_text("Current week (all models)\n10% used\nResets Sep 7 at 7am\n")
        (personal / "claude.txt").write_text("Current week (all models)\n80% used\nResets Sep 7 at 7am\n")
        accounts = root / "accounts.toml"
        accounts.write_text(
            "[claude.work]\n"
            f'env = {{ JAMSESSION_USAGE_FIXTURE_DIR = "{work}" }}\n'
            "\n"
            "[claude.personal]\n"
            f'env = {{ JAMSESSION_USAGE_FIXTURE_DIR = "{personal}" }}\n'
        )
        config = root / "jamsession.conf"
        config.write_text("")
        env = os.environ.copy()
        for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR", "JAMSESSION_USAGE_FIXTURE_DIR",
                     "JAMSESSION_CLAUDE_ACCOUNT"):
            env.pop(name, None)
        env.update({
            "HOME": str(root / "home"),
            "JAMSESSION_CONFIG": str(config),
            "JAMSESSION_ACCOUNTS": str(accounts),
            "JAMSESSION_SESSION_ACCOUNTS": str(root / "sessions.json"),
            "JAMSESSION_CLAUDE_BIN": str(root / "missing-claude"),
            "JAMSESSION_USAGE_TIMEOUT": "1",
        })
        before = os.environ.get("JAMSESSION_USAGE_FIXTURE_DIR")
        reply = subprocess.run([str(ROOT / "jamsession"), "usage", "claude", "--json"],
                               env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(os.environ.get("JAMSESSION_USAGE_FIXTURE_DIR"), before)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        rows = json.loads(reply.stdout)["providers"]
        self.assertEqual([(row["agent"], row["account"]) for row in rows],
                         [("claude", "work"), ("claude", "personal")])
        self.assertEqual(rows[0]["windows"][0]["remaining_percent"], 90)
        self.assertEqual(rows[1]["windows"][0]["remaining_percent"], 20)


class RecallAccountTests(unittest.TestCase):
    def test_recall_searches_every_accounts_history_directory(self):
        temp = tempfile.TemporaryDirectory(prefix="jamsession-account-recall-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        home = root / "home"
        work = root / "work-claude"
        personal = root / "personal-claude"
        home.mkdir()
        for directory, session, text in (
            (work, "work-session", "work-account-history"),
            (personal, "personal-session", "personal-account-history"),
        ):
            path = directory / "projects" / "repo" / f"{session}.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(claude_record(text))
        accounts = root / "accounts.toml"
        accounts.write_text(
            "[claude.work]\n"
            f'env = {{ CLAUDE_CONFIG_DIR = "{work}" }}\n'
            "\n"
            "[claude.personal]\n"
            f'env = {{ CLAUDE_CONFIG_DIR = "{personal}" }}\n'
        )
        config = root / "config"
        config.write_text("")
        env = os.environ.copy()
        for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR", "CLAUDE_CONFIG_DIR", "CODEX_HOME",
                     "JAMSESSION_CLAUDE_ACCOUNT"):
            env.pop(name, None)
        env.update({
            "HOME": str(home),
            "JAMSESSION_CONFIG": str(config),
            "JAMSESSION_ACCOUNTS": str(accounts),
            "JAMSESSION_SESSION_ACCOUNTS": str(root / "sessions.json"),
            "JAMSESSION_CWD": str(root),
        })

        def recall(session, phrase):
            return subprocess.run([str(ROOT / "jamsession"), "recall", "claude", session, phrase],
                                  env=env, capture_output=True, text=True, timeout=30)

        work_reply = recall("work-session", "work-account-history")
        self.assertEqual(work_reply.returncode, 0, work_reply.stderr)
        self.assertIn("work-account-history", work_reply.stdout)
        personal_reply = recall("personal-session", "personal-account-history")
        self.assertEqual(personal_reply.returncode, 0, personal_reply.stderr)
        self.assertIn("personal-account-history", personal_reply.stdout)
        missing = recall("personal-session", "work-account-history")
        self.assertEqual(missing.returncode, 1, missing.stderr)


class ShippedAccountFilesTests(unittest.TestCase):
    def test_the_example_file_names_no_live_account(self):
        env = os.environ.copy()
        env["JAMSESSION_ACCOUNTS"] = str(ROOT / "accounts.toml.example")
        reply = subprocess.run([sys.executable, str(ROOT / "usage" / "jamsession_accounts.py"), "list", "claude"],
                               env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(reply.stdout, "")

    def test_shipped_tiers_do_not_name_an_account(self):
        table = tomllib.loads((ROOT / "tiers.toml").read_text())
        named = [via.get("account") for entry in table["model"].values() for via in entry["via"] if via.get("account")]
        self.assertEqual(named, [])


if __name__ == "__main__":
    unittest.main()
