"""Independent new sessions through the public CLI, without real agent calls."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


class AdapterSessionTests(unittest.TestCase):
    def test_parallel_claude_grok_and_copilot_sessions_are_distinct(self):
        with tempfile.TemporaryDirectory(prefix="jamsession-session-test-") as temp:
            root = Path(temp)
            binary = root / "agent"
            binary.write_text("#!" + sys.executable + "\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
            binary.chmod(0o755)
            config = root / "config"
            # Repeat the weak PRNG seed: OS-backed session identity must not depend on it.
            config.write_text("RANDOM=42\n")
            env = dict(os.environ, HOME=temp, JAMSESSION_CONFIG=str(config),
                       JAMSESSION_CWD=temp, JAMSESSION_CLAUDE_BIN=str(binary),
                       JAMSESSION_GROK_BIN=str(binary), JAMSESSION_COPILOT_BIN=str(binary))
            for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR"):
                env.pop(name, None)

            def launch(provider):
                reply = subprocess.run([str(ROOT / "jamsession"), "run", provider, "new", "default",
                                        "high", "edit", "test only"], env=env,
                                       capture_output=True, text=True, timeout=10)
                self.assertEqual(reply.returncode, 0, reply.stderr)
                session = re.search(r"^session: (\S+)$", reply.stderr, re.MULTILINE)[1]
                parsed = uuid.UUID(session)
                self.assertEqual(parsed.version, 4)
                args = json.loads(reply.stdout)
                self.assertEqual(args[args.index("--session-id") + 1], session)
                return session

            with ThreadPoolExecutor(max_workers=5) as pool:
                sessions = list(pool.map(launch, ["claude", "grok", "copilot"] * 20))
            self.assertEqual(len(set(sessions)), len(sessions))

    def test_shared_uuid_reports_entropy_failure(self):
        script = 'source "$1"; JAMSESSION_PROVIDER=test; od() { return 1; }; session_id="$(jamsession_uuid)" || exit $?; printf LAUNCHED'
        reply = subprocess.run(["/bin/bash", "-c", script, "entropy-test",
                                str(ROOT / "adapters/_jamsession_adapter_common")],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(reply.returncode, 2)
        self.assertNotIn("LAUNCHED", reply.stdout)
        self.assertIn("OS randomness", reply.stderr)

    def test_every_adapter_uses_the_entropy_source_and_stops_if_it_fails(self):
        with tempfile.TemporaryDirectory(prefix="jamsession-entropy-test-") as temp:
            root = Path(temp)
            binary = root / "agent"
            binary.write_text("#!" + sys.executable + "\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
            binary.chmod(0o755)
            config = root / "config"
            env = dict(os.environ, HOME=temp, JAMSESSION_CONFIG=str(config),
                       JAMSESSION_CWD=temp, JAMSESSION_CLAUDE_BIN=str(binary),
                       JAMSESSION_GROK_BIN=str(binary), JAMSESSION_COPILOT_BIN=str(binary))
            for name in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR"):
                env.pop(name, None)
            entropy = os.urandom(16).hex()
            config.write_text("od() { printf '%s\\n' '" + entropy + "'; }\n")
            for provider in ("claude", "grok", "copilot"):
                args = [str(ROOT / "jamsession"), "run", provider, "new", "default", "high", "edit", "test"]
                reply = subprocess.run(args, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(reply.returncode, 0, reply.stderr)
                native_args = json.loads(reply.stdout)
                self.assertEqual(native_args[native_args.index("--session-id") + 1], str(uuid.UUID(hex=entropy, version=4)))
            config.write_text("od() { return 1; }\n")
            for provider in ("claude", "grok", "copilot"):
                reply = subprocess.run([str(ROOT / "jamsession"), "run", provider, "new", "default", "high", "edit", "test"],
                                       env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(reply.returncode, 2, reply.stderr)
                self.assertEqual(reply.stdout, "")


if __name__ == "__main__":
    unittest.main()
