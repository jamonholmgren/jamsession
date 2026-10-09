"""Codex's native local control connection; no Jam Session daemon."""

import base64
import hashlib
import json
import os
import socket
import stat
import struct
import subprocess
import sys
import time
import uuid


class ControlError(Exception):
    pass


class ControlUnavailable(ControlError):
    pass


class RpcError(ControlError):
    def __init__(self, error):
        super().__init__(error.get("message", "Codex rejected the request"))
        self.code = error.get("code")


def control_socket(binary):
    if not hasattr(socket, "AF_UNIX") or not hasattr(os, "getuid"):
        raise ControlUnavailable("native Codex control needs Unix sockets (macOS, Linux or WSL)")
    configured = os.environ.get("JAMSESSION_CODEX_CONTROL_SOCKET")
    if configured:
        return configured
    try:
        result = subprocess.run(
            [binary, "app-server", "daemon", "version"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        daemon = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise ControlUnavailable("cannot discover Codex's running app server") from error
    if daemon.get("status") != "running" or not daemon.get("socketPath"):
        try:
            subprocess.run([binary, "app-server", "daemon", "start"],
                           capture_output=True, text=True, timeout=30, check=True)
            result = subprocess.run([binary, "app-server", "daemon", "version"],
                                    capture_output=True, text=True, timeout=10, check=True)
            daemon = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise ControlUnavailable("Codex's native local control server could not start") from error
        if daemon.get("status") != "running" or not daemon.get("socketPath"):
            raise ControlUnavailable("Codex has no running local control server")
    return daemon["socketPath"]


class Control:
    def __init__(self, path, timeout=15):
        if not os.path.isabs(path):
            raise ControlError("Codex control socket must be an absolute path")
        info = os.stat(path)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ControlError("Codex control endpoint must be a socket owned by this user")
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.timeout = timeout
        self.request_id = 0
        self.events = []
        self.deadline = time.monotonic() + timeout
        try:
            self.socket.settimeout(timeout)
            self.socket.connect(path)
            key = base64.b64encode(os.urandom(16)).decode()
            self.socket.sendall((
                "GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                "Connection: Upgrade\r\nSec-WebSocket-Key: " + key +
                "\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode())
            headers = b""
            while not headers.endswith(b"\r\n\r\n"):
                if len(headers) >= 16384:
                    raise ControlError("oversized Codex WebSocket handshake")
                headers += self.read(1)
            fields = {}
            for line in headers.decode("ascii").split("\r\n")[1:]:
                if ":" in line:
                    name, value = line.split(":", 1)
                    fields[name.lower()] = value.strip()
            expected = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
            ).digest()).decode()
            if not headers.startswith(b"HTTP/1.1 101 ") or fields.get("sec-websocket-accept") != expected:
                raise ControlError("Codex control endpoint rejected the WebSocket handshake")
            self.call("initialize", {
                "clientInfo": {"name": "jamsession", "title": "Jam Session", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            })
            self.send({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def close(self):
        self.socket.close()

    def read(self, count):
        data = bytearray()
        while len(data) < count:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex control request timed out; do not resend blindly")
            self.socket.settimeout(remaining)
            chunk = self.socket.recv(count - len(data))
            if not chunk:
                raise ControlError("Codex control connection closed; delivery may be uncertain")
            data.extend(chunk)
        return bytes(data)

    def frame(self, opcode, payload):
        mask = os.urandom(4)
        length = len(payload)
        if length < 126:
            header = bytes([0x80 | opcode, 0x80 | length])
        elif length <= 65535:
            header = bytes([0x80 | opcode, 0xfe]) + struct.pack("!H", length)
        else:
            header = bytes([0x80 | opcode, 0xff]) + struct.pack("!Q", length)
        self.socket.sendall(header + mask + bytes(
            byte ^ mask[index % 4] for index, byte in enumerate(payload)
        ))

    def send(self, message):
        self.frame(1, json.dumps(message, ensure_ascii=False).encode())

    def receive(self):
        message = bytearray()
        while True:
            first, second = self.read(2)
            opcode = first & 15
            length = second & 127
            if length == 126:
                length = struct.unpack("!H", self.read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.read(8))[0]
            if first & 0x70 or second & 0x80 or length + len(message) > 32 * 1024 * 1024:
                raise ControlError("invalid or oversized Codex WebSocket frame")
            payload = self.read(length)
            if opcode == 8:
                raise ControlError("Codex closed the connection; delivery may be uncertain")
            if opcode == 9:
                self.frame(10, payload)
                continue
            if opcode == 10:
                continue
            if opcode not in (0, 1) or (opcode == 0 and not message):
                raise ControlError("unexpected Codex WebSocket frame")
            message.extend(payload)
            if first & 0x80:
                return json.loads(message)

    def call(self, method, params):
        self.request_id += 1
        request_id = self.request_id
        self.deadline = time.monotonic() + self.timeout
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            message = self.receive()
            if message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    raise RpcError(message["error"])
                return message["result"]
            if "id" in message and "method" in message:
                self.send({"id": message["id"], "error": {
                    "code": -32601, "message": "Jam Session cannot answer interactive server requests",
                }})
            elif "method" in message:
                self.events.append(message)


def saved_resume_params(thread):
    """Use only the provider's exact rollout and saved, representable policy."""
    session = thread["id"]
    settings = None
    identity = None
    with open(thread["path"], encoding="utf-8") as rollout:
        for line in rollout:
            item = json.loads(line)
            payload = item.get("payload", {})
            if item.get("type") == "session_meta":
                identity = payload.get("id")
            elif item.get("type") == "turn_context":
                settings = payload
            elif (item.get("type") == "event_msg" and
                  payload.get("type") == "thread_settings_applied"):
                if payload.get("thread_id") != session:
                    raise ControlError("saved settings belong to another session")
                settings = payload["thread_settings"]
    if identity != session or not settings:
        raise ControlError("cannot verify saved session settings; no prompt was sent")
    cwd = settings["cwd"]
    profile = settings.get("permission_profile")
    root_read = {"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}
    config = {}
    if profile == {"type": "disabled"}:
        sandbox = "danger-full-access"
    elif (profile and set(profile) == {"type", "file_system", "network"} and
          profile.get("type") == "managed" and
          set(profile.get("file_system", {})) == {"type", "entries"} and
          profile.get("file_system", {}).get("type") == "restricted" and
          profile.get("network") in ("restricted", "enabled")):
        entries = profile["file_system"]["entries"]
        network = profile["network"] == "enabled"
        if entries == [root_read] and not network:
            sandbox = "read-only"
        else:
            roots = [entry["path"]["path"] for entry in entries
                     if entry.get("access") == "write" and entry.get("path", {}).get("type") == "path"]
            expected = [root_read]
            for path in roots:
                expected.append({"path": {"type": "path", "path": path}, "access": "write"})
                for protected in (".git", ".agents", ".codex", ".aws"):
                    expected.append({"path": {"type": "path", "path": os.path.join(path, protected)},
                                     "access": "read", "missing_path_behavior": "skip"})
            for special in ("slash_tmp", "tmpdir"):
                entry = {"path": {"type": "special", "value": {"kind": special}}, "access": "write"}
                if entry in entries:
                    expected.append(entry)
                config["sandbox_workspace_write.exclude_" + ("slash_tmp" if special == "slash_tmp" else "tmpdir_env_var")] = entry not in entries
            canonical = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
            if cwd not in roots or canonical(entries) != canonical(expected):
                raise ControlError("cannot safely restore this custom permission profile; use its owning controller")
            sandbox = "workspace-write"
            config["sandbox_workspace_write.writable_roots"] = roots
            config["sandbox_workspace_write.network_access"] = network
    else:
        raise ControlError("cannot safely restore this permission profile; use its owning controller")
    effort = settings.get("reasoning_effort", settings.get("effort"))
    if effort is not None:
        config["model_reasoning_effort"] = effort
    params = {
        "threadId": session, "excludeTurns": True, "cwd": cwd,
        "model": settings["model"], "sandbox": sandbox,
        "approvalPolicy": settings["approval_policy"],
        "approvalsReviewer": settings["approvals_reviewer"], "config": config,
    }
    provider = settings.get("model_provider_id", thread.get("modelProvider"))
    if provider:
        params["modelProvider"] = provider
    if "service_tier" in settings:
        params["serviceTier"] = settings["service_tier"]
    if settings.get("runtime_workspace_roots") is not None:
        params["runtimeWorkspaceRoots"] = settings["runtime_workspace_roots"]
    return params, settings


def join_thread(client, session, subscribe=False):
    thread = client.call("thread/read", {"threadId": session, "includeTurns": False})["thread"]
    if thread["id"] != session:
        raise ControlError("Codex returned another session")
    if thread["status"]["type"] != "notLoaded":
        if subscribe:
            # Rejoining a thread already owned by this server retains its settings.
            client.call("thread/resume", {"threadId": session, "excludeTurns": True})
        return
    params, settings = saved_resume_params(thread)
    result = client.call("thread/resume", params)
    for key in ("model", "cwd", "approvalPolicy", "approvalsReviewer"):
        if result[key] != params[key]:
            raise ControlError("Codex did not restore saved " + key + "; no prompt was sent")
    expected = {"read-only": "readOnly", "workspace-write": "workspaceWrite",
                "danger-full-access": "dangerFullAccess"}[params["sandbox"]]
    if result["sandbox"]["type"] != expected:
        raise ControlError("Codex did not restore saved sandbox; no prompt was sent")
    if expected == "readOnly" and result["sandbox"].get("networkAccess", False):
        raise ControlError("Codex enabled network access; no prompt was sent")
    if expected == "workspaceWrite":
        for key, config_key in (("networkAccess", "network_access"),
                                ("excludeTmpdirEnvVar", "exclude_tmpdir_env_var"),
                                ("excludeSlashTmp", "exclude_slash_tmp")):
            if result["sandbox"][key] != params["config"]["sandbox_workspace_write." + config_key]:
                raise ControlError("Codex did not restore saved sandbox " + key + "; no prompt was sent")
        if set(result["sandbox"]["writableRoots"]) | {params["cwd"]} != set(params["config"]["sandbox_workspace_write.writable_roots"]):
            raise ControlError("Codex changed writable roots; no prompt was sent")
    effort = settings.get("reasoning_effort", settings.get("effort"))
    if effort is not None and result["reasoningEffort"] != effort:
        raise ControlError("Codex did not restore saved effort; no prompt was sent")
    updates = {"threadId": session}
    if settings.get("collaboration_mode") is not None:
        updates["collaborationMode"] = settings["collaboration_mode"]
    if "disabled_plugin_ids" in settings:
        updates["disabledPluginIds"] = settings["disabled_plugin_ids"]
    if len(updates) > 1:
        client.call("thread/settings/update", updates)


def resume_run(binary, session, prompt, model, effort, access):
    client = Control(control_socket(binary))
    try:
        join_thread(client, session, subscribe=True)
        cwd = os.path.abspath(os.environ.get("JAMSESSION_CWD", os.getcwd()))
        if os.environ.get("JAMSESSION_CODEX_SANDBOX", "on") == "off":
            sandbox = {"type": "dangerFullAccess"}
        elif access == "read":
            sandbox = {"type": "readOnly"}
        else:
            sandbox = {"type": "workspaceWrite", "writableRoots": [cwd], "networkAccess": False}
        params = {
            "threadId": session, "input": [{"type": "text", "text": prompt}],
            "cwd": cwd, "sandboxPolicy": sandbox,
        }
        if model != "default":
            params["model"] = model
        if effort != "default":
            params["effort"] = effort
        turn = client.call("turn/start", params)["turn"]
        print("delivery: turn started", file=sys.stderr)
        final_text = ""
        while True:
            client.deadline = time.monotonic() + 3600
            event = client.events.pop(0) if client.events else client.receive()
            params = event.get("params", {})
            if "id" in event and "method" in event:
                client.send({"id": event["id"], "error": {
                    "code": -32601, "message": "Jam Session cannot answer interactive server requests",
                }})
            if params.get("threadId") != session or params.get("turnId", params.get("turn", {}).get("id")) != turn["id"]:
                continue
            if event.get("method") == "item/completed":
                item = params.get("item", {})
                if item.get("type") == "agentMessage" and item.get("phase") != "commentary":
                    final_text = item.get("text", "")
            if event.get("method") == "turn/completed":
                completed = params["turn"]
                if final_text:
                    print(final_text)
                if completed["status"] != "completed":
                    raise ControlError("Codex turn " + completed["status"] + ": " + str(completed.get("error")))
                return 0
    finally:
        client.close()


def deliver(binary, intent, session, prompt):
    client = Control(control_socket(binary))
    try:
        try:
            join_thread(client, session)
        except RpcError as error:
            if error.code == -32600 and "already has an active writer" in str(error):
                print("delivery: another process owns this session", file=sys.stderr)
                return 4
            raise
        user_input = [{"type": "text", "text": prompt}]
        if intent == "steer":
            turn = client.call("turn/start", {"threadId": session, "input": user_input})["turn"]
            print("delivery: turn accepted", file=sys.stderr)
            print("turn: " + turn["id"], file=sys.stderr)
            return 0
        queued = client.call("thread/queue/add", {
            "threadId": session, "input": user_input,
            "clientUserMessageId": str(uuid.uuid4()),
        })["queuedSubmission"]
        print("Queued message " + queued["id"] + " for thread " + session + ".", flush=True)
        print("delivery: native queue accepted; Codex starts it automatically when idle", file=sys.stderr)
        return 0
    finally:
        client.close()


def main():
    if not ((len(sys.argv) == 4 and sys.argv[2] in ("message", "steer")) or
            (len(sys.argv) == 7 and sys.argv[2] == "run")):
        print("usage: _jamsession_codex_control.py <codex-bin> <message|steer|run> <session> [model effort access]", file=sys.stderr)
        return 2
    prompt = sys.stdin.read()
    if not prompt:
        print("jamsession_codex: message text must not be empty", file=sys.stderr)
        return 2
    if sys.argv[2] == "run" and (not sys.argv[4] or not sys.argv[5] or sys.argv[6] not in ("read", "edit")):
        print("jamsession_codex: run requires model, effort and read|edit access", file=sys.stderr)
        return 2
    try:
        if sys.argv[2] == "run":
            return resume_run(sys.argv[1], sys.argv[3], prompt, *sys.argv[4:])
        return deliver(sys.argv[1], sys.argv[2], sys.argv[3], prompt)
    except ControlUnavailable as error:
        print("jamsession_codex: " + str(error), file=sys.stderr)
        return 3
    except (ControlError, OSError, ValueError, KeyError) as error:
        print("jamsession_codex: " + str(error), file=sys.stderr)
        print("No fallback or retry was attempted; inspect the target before resending.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
