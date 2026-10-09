"""Exercise the shipped CLI across a real Unix WebSocket boundary."""

import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import socketserver
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Peer(socketserver.BaseRequestHandler):
    def handle(self):
        stream = self.request.makefile("rb")
        try:
            headers = {}
            stream.readline()
            while True:
                line = stream.readline().strip()
                if not line:
                    break
                key, value = line.decode().split(":", 1)
                headers[key.lower()] = value.strip()
            accept = base64.b64encode(hashlib.sha1(
                (headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
            ).digest()).decode()
            self.request.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                                  "Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode())
            while True:
                frame = stream.read(2)
                if not frame:
                    return
                first, second = frame
                assert first == 0x81 and second & 0x80
                length = second & 127
                if length == 126:
                    length = struct.unpack("!H", stream.read(2))[0]
                elif length == 127:
                    length = struct.unpack("!Q", stream.read(8))[0]
                mask = stream.read(4)
                body = stream.read(length)
                msg = json.loads(bytes(value ^ mask[index % 4] for index, value in enumerate(body)))
                if "id" not in msg:
                    continue
                self.server.calls.append(msg)
                method = msg["method"]
                params = msg.get("params", {})
                response = {"id": msg["id"]}
                if method == "initialize":
                    response["result"] = {}
                elif method == "thread/read":
                    if self.server.scenario == "busy":
                        self.server.save(params["threadId"])
                    response["result"] = {"thread": {"id": params["threadId"], "path": self.server.rollout,
                        "status": {"type": "notLoaded" if self.server.scenario in ("busy", "cold") else
                                   "active" if self.server.scenario == "active" else "idle"}}}
                elif method == "thread/resume":
                    if self.server.scenario == "busy":
                        response["error"] = {"code": -32600, "message": "thread fixture already has an active writer"}
                    else:
                        response["result"] = {"thread": {"id": "fixture", "status": {
                            "type": "active" if self.server.scenario == "active" else "idle",
                        }}, "model": "saved-model", "cwd": self.server.saved["cwd"],
                            "approvalPolicy": "on-request", "approvalsReviewer": "guardian_subagent",
                            "sandbox": {"type": "readOnly", "networkAccess": False}, "reasoningEffort": "high"}
                        if params.get("sandbox") == "workspace-write":
                            response["result"]["sandbox"] = {
                                "type": "workspaceWrite", "writableRoots": params["config"]["sandbox_workspace_write.writable_roots"],
                                "networkAccess": params["config"]["sandbox_workspace_write.network_access"],
                                "excludeTmpdirEnvVar": params["config"]["sandbox_workspace_write.exclude_tmpdir_env_var"],
                                "excludeSlashTmp": params["config"]["sandbox_workspace_write.exclude_slash_tmp"],
                            }
                        response["result"].update(self.server.resume_overrides)
                elif method == "thread/settings/update":
                    response["result"] = {}
                elif method == "thread/queue/add":
                    if self.server.scenario == "lost_ack":
                        return
                    if self.server.scenario == "denied":
                        response["error"] = {"code": -32600, "message": "denied by managed policy"}
                    else:
                        response["result"] = {"queuedSubmission": {"id": "q1", "input": params["input"]}}
                elif method == "turn/start":
                    response["result"] = {"turn": {"id": "t1", "status": "inProgress"}}
                else:
                    response["error"] = {"code": -32601, "message": "unexpected method"}
                self.send(response)
                if method == "turn/start":
                    self.send({"method": "item/completed", "params": {
                        "threadId": "fixture", "turnId": "t1", "item": {
                            "type": "agentMessage", "phase": "final_answer", "text": "CONTROL_RESULT",
                        },
                    }})
                    self.send({"method": "turn/completed", "params": {
                        "threadId": "fixture", "turn": {"id": "t1", "status": "completed"},
                    }})
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            stream.close()

    def send(self, message):
        payload = json.dumps(message).encode()
        if len(payload) < 126:
            header = bytes([0x81, len(payload)])
        elif len(payload) <= 65535:
            header = b"\x81\x7e" + struct.pack("!H", len(payload))
        else:
            header = b"\x81\x7f" + struct.pack("!Q", len(payload))
        self.request.sendall(header + payload)


class Fixture(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, path, scenario="idle"):
        self.calls = []
        self.scenario = scenario
        self.resume_overrides = {}
        self.rollout = str(Path(path).with_suffix(".jsonl"))
        self.saved = {"cwd": str(Path(path).parent), "model": "saved-model", "reasoning_effort": "high",
                      "approval_policy": "on-request", "approvals_reviewer": "guardian_subagent",
                      "permission_profile": {"type": "managed", "network": "restricted", "file_system": {
                          "type": "restricted", "entries": [{"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]}}}
        self.save()
        super().__init__(path, Peer)
        self.worker = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
        self.worker.start()

    def save(self, session="fixture"):
        Path(self.rollout).write_text(json.dumps({"type": "session_meta", "payload": {"id": session}}) + "\n" +
                                     json.dumps({"type": "event_msg", "payload": {"type": "thread_settings_applied",
                                         "thread_id": session, "thread_settings": self.saved}}) + "\n")

    def close(self):
        self.shutdown()
        self.server_close()
        self.worker.join()


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jc-")
        self.path = Path(self.temp.name)
        self.peer = Fixture(str(self.path / "control.sock"))
        binary = self.path / "codex"
        binary.write_text("#!" + sys.executable + "\nimport os,json,sys\nfrom pathlib import Path\n"
                          "with open(os.environ['FAKE_LOG'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
                          "if sys.argv[1:4]==['app-server','daemon','version']:\n"
                          " print(json.dumps({'status':'running' if Path(os.environ['FAKE_DAEMON_MARKER']).exists() else 'stopped','socketPath':os.environ['FAKE_DAEMON_SOCKET']}));sys.exit(0)\n"
                          "if sys.argv[1:4]==['app-server','daemon','start']:\n"
                          " Path(os.environ['FAKE_DAEMON_MARKER']).touch();sys.exit(0)\n"
                          "print('CODEX_QUEUED')\nsys.exit(int(os.environ.get('FAKE_EXIT','0')))\n")
        binary.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.path), CODEX_HOME=str(self.path / ".codex"),
                        JAMSESSION_CONFIG="/dev/null", JAMSESSION_CODEX_BIN=str(binary),
                        JAMSESSION_CWD=str(self.path), JAMSESSION_CODEX_CONTROL_SOCKET=str(self.path / "control.sock"),
                        JAMSESSION_PYTHON_BIN=sys.executable, JAMSESSION_CODEX_SANDBOX="on",
                        FAKE_LOG=str(self.path / "cli-calls"))
        for key in ("JAMSESSION_HOME", "JAMSESSION_ADAPTER_DIR", "JAMSESSION_PROMPT_LITERAL"):
            self.env.pop(key, None)

    def tearDown(self):
        self.peer.close()
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run([str(ROOT / "jamsession"), *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def methods(self):
        return [call["method"] for call in self.peer.calls if call["method"] != "initialize"]

    def test_message_rejoins_owner_and_sends_once_without_execution_overrides(self):
        text = 'literal $text "quotes"\n' + "x" * 70000 + "\n\n"
        result = self.cli("message", "codex", "fixture", text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.methods(), ["thread/read", "thread/queue/add"])
        self.assertEqual(self.peer.calls[-1]["params"]["input"][0]["text"], text)
        self.assertEqual(set(self.peer.calls[-1]["params"]), {"threadId", "input", "clientUserMessageId"})
        self.assertFalse((self.path / "cli-calls").exists())

    def test_steer_uses_native_turn_input_not_queue_or_kill(self):
        self.peer.scenario = "active"
        result = self.cli("codex", "fixture", "steer", "change direction")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.methods(), ["thread/read", "turn/start"])
        self.assertEqual(set(self.peer.calls[-1]["params"]), {"threadId", "input"})

    def test_idle_steer_uses_the_same_native_operation(self):
        self.assertEqual(self.cli("steer", "codex", "fixture", "start work").returncode, 0)
        self.assertEqual(self.methods(), ["thread/read", "turn/start"])

    def test_foreign_writer_keeps_its_native_queue_and_exit_status(self):
        self.peer.scenario = "busy"
        self.env["FAKE_EXIT"] = "7"
        result = self.cli("message", "codex", "fixture", "hello")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.methods(), ["thread/read", "thread/resume"])
        self.assertEqual(json.loads((self.path / "cli-calls").read_text()),
                         ["queue", "--thread", "fixture", "--message", "hello"])

    def test_foreign_writer_cannot_be_steered_by_a_second_controller(self):
        self.peer.scenario = "busy"
        self.assertEqual(self.cli("steer", "codex", "fixture", "redirect").returncode, 3)
        self.assertFalse((self.path / "cli-calls").exists())

    def test_denial_does_not_trigger_queue_or_resume_fallback(self):
        self.peer.scenario = "denied"
        result = self.cli("message", "codex", "fixture", "hello")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.methods(), ["thread/read", "thread/queue/add"])
        self.assertFalse((self.path / "cli-calls").exists())

    def test_uncertain_acceptance_is_not_retried(self):
        self.peer.scenario = "lost_ack"
        self.assertNotEqual(self.cli("message", "codex", "fixture", "hello").returncode, 0)
        self.assertEqual(self.methods(), ["thread/read", "thread/queue/add"])
        self.assertFalse((self.path / "cli-calls").exists())

    def test_control_resume_honors_read_and_returns_its_own_turn_result(self):
        result = self.cli("run", "codex", "fixture", "model", "high", "read", "continue")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "CONTROL_RESULT")
        params = self.peer.calls[-1]["params"]
        self.assertEqual(params["model"], "model")
        self.assertEqual(params["effort"], "high")
        self.assertEqual(params["sandboxPolicy"], {"type": "readOnly"})
        self.assertFalse((self.path / "cli-calls").exists())

    def test_resume_applies_explicit_settings_without_disabling_approval_policy(self):
        self.peer.scenario = "active"
        result = self.cli("run", "codex", "fixture", "model", "high", "read", "continue")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.methods(), ["thread/read", "thread/resume", "turn/start"])
        params = self.peer.calls[-1]["params"]
        self.assertEqual(params["sandboxPolicy"], {"type": "readOnly"})
        self.assertNotIn("approvalPolicy", params)
        self.assertNotIn("approvalsReviewer", params)

    def test_steer_rejects_execution_override_flags_before_connecting(self):
        self.assertEqual(self.cli("steer", "codex", "fixture", "hello", "--resume-with", "model", "high", "edit").returncode, 2)
        self.assertEqual(self.peer.calls, [])

    def test_unsupported_provider_steering_is_reported_without_a_run(self):
        self.assertEqual(self.cli("steer", "claude", "fixture", "hello").returncode, 3)
        self.assertEqual(self.peer.calls, [])

    def test_message_starts_only_the_native_daemon_when_needed(self):
        self.env.pop("JAMSESSION_CODEX_CONTROL_SOCKET")
        self.env["FAKE_DAEMON_MARKER"] = str(self.path / "daemon-started")
        self.env["FAKE_DAEMON_SOCKET"] = str(self.path / "control.sock")
        result = self.cli("message", "codex", "fixture", "start work")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (self.path / "cli-calls").read_text().splitlines()]
        self.assertEqual(calls, [["app-server", "daemon", "version"],
                                 ["app-server", "daemon", "start"],
                                 ["app-server", "daemon", "version"]])
        self.assertEqual(self.methods(), ["thread/read", "thread/queue/add"])

    def test_non_socket_endpoint_is_rejected_before_sending(self):
        self.env["JAMSESSION_CODEX_CONTROL_SOCKET"] = self.env["JAMSESSION_CODEX_BIN"]
        self.assertNotEqual(self.cli("message", "codex", "fixture", "hello").returncode, 0)
        self.assertEqual(self.peer.calls, [])

    def test_known_self_resume_is_rejected_before_waiting_on_itself(self):
        self.env["CODEX_THREAD_ID"] = "fixture"
        result = self.cli("run", "codex", "fixture", "model", "high", "read", "continue")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.peer.calls, [])

    def test_unloaded_message_restores_saved_read_only_and_approval_before_sending(self):
        self.peer.scenario = "cold"
        result = self.cli("message", "codex", "fixture", "start work")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.methods(), ["thread/read", "thread/resume", "thread/queue/add"])
        restore = self.peer.calls[-2]["params"]
        self.assertEqual(restore["sandbox"], "read-only")
        self.assertEqual(restore["approvalPolicy"], "on-request")
        self.assertEqual(restore["approvalsReviewer"], "guardian_subagent")
        self.assertEqual(restore["config"]["model_reasoning_effort"], "high")

    def test_custom_policy_is_not_downgraded_to_legacy_read_only(self):
        self.peer.scenario = "cold"
        self.peer.saved["permission_profile"]["file_system"]["entries"].append(
            {"path": {"type": "path", "path": "/private/secret"}, "access": "deny"})
        self.peer.save()
        result = self.cli("message", "codex", "fixture", "start work")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("custom permission profile", result.stderr)
        self.assertEqual(self.methods(), ["thread/read"])
        self.assertFalse((self.path / "cli-calls").exists())

    def test_provider_rollout_identity_must_match_target(self):
        self.peer.scenario = "cold"
        Path(self.peer.rollout).write_text(Path(self.peer.rollout).read_text().replace('"id": "fixture"', '"id": "other"'))
        self.assertEqual(self.cli("message", "codex", "fixture", "hello").returncode, 2)
        self.assertEqual(self.methods(), ["thread/read"])

    def test_unloaded_workspace_preserves_roots_temp_and_network_policy(self):
        self.peer.scenario = "cold"
        entries = self.peer.saved["permission_profile"]["file_system"]["entries"]
        entries.append({"path": {"type": "path", "path": str(self.path)}, "access": "write"})
        for protected in (".git", ".agents", ".codex", ".aws"):
            entries.append({"path": {"type": "path", "path": str(self.path / protected)},
                            "access": "read", "missing_path_behavior": "skip"})
        entries.append({"path": {"type": "special", "value": {"kind": "slash_tmp"}}, "access": "write"})
        self.peer.save()
        result = self.cli("message", "codex", "fixture", "hello")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.peer.calls[-2]["params"]["config"]
        self.assertEqual(config["sandbox_workspace_write.writable_roots"], [str(self.path)])
        self.assertFalse(config["sandbox_workspace_write.network_access"])
        self.assertTrue(config["sandbox_workspace_write.exclude_tmpdir_env_var"])
        self.assertFalse(config["sandbox_workspace_write.exclude_slash_tmp"])

    def test_settings_restore_mismatch_stops_before_prompt(self):
        self.peer.scenario = "cold"
        self.peer.resume_overrides = {"approvalPolicy": "never"}
        result = self.cli("message", "codex", "fixture", "hello")
        self.assertEqual(result.returncode, 2)
        self.assertIn("did not restore saved approvalPolicy", result.stderr)
        self.assertEqual(self.methods(), ["thread/read", "thread/resume"])

    def test_latest_native_settings_and_disabled_plugins_take_precedence(self):
        self.peer.scenario = "cold"
        self.peer.saved["disabled_plugin_ids"] = ["user-disabled-plugin"]
        self.peer.save()
        path = Path(self.peer.rollout)
        rows = path.read_text().splitlines()
        rows.insert(1, json.dumps({"type": "turn_context", "payload": {"model": "stale-model"}}))
        path.write_text("\n".join(rows) + "\n")
        result = self.cli("message", "codex", "fixture", "hello")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.methods(), ["thread/read", "thread/resume", "thread/settings/update", "thread/queue/add"])
        self.assertEqual(self.peer.calls[-3]["params"]["model"], "saved-model")
        self.assertEqual(self.peer.calls[-2]["params"]["disabledPluginIds"], ["user-disabled-plugin"])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve":
        fixture = Fixture(sys.argv[2], "busy")
        stopped = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopped.set())
        print("READY", flush=True)
        stopped.wait()
        fixture.close()
    else:
        unittest.main()
