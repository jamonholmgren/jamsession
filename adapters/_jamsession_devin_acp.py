#!/usr/bin/env python3
"""Devin ACP helper for the Jam Session Devin adapter.

Subcommands, all talking JSON-RPC over stdio to `<devin> acp`:

  create <devin-bin> <cwd>
      initialize, then session/new with the automation _meta, then a setup
      prompt cancelled immediately so the session row persists without a
      model reply. Prints the new session id on stdout.

  rename <devin-bin> <cwd> <session-id> <title>
      initialize, session/load, _cognition.ai/session/rename.

Diagnostics go to stderr; stdout carries only the answer. Any failure is a
nonzero exit so the caller can fall back to unflagged behaviour.
"""
import json
import os
import subprocess
import sys
import threading

SETUP_PROMPT = "Jam Session created this session. Your task arrives in the next message; do that task fully."

AUTOMATION_META = {
    "cognition.ai/isAutomation": True,
    "cognition.ai/sessionOrigin": "automation",
    "cognition.ai/automationId": "jamsession",
}

# Devin CLI refuses to run under an editor's ACP environment.
STRIP_ENV = ("ACP_BACKEND", "WINDSURF_IDE_TYPE", "WINDSURF_EXT_HOST_PID",
             "ELECTRON_RUN_AS_NODE")


def fail(message):
    sys.stderr.write("jamsession_devin_acp: %s\n" % message)
    sys.exit(1)


class ACP:
    def __init__(self, devin_bin):
        env = dict(os.environ)
        for key in STRIP_ENV:
            env.pop(key, None)
        try:
            self.proc = subprocess.Popen(
                [devin_bin, "acp"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=env)
        except OSError as e:
            fail("could not start %r acp: %s" % (devin_bin, e))
        self.next_id = 0
        self._buffer = b""

    def _send(self, message):
        try:
            self.proc.stdin.write((json.dumps(message) + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            fail("could not write to devin acp: %s" % e)

    # select() only sees kernel-buffered bytes; lines already pulled into a
    # buffered reader would time out even after the response arrived. Read the
    # raw descriptor so every byte is accounted for in our own buffer.
    def _readline(self, timeout):
        import select
        fd = self.proc.stdout.fileno()
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                line = self._buffer[:newline]
                self._buffer = self._buffer[newline + 1:]
                return line
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                return None
            chunk = os.read(fd, 65536)
            if not chunk:
                return None
            self._buffer += chunk

    def request(self, method, params, timeout=120):
        self.next_id += 1
        rid = self.next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method,
                    "params": params})
        while True:
            line = self._readline(timeout)
            if line is None:
                fail("devin acp closed or timed out during %s" % method)
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                continue
            if reply.get("id") != rid:
                continue
            if "error" in reply:
                fail("%s failed: %s" % (method, reply["error"]))
            return reply.get("result") or {}

    def notify(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def initialize(cli):
    cli.request("initialize", {
        "protocolVersion": 1,
        "clientCapabilities": {},
        "clientInfo": {"name": "jamsession", "version": "1"},
    })


def cmd_create(devin_bin, cwd):
    cli = ACP(devin_bin)
    try:
        initialize(cli)
        result = cli.request("session/new", {
            "cwd": cwd,
            "mcpServers": [],
            "_meta": AUTOMATION_META,
        })
        session_id = result.get("sessionId")
        if not session_id:
            fail("session/new returned no sessionId")

        # Persist the session row without a model reply: send the setup prompt
        # and an immediate cancel notification, then read until the prompt
        # response arrives.
        holder = {}

        def prompt():
            try:
                holder["result"] = cli.request(
                    "session/prompt",
                    {"sessionId": session_id,
                     "prompt": [{"type": "text", "text": SETUP_PROMPT}]},
                    timeout=300)
            except SystemExit:
                holder["failed"] = True

        worker = threading.Thread(target=prompt, daemon=True)
        worker.start()
        cli.notify("session/cancel", {"sessionId": session_id})
        worker.join(310)
        if holder.get("failed") or "result" not in holder:
            fail("setup prompt did not complete")
        print(session_id)
    finally:
        cli.close()


def cmd_rename(devin_bin, cwd, session_id, title):
    cli = ACP(devin_bin)
    try:
        initialize(cli)
        cli.request("session/load", {
            "sessionId": session_id,
            "cwd": cwd,
            "mcpServers": [],
        })
        cli.request("_cognition.ai/session/rename", {
            "sessionId": session_id,
            "title": title,
        })
    finally:
        cli.close()


def main():
    if len(sys.argv) < 3:
        fail("usage: _jamsession_devin_acp.py <create|rename> <devin-bin> ...")
    command, devin_bin = sys.argv[1], sys.argv[2]
    if command == "create" and len(sys.argv) == 4:
        cmd_create(devin_bin, sys.argv[3])
    elif command == "rename" and len(sys.argv) == 6:
        cmd_rename(devin_bin, sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        fail("usage: _jamsession_devin_acp.py create <devin-bin> <cwd>"
             " | rename <devin-bin> <cwd> <session-id> <title>")


if __name__ == "__main__":
    main()
