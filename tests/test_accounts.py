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
printf 'INHERITED=%s%s%s\\n' "${CLAUDE_CODE_OAUTH_TOKEN:+oauth}" "${ANTHROPIC_API_KEY:+apikey}" "${ANTHROPIC_AUTH_TOKEN:+authtoken}"
"""

# Dummy values standing in for what the Claude desktop app exports.
INHERITED_AUTH = {
    "CLAUDE_CODE_OAUTH_TOKEN": "inherited-dummy",
    "ANTHROPIC_API_KEY": "inherited-dummy",
    "ANTHROPIC_AUTH_TOKEN": "inherited-dummy",
}


def claude_record(text):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": text}}) + "\n"


class AccountHarness(unittest.TestCase):
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
                     "JAMSESSION_USAGE_FIXTURE_DIR", "JAMSESSION_LATEST_CACHE",
                     "JAMSESSION_USAGE_CACHE", "JAMSESSION_FAILOVER_STEP"):
            self.env.pop(name, None)
        self.usage_cache = self.root / "usage-cache.json"
        self.env.update({
            "HOME": str(self.home),
            "JAMSESSION_CONFIG": str(self.config),
            "JAMSESSION_ADAPTER_DIR": str(adapters),
            "JAMSESSION_ACCOUNTS": str(self.accounts_path),
            "JAMSESSION_SESSION_ACCOUNTS": str(self.sessions),
            "JAMSESSION_CWD": str(self.root),
            "ACCOUNT_LOG": str(self.log),
            "CLAUDE_CONFIG_DIR": "/ambient/claude",
            "JAMSESSION_USAGE_CACHE": str(self.usage_cache),
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

class AccountCLITests(AccountHarness):
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


    def test_inherited_claude_credentials_never_reach_an_account_run(self):
        self.claude_accounts()
        tiers = self.root / "tiers.toml"
        tiers.write_text(opus_tiers('  { harness = "claude", id = "opus-test" },'))
        extra = dict(INHERITED_AUTH, JAMSESSION_TIERS=str(tiers),
                     JAMSESSION_LATEST_CACHE=str(self.root / "latest.json"))
        runs = {
            "named": self.jam("run", "claude:personal", "new", "default", "default", "edit", "hi", extra=extra),
            "bare": self.jam("run", "claude", "new", "default", "default", "edit", "hi", extra=extra),
            "resume": self.jam("run", "claude", "sess-personal", "default", "default", "edit", "hi", extra=extra),
            "message": self.jam("message", "claude", "sess-personal", "hi", extra=extra),
            "failover": self.jam("run", "--failover", "--min-usage", "0", "claude", "new", "opus-test",
                                 "high", "edit", "hi", extra=extra),
        }
        for name, reply in runs.items():
            self.assertEqual(reply.returncode, 0, f"{name}: {reply.stderr}")
            self.assertIn("INHERITED=\n", reply.stdout, name)
            self.assertNotIn("inherited-dummy", reply.stdout + reply.stderr, name)
        codex = self.jam("run", "codex", "new", "default", "default", "edit", "hi", extra=extra)
        self.assertEqual(codex.returncode, 0, codex.stderr)
        self.assertIn("INHERITED=oauthapikeyauthtoken\n", codex.stdout)

    def test_a_config_exported_token_does_not_reach_an_account_run(self):
        self.claude_accounts()
        adapter = self.root / "adapters" / "jamsession_claude"
        adapter.write_text(
            "#!/usr/bin/env bash\n"
            f'source "{ROOT / "adapters" / "_jamsession_adapter_common"}"\n'
            "jamsession_adapter_setup claude claude JAMSESSION_CLAUDE_BIN\n"
            "printf 'session: sess-%s\\n' \"${TEST_ACCOUNT_MARKER:-none}\" >&2\n"
            "printf 'MARKER=%s\\n' \"${TEST_ACCOUNT_MARKER:-none}\"\n"
            "printf 'INHERITED=%s%s\\n' \"${CLAUDE_CODE_OAUTH_TOKEN:+oauth}\" \"${ANTHROPIC_API_KEY:+apikey}\"\n"
        )
        adapter.chmod(0o755)
        self.config.write_text(
            "export CLAUDE_CODE_OAUTH_TOKEN=config-dummy\n"
            "TEST_ACCOUNT_MARKER=config\n"
        )
        reply = self.jam("run", "claude:personal", "new", "default", "default", "edit", "hi")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("INHERITED=\n", reply.stdout)
        self.assertIn("MARKER=personal", reply.stdout)
        self.accounts_path.unlink()
        plain = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertIn("INHERITED=oauth\n", plain.stdout)

    def test_an_account_may_set_its_own_claude_token(self):
        self.write_accounts(
            "[claude.token]\n"
            'env = { CLAUDE_CODE_OAUTH_TOKEN = "account-dummy", TEST_ACCOUNT_MARKER = "token" }\n'
        )
        reply = self.jam("run", "claude:token", "new", "default", "default", "edit", "hi", extra=INHERITED_AUTH)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("INHERITED=oauth\n", reply.stdout)


class UsageAccountTests(unittest.TestCase):
    def test_usage_is_read_without_inherited_claude_credentials(self):
        temp = tempfile.TemporaryDirectory(prefix="jamsession-account-usage-auth-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        log = root / "usage-launches"
        fake = root / "claude"
        fake.write_text(
            "#!/bin/sh\n"
            'printf \'%s %s%s%s\\n\' "${TEST_ACCOUNT_MARKER:-none}" "${CLAUDE_CODE_OAUTH_TOKEN:+oauth}" '
            '"${ANTHROPIC_API_KEY:+apikey}" "${ANTHROPIC_AUTH_TOKEN:+authtoken}" >>"$USAGE_LOG"\n'
            "printf 'Current week (all models)\\n40%% used\\nResets Sep 7 at 7am\\n"
            "Current week (Fable)\\n40%% used\\nResets Sep 7 at 7am\\n'\n"
            "sleep 2\n"
        )
        fake.chmod(0o755)
        accounts = root / "accounts.toml"
        accounts.write_text(
            '[claude.work]\nenv = { TEST_ACCOUNT_MARKER = "work" }\n\n'
            '[claude.personal]\nenv = { TEST_ACCOUNT_MARKER = "personal" }\n'
        )
        config = root / "jamsession.conf"
        config.write_text("")
        env = os.environ.copy()
        for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR", "JAMSESSION_USAGE_FIXTURE_DIR",
                     "JAMSESSION_CLAUDE_ACCOUNT", "TEST_ACCOUNT_MARKER"):
            env.pop(name, None)
        env.update(INHERITED_AUTH)
        env.update({
            "HOME": str(root / "home"),
            "JAMSESSION_CONFIG": str(config),
            "JAMSESSION_ACCOUNTS": str(accounts),
            "JAMSESSION_SESSION_ACCOUNTS": str(root / "sessions.json"),
            "JAMSESSION_USAGE_CACHE": str(root / "usage-cache.json"),
            "JAMSESSION_CLAUDE_BIN": str(fake),
            "JAMSESSION_USAGE_TIMEOUT": "8",
            "USAGE_LOG": str(log),
        })
        reply = subprocess.run([str(ROOT / "jamsession"), "usage", "claude", "--json"],
                               env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(sorted(log.read_text().splitlines()), ["personal ", "work "])

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


SECURITY_STUB = """#!/bin/sh
service=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "-s" ]; then
    service="$arg"
  fi
  prev="$arg"
done
file="$KEYCHAIN_DIR/$service"
if [ -f "$file" ]; then
  cat "$file"
  exit 0
fi
printf 'not found\\n' >&2
exit 44
"""

KEY_ADAPTER = """#!/bin/sh
printf '%s %s\\n' "$1" "${TEST_ACCOUNT_MARKER:-none}" >>"$ACCOUNT_LOG"
if [ -n "${ANTHROPIC_API_KEY:-}" ] && [ -f "${KEY_FILE:-}" ] && \
  [ "$ANTHROPIC_API_KEY" = "$(cat "$KEY_FILE")" ]; then
  printf 'key-received\\n' >>"$ACCOUNT_LOG"
  printf 'key-received\\n'
fi
case "$1" in
  run) printf 'session: sess-%s\\n' "${TEST_ACCOUNT_MARKER:-none}" >&2 ;;
esac
printf 'MARKER=%s\\n' "${TEST_ACCOUNT_MARKER:-none}"
"""

REFUSAL_ADAPTER = """#!/bin/sh
printf '%s %s\\n' "$1" "${TEST_ACCOUNT_MARKER:-none}" >>"$ACCOUNT_LOG"
case "$TEST_ACCOUNT_MARKER" in
  a|b|work|personal)
    printf 'session: sess-%s\\n' "$TEST_ACCOUNT_MARKER" >&2
    exit 75
    ;;
esac
printf 'session: sess-%s\\n' "${TEST_ACCOUNT_MARKER:-none}" >&2
printf 'MARKER=%s\\n' "${TEST_ACCOUNT_MARKER:-none}"
"""


def opus_tiers(*vias):
    body = "\n".join(vias)
    return (
        'tiers = [\n  { name = "A", models = ["opus-test"] },\n]\n\n'
        "[model.opus-test]\nvia = [\n"
        f"{body}\n]\n"
    )


class PlainProviderTests(AccountHarness):
    def test_no_accounts_file_keeps_the_plain_provider(self):
        self.assertFalse(self.accounts_path.exists())
        reply = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("MARKER=none", reply.stdout)
        self.assertFalse(self.sessions.exists())
        self.assertEqual(self.launches(), ["run none"])
        fixture = self.root / "usage-fixture"
        fixture.mkdir()
        (fixture / "claude.txt").write_text("Current week (all models)\n10% used\nResets Sep 7 at 7am\n")
        usage = self.jam("usage", "claude", "--json", extra={
            "JAMSESSION_USAGE_FIXTURE_DIR": str(fixture),
            "JAMSESSION_CLAUDE_BIN": str(self.root / "missing-claude"),
            "JAMSESSION_USAGE_TIMEOUT": "1",
        })
        self.assertEqual(usage.returncode, 0, usage.stderr)
        row = json.loads(usage.stdout)["providers"][0]
        self.assertEqual(row["agent"], "claude")
        self.assertNotIn("account", row)
        tiers = self.root / "tiers.toml"
        tiers.write_text(opus_tiers('  { harness = "claude", id = "opus-test" },'))
        failover = self.jam(
            "run", "--failover", "--min-usage", "0", "claude", "new", "opus-test", "high", "edit", "hi",
            extra={"JAMSESSION_TIERS": str(tiers), "JAMSESSION_LATEST_CACHE": str(self.root / "latest.json")})
        self.assertEqual(failover.returncode, 0, failover.stderr)
        self.assertIn("ran: provider=claude ", failover.stderr)
        self.assertNotIn("provider=claude:", failover.stderr)
        self.assertFalse(self.sessions.exists())

    def test_one_account_does_not_rename_the_provider(self):
        fixture = self.root / "usage-fixture"
        fixture.mkdir()
        (fixture / "claude.txt").write_text("Current week (all models)\n10% used\nResets Sep 7 at 7am\n")
        self.write_accounts(
            "[claude.only]\n"
            f'env = {{ TEST_ACCOUNT_MARKER = "only", JAMSESSION_USAGE_FIXTURE_DIR = "{fixture}" }}\n'
        )
        reply = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("MARKER=only", reply.stdout)
        tiers = self.root / "tiers.toml"
        tiers.write_text(opus_tiers('  { harness = "claude", id = "opus-test" },'))
        failover = self.jam(
            "run", "--failover", "--min-usage", "0", "claude", "new", "opus-test", "high", "edit", "hi",
            extra={"JAMSESSION_TIERS": str(tiers), "JAMSESSION_LATEST_CACHE": str(self.root / "latest.json")})
        self.assertEqual(failover.returncode, 0, failover.stderr)
        self.assertIn("MARKER=only", failover.stdout)
        self.assertIn("ran: provider=claude ", failover.stderr)
        self.assertNotIn("provider=claude:", failover.stderr)
        usage = self.jam("usage", "claude", "--json", extra={
            "JAMSESSION_CLAUDE_BIN": str(self.root / "missing-claude"),
            "JAMSESSION_USAGE_TIMEOUT": "1",
        })
        self.assertEqual(usage.returncode, 0, usage.stderr)
        row = json.loads(usage.stdout)["providers"][0]
        self.assertNotIn("account", row)
        self.assertEqual(row["windows"][0]["remaining_percent"], 90)


class FailoverOrderTests(AccountHarness):
    def setUp(self):
        super().setUp()
        adapter = self.root / "adapters" / "jamsession_claude"
        adapter.write_text(REFUSAL_ADAPTER)
        adapter.chmod(0o755)
        self.tiers = self.root / "tiers.toml"
        self.extra = {"JAMSESSION_TIERS": str(self.tiers), "JAMSESSION_LATEST_CACHE": str(self.root / "latest.json")}

    def test_three_accounts_fail_over_in_file_order(self):
        self.write_accounts(
            '[claude.a]\nenv = { TEST_ACCOUNT_MARKER = "a" }\n\n'
            '[claude.b]\nenv = { TEST_ACCOUNT_MARKER = "b" }\n\n'
            '[claude.c]\nenv = { TEST_ACCOUNT_MARKER = "c" }\n'
        )
        self.tiers.write_text(opus_tiers('  { harness = "claude", id = "opus-test" },'))
        reply = self.jam(
            "run", "--failover", "--min-usage", "0", "claude", "new", "opus-test", "high", "edit", "hi",
            extra=self.extra)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(self.launches(), ["run a", "run b", "run c"])
        self.assertIn("ran: provider=claude:c", reply.stderr)
        self.assertLess(reply.stderr.index("claude:a"), reply.stderr.index("claude:b"))
        self.assertLess(reply.stderr.index("claude:b"), reply.stderr.index("claude:c"))

    def test_named_vias_keep_listed_order_without_renaming_the_default(self):
        self.write_accounts(
            '[claude.work]\nenv = { TEST_ACCOUNT_MARKER = "work" }\n\n'
            '[claude.personal]\nenv = { TEST_ACCOUNT_MARKER = "personal" }\n\n'
            '[claude.api]\nenv = { TEST_ACCOUNT_MARKER = "api" }\n'
        )
        self.tiers.write_text(opus_tiers(
            '  { harness = "claude", id = "opus-test" },',
            '  { harness = "claude", account = "personal", id = "opus-test" },',
            '  { harness = "claude", account = "api", id = "opus-test" },',
        ))
        reply = self.jam(
            "run", "--failover", "--min-usage", "0", "claude", "new", "opus-test", "high", "edit", "hi",
            extra=self.extra)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(self.launches(), ["run work", "run personal", "run api"])
        self.assertIn("failover: claude opus-test high refused", reply.stderr)
        self.assertNotIn("failover: claude:work", reply.stderr)
        self.assertNotIn("ran: provider=claude:work", reply.stderr)
        self.assertEqual(reply.stderr.count("several claude accounts"), 1)
        self.assertIn("ran: provider=claude:api", reply.stderr)


class CodexWorkspaceTests(AccountHarness):
    def test_codex_workspaces_follow_codex_home(self):
        work = self.root / "codex-work"
        other = self.root / "codex-other"
        self.write_accounts(
            "[codex.work]\n"
            f'env = {{ CODEX_HOME = "{work}", TEST_ACCOUNT_MARKER = "work" }}\n\n'
            "[codex.other]\n"
            f'env = {{ CODEX_HOME = "{other}", TEST_ACCOUNT_MARKER = "other" }}\n'
        )
        started = self.jam("run", "codex:other", "new", "default", "default", "edit", "hi")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("MARKER=other", started.stdout)
        self.assertIn(f"CODEX_HOME={other}", started.stdout)
        self.assertNotIn(str(work), started.stdout)
        resumed = self.jam("run", "codex", "sess-other", "default", "default", "edit", "again")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertIn(f"CODEX_HOME={other}", resumed.stdout)
        message = self.jam("message", "codex", "sess-other", "hello")
        self.assertEqual(message.returncode, 0, message.stderr)
        self.assertIn("MARKER=other", message.stdout)
        steer = self.jam("steer", "codex", "sess-other", "continue")
        self.assertEqual(steer.returncode, 0, steer.stderr)
        self.assertIn(f"CODEX_HOME={other}", steer.stdout)
        refused = self.jam("message", "codex:work", "sess-other", "nope")
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("refusing account", refused.stderr)
        usage = self.root / "usage.json"
        usage.write_text(json.dumps({"providers": [
            {"agent": "codex", "account": "work", "status": "ok", "windows": [{"remaining_percent": 10}]},
            {"agent": "codex", "account": "other", "status": "ok", "windows": [{"remaining_percent": 80}]},
        ]}))
        tiers = self.root / "tiers.toml"
        tiers.write_text(opus_tiers('  { harness = "codex", id = "opus-test" },'))
        failover = self.jam(
            "run", "--failover", "codex", "new", "opus-test", "high", "edit", "hi",
            extra={
                "JAMSESSION_TIERS": str(tiers),
                "JAMSESSION_USAGE_JSON": str(usage),
                "JAMSESSION_LATEST_CACHE": str(self.root / "latest.json"),
            })
        self.assertEqual(failover.returncode, 0, failover.stderr)
        self.assertIn("skipping codex:work", failover.stderr)
        self.assertIn("ran: provider=codex:other", failover.stderr)
        self.assertIn(f"CODEX_HOME={other}", failover.stdout)
        self.assertNotIn(str(work), failover.stdout)


class CodexRecallTests(unittest.TestCase):
    def test_recall_searches_every_codex_home(self):
        temp = tempfile.TemporaryDirectory(prefix="jamsession-codex-recall-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        home = root / "home"
        work = root / "codex-work"
        other = root / "codex-other"
        home.mkdir()
        record = {
            "type": "response_item",
            "payload": {"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": "codex-other-history"}]},
        }
        path = other / "sessions" / "rollout-other-session.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record) + "\n")
        (work / "sessions").mkdir(parents=True)
        accounts = root / "accounts.toml"
        accounts.write_text(
            "[codex.work]\n"
            f'env = {{ CODEX_HOME = "{work}" }}\n\n'
            "[codex.other]\n"
            f'env = {{ CODEX_HOME = "{other}" }}\n'
        )
        env = os.environ.copy()
        for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR", "CODEX_HOME", "CLAUDE_CONFIG_DIR",
                     "JAMSESSION_CODEX_ACCOUNT"):
            env.pop(name, None)
        env.update({
            "HOME": str(home),
            "JAMSESSION_CONFIG": str(root / "config"),
            "JAMSESSION_ACCOUNTS": str(accounts),
            "JAMSESSION_SESSION_ACCOUNTS": str(root / "sessions.json"),
            "JAMSESSION_CWD": str(root),
        })
        (root / "config").write_text("")
        reply = subprocess.run(
            [str(ROOT / "jamsession"), "recall", "codex", "other-session", "codex-other-history"],
            env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("codex-other-history", reply.stdout)


class KeychainAndBudgetTests(AccountHarness):
    def setUp(self):
        super().setUp()
        self.secret = "sentinel-key-9f3c2a"
        self.keychain = self.root / "keychain"
        self.keychain.mkdir()
        self.key_file = self.root / "expected-key"
        self.key_file.write_text(self.secret)
        self.stub = self.root / "security"
        self.stub.write_text(SECURITY_STUB)
        self.stub.chmod(0o755)
        self.spend = self.root / "spend.json"
        adapter = self.root / "adapters" / "jamsession_claude"
        adapter.write_text(KEY_ADAPTER)
        adapter.chmod(0o755)
        self.base = {
            "JAMSESSION_SECURITY_BIN": str(self.stub),
            "JAMSESSION_SPEND": str(self.spend),
            "KEYCHAIN_DIR": str(self.keychain),
            "KEY_FILE": str(self.key_file),
        }

    def secret_is_absent(self, *chunks):
        for chunk in chunks:
            self.assertNotIn(self.secret, chunk)

    def test_a_keychain_value_reaches_only_that_run(self):
        (self.keychain / "jamsession-claude-api").write_text(self.secret + "\n")
        self.write_accounts(
            "[claude.api]\n"
            'env = { TEST_ACCOUNT_MARKER = "api" }\n'
            'keychain_env = { ANTHROPIC_API_KEY = "jamsession-claude-api" }\n\n'
            "[claude.work]\n"
            'env = { TEST_ACCOUNT_MARKER = "work" }\n'
        )
        api = self.jam("run", "claude:api", "new", "default", "default", "edit", "hi", extra=self.base)
        self.assertEqual(api.returncode, 0, api.stderr)
        self.assertIn("key-received", api.stdout)
        self.assertIn("MARKER=api", api.stdout)
        self.secret_is_absent(api.stdout, api.stderr, self.accounts_path.read_text(), self.log.read_text())
        self.assertNotIn(self.secret, self.sessions.read_text())
        if self.spend.exists():
            self.assertNotIn(self.secret, self.spend.read_text())
        work = self.jam("run", "claude:work", "new", "default", "default", "edit", "hi", extra=self.base)
        self.assertEqual(work.returncode, 0, work.stderr)
        self.assertNotIn("key-received", work.stdout)
        self.assertIn("MARKER=work", work.stdout)
        self.secret_is_absent(work.stdout, work.stderr)
        self.assertNotIn("ANTHROPIC_API_KEY", os.environ)

    def test_a_missing_keychain_item_skips_the_account(self):
        self.write_accounts(
            "[claude.api]\n"
            'kind = "api"\n'
            'backend = "claude-cli"\n'
            'env = { TEST_ACCOUNT_MARKER = "api" }\n'
            'keychain_env = { ANTHROPIC_API_KEY = "jamsession-claude-api" }\n\n'
            "[claude.work]\n"
            'env = { TEST_ACCOUNT_MARKER = "work" }\n'
        )
        tiers = self.root / "tiers.toml"
        tiers.write_text(opus_tiers('  { harness = "claude", id = "opus-test" },'))
        extra = dict(self.base, JAMSESSION_TIERS=str(tiers), JAMSESSION_LATEST_CACHE=str(self.root / "latest.json"))
        failover = self.jam(
            "run", "--failover", "--min-usage", "0", "claude", "new", "opus-test", "high", "edit", "hi",
            extra=extra)
        self.assertEqual(failover.returncode, 0, failover.stderr)
        self.assertEqual(failover.stderr.count("keychain item jamsession-claude-api not found"), 1)
        self.assertIn("ran: provider=claude:work", failover.stderr)
        self.assertEqual(self.launches(), ["run work"])
        self.secret_is_absent(failover.stdout, failover.stderr)
        direct = self.jam("run", "claude:api", "new", "default", "default", "edit", "hi", extra=self.base)
        self.assertEqual(direct.returncode, 75, direct.stderr)
        self.assertEqual(
            [line for line in direct.stderr.splitlines() if line.strip()],
            ["jamsession: claude:api is unavailable: keychain item jamsession-claude-api not found"])
        self.assertEqual(self.launches(), ["run work"])
        self.secret_is_absent(direct.stdout, direct.stderr)

    def test_an_unknown_backend_is_unavailable(self):
        self.write_accounts(
            "[claude.api]\n"
            'kind = "api"\n'
            'backend = "agent-sdk"\n'
            'env = { TEST_ACCOUNT_MARKER = "api" }\n'
        )
        reply = self.jam("run", "claude:api", "new", "default", "default", "edit", "hi", extra=self.base)
        self.assertEqual(reply.returncode, 75, reply.stderr)
        self.assertIn("unknown backend 'agent-sdk'", reply.stderr)
        self.assertEqual(self.launches(), [])

    def test_the_budget_stops_an_account_once_spend_reaches_it(self):
        config = self.root / "claude-api-home"
        config.mkdir()
        fake = self.root / "fake-claude"
        log = self.root / "claude-launches"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os\n"
            "from pathlib import Path\n"
            "log = Path(os.environ['CLAUDE_FAKE_LOG'])\n"
            "log.write_text(log.read_text() + 'launched\\n' if log.exists() else 'launched\\n')\n"
            "key = os.environ.get('ANTHROPIC_API_KEY', '')\n"
            "expected = Path(os.environ['KEY_FILE']).read_text()\n"
            "result = 'api-ok\\nkey-received' if key and key == expected else 'api-ok'\n"
            "json.dump({'type': 'result', 'result': result, 'total_cost_usd': 1.25}, __import__('sys').stdout)\n"
        )
        fake.chmod(0o755)
        (self.keychain / "jamsession-claude-api").write_text(self.secret + "\n")
        self.write_accounts(
            "[claude.api]\n"
            'kind = "api"\n'
            'backend = "claude-cli"\n'
            "monthly_budget_usd = 1\n"
            f'env = {{ CLAUDE_CONFIG_DIR = "{config}", TEST_ACCOUNT_MARKER = "api" }}\n'
            'keychain_env = { ANTHROPIC_API_KEY = "jamsession-claude-api" }\n'
        )
        extra = dict(self.base)
        extra.update({
            "JAMSESSION_ADAPTER_DIR": str(ROOT / "adapters"),
            "JAMSESSION_CLAUDE_BIN": str(fake),
            "CLAUDE_FAKE_LOG": str(log),
        })
        seeded = subprocess.run(
            [sys.executable, str(ROOT / "usage" / "jamsession_accounts.py"), "spend", "claude", "api", "1"],
            env=dict(self.env, **self.base), capture_output=True, text=True, timeout=30)
        self.assertEqual(seeded.returncode, 0, seeded.stderr)
        blocked = self.jam("run", "claude:api", "new", "default", "default", "edit", "hi", extra=extra)
        self.assertEqual(blocked.returncode, 75, blocked.stderr)
        self.assertIn("monthly budget reached: $1 of $1", blocked.stderr)
        self.assertFalse(log.exists())
        self.secret_is_absent(blocked.stdout, blocked.stderr, self.spend.read_text())
        self.spend.unlink()
        first = self.jam("run", "claude:api", "new", "default", "default", "edit", "hi", extra=extra)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("api-ok", first.stdout)
        self.assertIn("key-received", first.stdout)
        self.assertNotIn("total_cost_usd", first.stdout)
        self.assertEqual(log.read_text().count("launched"), 1)
        recorded = json.loads(self.spend.read_text())
        self.assertEqual(list(recorded["claude"]["api"].values()), [1.25])
        self.secret_is_absent(
            first.stdout, first.stderr, self.spend.read_text(), self.accounts_path.read_text(), log.read_text())
        if self.sessions.exists():
            self.assertNotIn(self.secret, self.sessions.read_text())
        second = self.jam("run", "claude:api", "new", "default", "default", "edit", "hi", extra=extra)
        self.assertEqual(second.returncode, 75, second.stderr)
        self.assertIn("monthly budget reached: $1.25 of $1", second.stderr)
        self.assertEqual(log.read_text().count("launched"), 1)
        self.secret_is_absent(second.stdout, second.stderr)


class AccountsCommandTests(AccountHarness):
    def test_add_writes_the_entry_and_prints_one_login_command(self):
        source = self.home / ".claude"
        (source / "skills").mkdir(parents=True)
        (source / "settings.json").write_text("{}\n")
        (source / "skills" / "demo").write_text("skill\n")
        added = self.jam("accounts", "add", "claude", "personal", "--link")
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertEqual(added.stdout.strip(), "claude-personal")
        dest = self.home / ".claude-personal"
        self.assertTrue(dest.is_dir())
        self.assertTrue((dest / "settings.json").is_symlink())
        self.assertTrue((dest / "skills").is_symlink())
        wrapper = self.home / ".local" / "bin" / "claude-personal"
        self.assertIn("jamsession account wrapper", wrapper.read_text())
        self.assertIn('CLAUDE_CONFIG_DIR="$HOME/.claude-personal"', wrapper.read_text())
        self.assertEqual(self.accounts_path.stat().st_mode & 0o777, 0o600)
        table = tomllib.loads(self.accounts_path.read_text())
        self.assertEqual(table["claude"]["personal"]["env"]["CLAUDE_CONFIG_DIR"], "~/.claude-personal")
        again = self.jam("accounts", "add", "claude", "personal")
        self.assertEqual(again.returncode, 2, again.stderr)
        self.assertIn("already has an account", again.stderr)
        codex = self.jam("accounts", "add", "codex", "side")
        self.assertEqual(codex.returncode, 0, codex.stderr)
        self.assertEqual(codex.stdout.strip(), "CODEX_HOME=~/.codex-side codex login")
        self.assertTrue((self.home / ".codex-side").is_dir())
        api = self.jam(
            "accounts", "add", "claude", "api", "--kind", "api", "--budget", "500",
            "--keychain", "ANTHROPIC_API_KEY=jamsession-claude-api")
        self.assertEqual(api.returncode, 0, api.stderr)
        self.assertEqual(
            api.stdout.strip(),
            "security add-generic-password -s jamsession-claude-api -a $USER -w")
        self.assertFalse((self.home / ".local" / "bin" / "claude-api").exists())
        text = self.accounts_path.read_text()
        self.assertIn('kind = "api"', text)
        self.assertIn('backend = "claude-cli"', text)
        self.assertIn("monthly_budget_usd = 500", text)
        self.assertIn('CLAUDE_CONFIG_DIR = "~/.claude-api"', text)
        self.assertNotIn("sentinel", text)

    def test_list_shows_usage_and_spend_against_the_budget(self):
        work = self.root / "work-fixture"
        api = self.root / "api-fixture"
        work.mkdir()
        api.mkdir()
        (work / "claude.txt").write_text(
            "Current session\n98% used\nResets 4:30pm\n"
            "Current week (all models)\n10% used\nResets Sep 7 at 7am\n"
        )
        (api / "claude.txt").write_text("Current week (all models)\n80% used\nResets Sep 7 at 7am\n")
        self.write_accounts(
            "[claude.work]\n"
            f'env = {{ JAMSESSION_USAGE_FIXTURE_DIR = "{work}" }}\n\n'
            "[claude.api]\n"
            "kind = \"api\"\n"
            "backend = \"claude-cli\"\n"
            "monthly_budget_usd = 500\n"
            f'env = {{ JAMSESSION_USAGE_FIXTURE_DIR = "{api}" }}\n'
        )
        spend = self.root / "spend.json"
        seeded = subprocess.run(
            [sys.executable, str(ROOT / "usage" / "jamsession_accounts.py"), "spend", "claude", "api", "12.5"],
            env=dict(self.env, JAMSESSION_SPEND=str(spend)), capture_output=True, text=True, timeout=30)
        self.assertEqual(seeded.returncode, 0, seeded.stderr)
        extra = {
            "JAMSESSION_SPEND": str(spend),
            "JAMSESSION_CLAUDE_BIN": str(self.root / "missing-claude"),
            "JAMSESSION_USAGE_TIMEOUT": "1",
        }
        listed = self.jam("accounts", "list", extra=extra)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("claude work", listed.stdout)
        self.assertIn("90% remaining", listed.stdout)
        self.assertLess(
            listed.stdout.index("90% remaining, Current week (all models)"),
            listed.stdout.index("2% remaining, Current session"))
        self.assertIn("claude api", listed.stdout)
        self.assertIn("spend: $12.50 of $500 this month", listed.stdout)
        usage = self.jam("usage", "claude", "--json", extra=extra)
        self.assertEqual(usage.returncode, 0, usage.stderr)
        rows = json.loads(usage.stdout)["providers"]
        self.assertEqual(rows[0]["windows"][0]["bucket_id"], "weekly_all")
        self.assertEqual(rows[0]["windows"][1]["bucket_id"], "current_session")
        self.assertEqual(rows[1]["account"], "api")
        self.assertEqual(rows[1]["spend"]["usd"], 12.5)
        self.assertEqual(rows[1]["spend"]["budget_usd"], 500)
        cached = json.loads(self.usage_cache.read_text())
        self.assertEqual(cached["providers"][0]["windows"][0]["remaining_percent"], 90)
        self.assertEqual(cached["providers"][0]["windows"][0]["bucket_id"], "weekly_all")


def usage_report(*windows):
    return json.dumps({"providers": [{"agent": "claude", "status": "ok", "windows": list(windows)}]})


def session_and_week(session_left, week_left):
    return usage_report(
        {"bucket_id": "current_session", "label": "Current session",
         "remaining_percent": session_left, "window_minutes": 300},
        {"bucket_id": "weekly_all", "label": "Current week (all models)",
         "remaining_percent": week_left, "window_minutes": 10080},
    )


class UsageThresholdTests(AccountHarness):
    def setUp(self):
        super().setUp()
        self.tiers = self.root / "tiers.toml"
        self.tiers.write_text(opus_tiers('  { harness = "claude", id = "opus-test" },'))
        self.usage = self.root / "usage.json"
        self.extra = {
            "JAMSESSION_TIERS": str(self.tiers),
            "JAMSESSION_LATEST_CACHE": str(self.root / "latest.json"),
            "JAMSESSION_USAGE_JSON": str(self.usage),
        }

    def fail_over(self):
        return self.jam(
            "run", "--failover", "claude", "new", "opus-test", "high", "edit", "hi",
            extra=self.extra)

    def test_two_percent_session_and_forty_percent_weekly_stays_available(self):
        self.usage.write_text(session_and_week(2, 40))
        reply = self.fail_over()
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(self.launches(), ["run none"])
        self.assertNotIn("usage 2% left", reply.stderr)
        self.log.write_text("")
        self.usage.write_text(session_and_week(90, 10))
        skipped = self.fail_over()
        self.assertEqual(skipped.returncode, 75, skipped.stderr)
        self.assertEqual(self.launches(), [])
        self.assertIn("usage 10% left, below 25%", skipped.stderr)

    def test_account_min_usage_overrides_the_global_threshold(self):
        self.write_accounts('[claude.work]\nmin_usage = 5\nenv = { TEST_ACCOUNT_MARKER = "work" }\n')
        self.usage.write_text(session_and_week(2, 10))
        reply = self.fail_over()
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(self.launches(), ["run work"])
        self.assertNotIn("below 25%", reply.stderr)
        self.log.write_text("")
        self.usage.write_text(session_and_week(90, 4))
        skipped = self.fail_over()
        self.assertEqual(skipped.returncode, 75, skipped.stderr)
        self.assertEqual(self.launches(), [])
        self.assertIn("usage 4% left, below 5%", skipped.stderr)
        self.write_accounts('[claude.work]\nenv = { TEST_ACCOUNT_MARKER = "work" }\n')
        self.usage.write_text(session_and_week(90, 10))
        plain = self.fail_over()
        self.assertEqual(plain.returncode, 75, plain.stderr)
        self.assertEqual(self.launches(), [])
        self.assertIn("usage 10% left, below 25%", plain.stderr)


def window(remaining, minutes, bucket):
    return {"bucket_id": bucket, "remaining_percent": remaining, "window_minutes": minutes}


class BareProviderWarningTests(AccountHarness):
    def setUp(self):
        super().setUp()
        self.spend = self.root / "spend.json"
        self.env["JAMSESSION_SPEND"] = str(self.spend)
        self.env["JAMSESSION_CLAUDE_BIN"] = str(self.root / "missing-claude")
        self.env["JAMSESSION_CODEX_BIN"] = str(self.root / "missing-codex")
        self.env["JAMSESSION_USAGE_TIMEOUT"] = "1"

    def write_cache(self, providers):
        self.usage_cache.write_text(json.dumps({"schema_version": 1, "providers": providers}))

    def three_accounts(self):
        self.write_accounts(
            "[claude.work]\n"
            "min_usage = 5\n"
            'env = { TEST_ACCOUNT_MARKER = "work" }\n\n'
            "[claude.personal]\n"
            "min_usage = 5\n"
            'env = { TEST_ACCOUNT_MARKER = "personal" }\n\n'
            "[claude.api]\n"
            'kind = "api"\n'
            'backend = "claude-cli"\n'
            "monthly_budget_usd = 500\n"
            'env = { TEST_ACCOUNT_MARKER = "api" }\n'
        )

    def seed_spend(self, amount):
        seeded = subprocess.run(
            [sys.executable, str(ROOT / "usage" / "jamsession_accounts.py"),
             "spend", "claude", "api", str(amount)],
            env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(seeded.returncode, 0, seeded.stderr)

    def test_a_bare_provider_warns_lists_usage_and_still_runs(self):
        self.three_accounts()
        self.seed_spend(498)
        self.write_cache([
            {"agent": "claude", "account": "work", "status": "ok", "windows": [
                window(2, 300, "current_session"), window(28, 10080, "weekly_all")]},
            {"agent": "claude", "account": "personal", "status": "ok", "windows": [
                window(91, 10080, "weekly_all")]},
            {"agent": "claude", "account": "api", "status": "ok", "windows": [
                window(50, 10080, "weekly_all")]},
        ])
        reply = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn(
            "jamsession: several claude accounts are set up; "
            "name one next time (claude:work, claude:personal, claude:api). "
            "Weekly usage left: work 28%, personal 91%, api $498 of $500. "
            "Using claude:work.",
            reply.stderr)
        self.assertIn("MARKER=work", reply.stdout)
        self.assertEqual(self.launches(), ["run work"])
        self.assertEqual(json.loads(self.sessions.read_text())["claude"]["sess-work"], "work")

        self.write_cache([
            {"agent": "claude", "account": "work", "status": "ok", "windows": [
                window(4, 10080, "weekly_all")]},
            {"agent": "claude", "account": "personal", "status": "ok", "windows": [
                window(91, 10080, "weekly_all")]},
        ])
        self.log.write_text("")
        low = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(low.returncode, 0, low.stderr)
        self.assertIn("work 4%, personal 91%, api $498 of $500", low.stderr)
        self.assertIn("Using claude:personal.", low.stderr)
        self.assertIn("MARKER=personal", low.stdout)
        self.assertEqual(self.launches(), ["run personal"])

        self.write_cache([
            {"agent": "claude", "account": "work", "status": "ok", "windows": [
                window(5, 10080, "weekly_all")]},
        ])
        self.log.write_text("")
        exact = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(exact.returncode, 0, exact.stderr)
        self.assertIn("Using claude:work.", exact.stderr)
        self.assertIn("work 5%, personal ?, api $498 of $500", exact.stderr)
        self.assertEqual(self.launches(), ["run work"])

    def test_a_named_account_does_not_warn(self):
        self.three_accounts()
        self.write_cache([
            {"agent": "claude", "account": "work", "status": "ok", "windows": [
                window(4, 10080, "weekly_all")]},
            {"agent": "claude", "account": "personal", "status": "ok", "windows": [
                window(91, 10080, "weekly_all")]},
        ])
        named = self.jam("run", "claude:personal", "new", "default", "default", "edit", "hi")
        self.assertEqual(named.returncode, 0, named.stderr)
        self.assertNotIn("several", named.stderr)
        self.assertIn("MARKER=personal", named.stdout)
        selected = self.jam("run", "claude", "new", "default", "default", "edit", "hi",
                            extra={"JAMSESSION_CLAUDE_ACCOUNT": "personal"})
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertNotIn("several", selected.stderr)
        self.assertIn("MARKER=personal", selected.stdout)
        self.assertNotIn("MARKER=work", selected.stdout)

    def test_a_single_account_does_not_warn(self):
        self.write_accounts('[claude.only]\nenv = { TEST_ACCOUNT_MARKER = "only" }\n')
        self.write_cache([
            {"agent": "claude", "status": "ok", "windows": [window(40, 10080, "weekly_all")]},
        ])
        reply = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertNotIn("several", reply.stderr)
        self.assertIn("MARKER=only", reply.stdout)

    def test_resuming_a_recorded_session_does_not_warn(self):
        self.three_accounts()
        self.write_cache([
            {"agent": "claude", "account": "work", "status": "ok", "windows": [
                window(28, 10080, "weekly_all")]},
            {"agent": "claude", "account": "personal", "status": "ok", "windows": [
                window(91, 10080, "weekly_all")]},
        ])
        started = self.jam("run", "claude:personal", "new", "default", "default", "edit", "hi")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("several", started.stderr)
        resumed = self.jam("run", "claude", "sess-personal", "default", "default", "edit", "again")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertNotIn("several", resumed.stderr)
        self.assertIn("MARKER=personal", resumed.stdout)
        message = self.jam("message", "claude", "sess-personal", "hello")
        self.assertEqual(message.returncode, 0, message.stderr)
        self.assertNotIn("several", message.stderr)
        self.assertIn("MARKER=personal", message.stdout)
        steer = self.jam("steer", "claude", "sess-personal", "continue")
        self.assertEqual(steer.returncode, 0, steer.stderr)
        self.assertNotIn("several", steer.stderr)
        self.assertEqual(self.launches(),
                         ["run personal", "run personal", "message personal", "steer personal"])

    def test_unknown_usage_and_a_bare_codex_provider(self):
        self.three_accounts()
        missing = self.jam("run", "claude", "new", "default", "default", "edit", "hi")
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertIn("Weekly usage left: work ?, personal ?, api $0 of $500.", missing.stderr)
        self.assertIn("Using claude:work.", missing.stderr)
        self.assertIn("MARKER=work", missing.stdout)
        self.write_accounts(
            "[codex.work]\n"
            'env = { CODEX_HOME = "~/codex-work", TEST_ACCOUNT_MARKER = "codex-work" }\n\n'
            "[codex.other]\n"
            'env = { CODEX_HOME = "~/codex-other", TEST_ACCOUNT_MARKER = "codex-other" }\n'
        )
        self.write_cache([
            {"agent": "codex", "account": "work", "status": "ok", "windows": [
                window(12, 300, "session"), window(60, 10080, "weekly")]},
            {"agent": "codex", "account": "other", "status": "ok", "windows": [
                window(70, 10080, "weekly")]},
        ])
        self.log.write_text("")
        codex = self.jam("run", "codex", "new", "default", "default", "edit", "hi")
        self.assertEqual(codex.returncode, 0, codex.stderr)
        self.assertIn(
            "jamsession: several codex accounts are set up; "
            "name one next time (codex:work, codex:other). "
            "Weekly usage left: work 60%, other 70%. Using codex:work.",
            codex.stderr)
        self.assertNotIn("12%", codex.stderr)
        self.assertIn("MARKER=codex-work", codex.stdout)
        quiet = self.jam("run", "codex", "new", "default", "default", "edit", "hi",
                         extra={"JAMSESSION_FAILOVER_STEP": "1"})
        self.assertEqual(quiet.returncode, 0, quiet.stderr)
        self.assertNotIn("several", quiet.stderr)
        self.assertIn("MARKER=codex-work", quiet.stdout)

    def test_an_internal_failover_step_does_not_switch_accounts(self):
        self.write_accounts(
            "[claude.work]\n"
            "min_usage = 5\n"
            'env = { TEST_ACCOUNT_MARKER = "work" }\n\n'
            "[claude.personal]\n"
            "min_usage = 5\n"
            'env = { TEST_ACCOUNT_MARKER = "personal" }\n'
        )
        self.write_cache([
            {"agent": "claude", "account": "work", "status": "ok", "windows": [
                window(4, 10080, "weekly_all")]},
            {"agent": "claude", "account": "personal", "status": "ok", "windows": [
                window(90, 10080, "weekly_all")]},
        ])
        tiers = self.root / "tiers.toml"
        tiers.write_text(opus_tiers(
            '  { harness = "claude", id = "opus-test" },',
            '  { harness = "claude", account = "personal", id = "opus-test" },',
        ))
        reply = self.jam(
            "run", "--failover", "--min-usage", "0", "claude", "new", "opus-test", "high", "edit", "hi",
            extra={"JAMSESSION_TIERS": str(tiers), "JAMSESSION_LATEST_CACHE": str(self.root / "latest.json")})
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(reply.stderr.count("several claude accounts"), 1)
        self.assertIn("Using claude:personal.", reply.stderr)
        self.assertIn("MARKER=work", reply.stdout)
        self.assertEqual(self.launches(), ["run work"])


if __name__ == "__main__":
    unittest.main()
