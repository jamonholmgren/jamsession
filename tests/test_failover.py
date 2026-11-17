"""Refusal classification per adapter, and tier failover through the public CLI, with fake providers."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFUSAL = 75
spec = importlib.util.spec_from_file_location("failover", ROOT / "usage" / "jamsession_failover.py")
failover = importlib.util.module_from_spec(spec)
sys.modules["failover"] = failover
spec.loader.exec_module(failover)

# One fake binary serves every provider: listing commands get what each adapter
# needs, and a run prints FAKE_STDOUT / FAKE_STDERR and exits FAKE_STATUS.
FAKE = r"""#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if args[:1] == ["create-chat"]:
    print("chat-1"); sys.exit(0)
if args[:1] == ["models"]:
    print("gemini-3.8-flash-high"); sys.exit(0)
if args[:2] == ["list", "--format"]:
    print("id,title"); sys.exit(0)
sys.stdout.write(os.environ.get("FAKE_STDOUT", ""))
sys.stderr.write(os.environ.get("FAKE_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_STATUS", "0")))
"""

PROVIDERS = ["claude", "codex", "cursor", "grok", "copilot", "devin", "muse", "antigravity"]


def codex_error(message):
    return json.dumps({"type": "error", "message": message}) + "\n"


def muse_error(message):
    return json.dumps({"payload_type": "run.failed", "error": message}) + "\n"


def antigravity_error(message):
    return json.dumps({"status": "ERROR", "conversation_id": "c1", "error": message}) + "\n"


# Where each provider puts a refusal: stdout events for JSON harnesses, else stderr.
REFUSAL_OUTPUT = {
    "claude": {"FAKE_STDOUT": "Claude AI usage limit reached|1763400000\n"},
    "codex": {"FAKE_STDOUT": codex_error("You've hit your usage limit. Try again at 3pm.")},
    "cursor": {"FAKE_STDERR": "Error: You've hit your usage limit for this billing cycle\n"},
    "grok": {"FAKE_STDERR": "error: 429 Too Many Requests: rate limit exceeded\n"},
    "copilot": {"FAKE_STDERR": "Error: You have exceeded your premium request allowance\n"},
    "devin": {"FAKE_STDERR": "error: resource_exhausted: subscription quota used\n"},
    "muse": {"FAKE_STDOUT": muse_error("Not authenticated. Run muse auth login.")},
    "antigravity": {"FAKE_STDOUT": antigravity_error("RESOURCE_EXHAUSTED: quota exceeded")},
}


class AdapterRefusalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="jamsession-refusal-test-")
        root = Path(cls.temp.name)
        fake = root / "agent"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        config = root / "config"
        config.write_text("")
        cls.env = dict(os.environ, HOME=str(root), JAMSESSION_CONFIG=str(config), JAMSESSION_CWD=str(root),
                       JAMSESSION_DEVIN_AUTOMATION="0",
                       JAMSESSION_CODEX_CONTROL_SOCKET=str(root / "no-socket"))
        for provider in PROVIDERS:
            cls.env[f"JAMSESSION_{provider.upper()}_BIN"] = str(fake)
        for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR"):
            cls.env.pop(name, None)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_adapter(self, provider, status, **output):
        env = dict(self.env, FAKE_STATUS=str(status), **{"FAKE_STDOUT": "", "FAKE_STDERR": "", **output})
        return subprocess.run([str(ROOT / "jamsession"), "run", provider, "new", "default", "default", "edit",
                               "test only"], env=env, capture_output=True, text=True, timeout=30)

    def test_each_adapter_reports_a_provider_refusal_as_exit_75(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                reply = self.run_adapter(provider, 1, **REFUSAL_OUTPUT[provider])
                self.assertEqual(reply.returncode, REFUSAL, reply.stderr)
                self.assertRegex(reply.stderr, r"(?m)^refusal: (limit|auth): ")

    def test_each_adapter_keeps_an_ordinary_failure(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                reply = self.run_adapter(provider, 1, FAKE_STDERR="error: build failed in parser.gd\n")
                self.assertNotIn(reply.returncode, (0, REFUSAL), reply.stderr)
                self.assertNotIn("refusal:", reply.stderr)

    def test_auth_failure_is_a_refusal(self):
        reply = self.run_adapter("claude", 1, FAKE_STDOUT="Not logged in · Please run /login\n")
        self.assertEqual(reply.returncode, REFUSAL)
        self.assertIn("refusal: auth: ", reply.stderr)

    def test_a_limit_notice_answered_as_success_is_still_a_refusal(self):
        reply = self.run_adapter("claude", 0, FAKE_STDOUT="You've hit your spend limit · resets 3pm\n")
        self.assertEqual(reply.returncode, REFUSAL)

    def test_a_long_successful_reply_that_mentions_limits_is_not_a_refusal(self):
        answer = "Added a rate limit to the API.\nThe quota now resets daily.\nTests pass.\nDone.\n"
        reply = self.run_adapter("grok", 0, FAKE_STDOUT=answer, FAKE_STDERR="warning: rate limit hit, retrying\n")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(reply.stdout, answer)


def table():
    return failover.load_tiers(ROOT / "tiers.toml")


class LadderTests(unittest.TestCase):
    def test_failover_never_moves_to_a_costlier_tier(self):
        tiers = table()
        rank = {tier["name"]: index for index, tier in enumerate(tiers["tiers"])}
        for name, entry in tiers["model"].items():
            for via in entry["via"]:
                for allow_lower in (False, True):
                    candidates = failover.ladder(tiers, via["harness"], via["id"], "high", allow_lower)
                    start = rank[candidates[0].tier]
                    with self.subTest(model=name, harness=via["harness"], allow_lower=allow_lower):
                        self.assertTrue(all(rank[c.tier] >= start for c in candidates))
                        if not allow_lower:
                            self.assertTrue(all(rank[c.tier] == start for c in candidates))

    def test_same_model_through_other_harnesses_comes_first_devin_first(self):
        candidates = failover.ladder(table(), "claude", "claude-opus-5-5", "medium")
        self.assertEqual([(c.provider, c.name) for c in candidates[:3]],
                         [("claude", "opus"), ("devin", "opus"), ("cursor", "opus")])
        self.assertEqual({c.name for c in candidates[3:]}, {"sol"})

    def test_lower_tiers_only_with_allow_lower(self):
        tiers = table()
        self.assertNotIn("C", {c.tier for c in failover.ladder(tiers, "codex", "gpt-6.1-sol", "high")})
        self.assertIn("C", {c.tier for c in failover.ladder(tiers, "codex", "gpt-6.1-sol", "high", True)})

    def test_lowest_tier_caps_how_far_failover_falls(self):
        tiers = failover.ladder(table(), "codex", "gpt-6.1-sol", "high", lowest_tier="C")
        self.assertEqual({c.tier for c in tiers}, {"B", "C"})

    def test_an_unknown_model_has_no_fallbacks(self):
        self.assertEqual(len(failover.ladder(table(), "copilot", "gpt-4.1", "high")), 1)

    def test_effort_folded_into_a_model_id_carries_to_fallbacks(self):
        candidates = failover.ladder(table(), "cursor", "grok-4.7-high", "default")
        self.assertEqual(candidates[1].effort, "high")


# A fake `jamsession` CLI for the failover loop: FAKE_PLAN maps provider to
# [status, reply]; every call is appended to FAKE_CALLS.
FAKE_CLI = r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CALLS"], "a") as calls:
    calls.write(json.dumps(args) + "\n")
status, reply = json.loads(os.environ["FAKE_PLAN"]).get(args[1], [0, "ok"])
sys.stdin.read()
sys.stdout.write(reply)
sys.exit(status)
"""


class FailoverRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jamsession-failover-test-")
        root = Path(self.temp.name)
        self.cli = root / "jamsession"
        self.cli.write_text(FAKE_CLI)
        self.cli.chmod(0o755)
        self.calls = root / "calls"
        self.usage = root / "usage.json"
        self.usage.write_text(json.dumps({"providers": []}))
        self.routes = root / "routes.toml"

    def tearDown(self):
        self.temp.cleanup()

    def run_helper(self, plan, *args, usage=None):
        if usage is not None:
            self.usage.write_text(json.dumps({"providers": usage}))
        env = dict(os.environ, JAMSESSION_CLI=str(self.cli), FAKE_CALLS=str(self.calls), FAKE_PLAN=json.dumps(plan),
                   JAMSESSION_USAGE_JSON=str(self.usage), JAMSESSION_TIERS=str(ROOT / "tiers.toml"),
                   JAMSESSION_ROUTES=str(self.routes))
        reply = subprocess.run([sys.executable, str(ROOT / "usage" / "jamsession_failover.py"), *args],
                               env=env, capture_output=True, text=True, timeout=30)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        return reply, calls

    def test_a_refusal_moves_to_the_same_model_on_devin_and_reports_what_ran(self):
        reply, calls = self.run_helper({"claude": [REFUSAL, "Claude AI usage limit reached"], "devin": [0, "answer"]},
                                       "run", "claude", "sess-1", "claude-opus-5-5", "medium", "edit", "do it")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(reply.stdout, "answer")
        self.assertEqual([call[1:5] for call in calls],
                         [["claude", "sess-1", "claude-opus-5-5", "medium"], ["devin", "new", "claude-opus-5-5", "medium"]])
        self.assertIn("ran: provider=devin model=claude-opus-5-5 effort=medium session=new", reply.stderr)

    def test_an_ordinary_failure_does_not_fail_over(self):
        reply, calls = self.run_helper({"claude": [1, "partial"]},
                                       "run", "claude", "new", "claude-opus-5-5", "medium", "edit", "do it")
        self.assertEqual(reply.returncode, 1)
        self.assertEqual(len(calls), 1)

    def test_low_usage_pools_are_skipped_but_unmetered_and_unread_pools_are_not(self):
        low = [{"agent": "devin", "status": "ok", "windows": [{"remaining_percent": 10}]},
               {"agent": "cursor", "status": "ok", "windows": [{"remaining_percent": 5}]}]
        reply, calls = self.run_helper({"claude": [REFUSAL, ""]},
                                       "run", "claude", "new", "claude-opus-5-5", "medium", "edit", "do it", usage=low)
        self.assertEqual([call[1] for call in calls], ["claude", "cursor"])  # cursor's Opus pool is unmetered
        self.assertIn("skipping devin claude-opus-5-5 medium (usage 10% left", reply.stderr)

    def test_every_refusal_exits_75_without_printing_a_refusal_as_the_answer(self):
        plan = {name: [REFUSAL, "limit reached"] for name in ("claude", "devin", "cursor", "codex")}
        reply, calls = self.run_helper(plan, "run", "claude", "new", "claude-opus-5-5", "medium", "edit", "do it")
        self.assertEqual(reply.returncode, REFUSAL)
        self.assertEqual(reply.stdout, "")
        self.assertIn("all routes refused", reply.stderr)
        self.assertEqual(len(calls), 5)

    def test_read_runs_skip_edit_only_harnesses(self):
        reply, calls = self.run_helper({"claude": [REFUSAL, ""]},
                                       "run", "claude", "new", "claude-opus-5-5", "medium", "read", "look")
        self.assertEqual([call[1] for call in calls], ["claude", "cursor"])

    def test_a_route_capped_at_tier_c_never_reaches_d_or_f(self):
        self.routes.write_text('[route.night]\ntier = "B"\neffort = "medium"\nlowest_tier = "C"\n')
        plan = {name: [REFUSAL, "limit reached"] for name in ("claude", "devin", "cursor", "codex", "grok", "muse")}
        reply, calls = self.run_helper(plan, "run", "--route", "night", "new", "edit", "fix")
        self.assertEqual(reply.returncode, REFUSAL)
        self.assertIn("all routes refused", reply.stderr)
        tried = {failover.find_model(table(), call[1], call[3]) for call in calls}
        self.assertIn("grok", tried)
        self.assertEqual({failover.tier_of(table())[name][1] for name in tried}, {"B", "C"})

    def test_a_tier_route_expands_and_fails_over(self):
        self.routes.write_text('[defaults]\nskip_below_usage = 25\n[route.doctor]\ntier = "B"\neffort = "medium"\n')
        reply, calls = self.run_helper({"devin": [REFUSAL, ""]}, "run", "--route", "doctor", "new", "edit", "fix")
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual([call[1] for call in calls], ["devin", "claude"])


if __name__ == "__main__":
    unittest.main()
