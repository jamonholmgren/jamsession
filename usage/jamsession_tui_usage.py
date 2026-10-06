#!/usr/bin/env python3
"""Read supported interactive /usage screens through a disposable local PTY."""

import codecs
import errno
import fcntl
import json
import math
import os
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
from datetime import datetime, timezone
from decimal import Decimal


class Screen:
    """The small ANSI subset used by the supported interactive usage screens."""

    def __init__(self, rows: int = 40, columns: int = 120) -> None:
        self.rows = rows
        self.columns = columns
        self.cells = [[" "] * columns for _ in range(rows)]
        self.row = 0
        self.column = 0
        self.saved_row = 0
        self.saved_column = 0

    def _scroll(self, count: int = 1) -> None:
        for _ in range(max(count, 1)):
            self.cells.pop(0)
            self.cells.append([" "] * self.columns)
        self.row = max(0, self.row - count)

    def _linefeed(self) -> None:
        self.row += 1
        if self.row >= self.rows:
            self._scroll(self.row - self.rows + 1)
            self.row = self.rows - 1

    def _put(self, char: str) -> None:
        if self.column >= self.columns:
            self.column = 0
            self._linefeed()
        self.cells[self.row][self.column] = char
        self.column += 1

    @staticmethod
    def _params(value: str) -> list[int]:
        values = value.lstrip("?>!").split(";")
        return [int(item) if item.isdigit() else 0 for item in values]

    def _erase_display(self, mode: int) -> None:
        if mode == 2:
            for line in self.cells:
                line[:] = [" "] * self.columns
        elif mode == 1:
            for line in self.cells[: self.row]:
                line[:] = [" "] * self.columns
            self.cells[self.row][: self.column + 1] = [" "] * (self.column + 1)
        else:
            self.cells[self.row][self.column :] = [" "] * (self.columns - self.column)
            for line in self.cells[self.row + 1 :]:
                line[:] = [" "] * self.columns

    def _erase_line(self, mode: int) -> None:
        if mode == 1:
            self.cells[self.row][: self.column + 1] = [" "] * (self.column + 1)
        elif mode == 2:
            self.cells[self.row][:] = [" "] * self.columns
        else:
            self.cells[self.row][self.column :] = [" "] * (self.columns - self.column)

    def _csi(self, parameters: str, final: str) -> None:
        values = self._params(parameters)
        first = values[0] if values else 0
        amount = first or 1
        if final in "Hf":
            self.row = max(0, min(self.rows - 1, (values[0] if values else 1) - 1))
            self.column = max(0, min(self.columns - 1, (values[1] if len(values) > 1 else 1) - 1))
        elif final == "A":
            self.row = max(0, self.row - amount)
        elif final == "B":
            self.row = min(self.rows - 1, self.row + amount)
        elif final == "C":
            self.column = min(self.columns - 1, self.column + amount)
        elif final == "D":
            self.column = max(0, self.column - amount)
        elif final == "E":
            self.row = min(self.rows - 1, self.row + amount)
            self.column = 0
        elif final == "F":
            self.row = max(0, self.row - amount)
            self.column = 0
        elif final == "G":
            self.column = max(0, min(self.columns - 1, amount - 1))
        elif final == "d":
            self.row = max(0, min(self.rows - 1, amount - 1))
        elif final == "J":
            self._erase_display(first)
        elif final == "K":
            self._erase_line(first)
        elif final == "S":
            self._scroll(amount)
        elif final == "s":
            self.saved_row, self.saved_column = self.row, self.column
        elif final == "u":
            self.row, self.column = self.saved_row, self.saved_column

    def feed(self, text: str) -> None:
        index = 0
        while index < len(text):
            char = text[index]
            index += 1
            if char == "\x1b":
                if index >= len(text):
                    break
                kind = text[index]
                index += 1
                if kind == "[":
                    start = index
                    while index < len(text) and not ("@" <= text[index] <= "~"):
                        index += 1
                    if index < len(text):
                        self._csi(text[start:index], text[index])
                        index += 1
                elif kind == "]":
                    while index < len(text) and text[index] not in "\a\x1b":
                        index += 1
                    if index < len(text) and text[index] == "\x1b" and index + 1 < len(text) and text[index + 1] == "\\":
                        index += 2
                    else:
                        index += 1
                elif kind in "78":
                    if kind == "7":
                        self.saved_row, self.saved_column = self.row, self.column
                    else:
                        self.row, self.column = self.saved_row, self.saved_column
                elif kind in "()":
                    index += 1
                continue
            if char == "\r":
                self.column = 0
            elif char in "\n\v\f":
                self._linefeed()
            elif char == "\b":
                self.column = max(0, self.column - 1)
            elif char >= " ":
                self._put(char)

    def text(self) -> str:
        return "\n".join("".join(line).rstrip() for line in self.cells)


def visible_usage(provider: str, screen: Screen) -> str | None:
    text = screen.text()
    if provider == "devin":
        quota = re.search(r"([^\n·]+)\s*·\s*(\d+(?:\.\d+)?)%\s+remaining\s*\(resets in ([^)\n]+)\)", text)
        if not quota or not 0 <= float(quota.group(2)) <= 100:
            return None
        used = Decimal(100) - Decimal(quota.group(2))
        return "\n".join((f"Subscription ({quota.group(1).strip()})", f"{used:f}% used", f"Resets: in {quota.group(3).strip()}"))
    if provider == "grok":
        # Grok can redraw the `l` in "limit" in an earlier terminal frame. The
        # completed screen still has the same modal and its unique tier label.
        limit = re.search(r"Weekly\s+(?:l)?imit\s*\(([^)]+)\)", text)
        reset = re.search(r"Resets:\s*([^\n]+)", text)
        if not limit or not reset:
            return None
        between = text[limit.end() : reset.start()]
        percent = re.search(r"\b(\d+(?:\.\d+)?)%", between)
        if not percent:
            return None
        reset_text = reset.group(1).rstrip(" │").strip()
        return "\n".join((f"Weekly limit ({limit.group(1)})", f"{percent.group(1)}% used", f"Resets: {reset_text}"))
    plan = re.search(r"\bPlan\s+(\d+(?:\.\d+)?)%\s+used\b", text)
    if plan:
        return "\n".join(("Plan", f"{plan.group(1)}% used"))
    return None


def visible_claude_models(screen: Screen) -> str | None:
    text = screen.text()
    if "Select model" not in text:
        return None
    choices = []
    for line in text.splitlines():
        match = re.match(r"\s*(?:❯\s*)?(\d+)\.\s+(.+?)\s*$", line)
        if match:
            parts = re.split(r"\s{2,}", match.group(2), maxsplit=1)
            label = re.sub(r"\s*(?:\([^)]*\)|✔).*", "", parts[0]).strip().lower()
            description = parts[1] if len(parts) == 2 else parts[0]
            choices.append(f"{label} - {description}")
    return "\n".join(choices) if len(choices) >= 2 and "Enter to set as default" in text else None


def command(provider: str, binary: str, directory: str) -> tuple[list[str], dict[str, str]]:
    environment = os.environ.copy()
    if provider == "grok":
        environment["TERM"] = "xterm-256color"
        environment["COLORTERM"] = "truecolor"
        return [binary, "--fullscreen", "--no-alt-screen"], environment
    if provider == "claude-models":
        environment["TERM"] = "xterm-256color"
        return [binary, "--permission-mode", "plan"], environment
    if provider == "devin":
        environment["TERM"] = "xterm-256color"
        return [binary, "--permission-mode", "auto", "--respect-workspace-trust", "false"], environment
    environment["TERM"] = "dumb"
    return [binary, "--screen-reader", "--mode", "plan", "-C", directory], environment


def muse_usage_text(usage: dict) -> str | None:
    """Only provider subscription observations count, never session tokens."""
    observed = usage.get("observedAtMs")
    if type(observed) is not int or observed <= 0:
        raise ValueError("invalid Muse observation timestamp")
    stamp = datetime.fromtimestamp(observed / 1000, timezone.utc).isoformat()
    rows = [f"Observed at: {stamp}"]
    for key, label in (("window", "Subscription window"), ("weekly", "Subscription weekly")):
        block = usage.get(key)
        if not isinstance(block, dict):
            raise ValueError("invalid Muse subscription window")
        used, reset = block.get("usedPercent"), block.get("resetsAtMs")
        if type(used) not in (int, float) or not math.isfinite(used) or used < 0 or type(reset) is not int:
            raise ValueError("invalid Muse subscription numbers")
        # Last-observed data can outlive a reset; do not invent the new balance.
        if reset <= time.time() * 1000:
            continue
        reset_text = datetime.fromtimestamp(reset / 1000, timezone.utc).isoformat()
        rows.extend((label, f"{Decimal(str(used)):f}% used", f"Resets: {reset_text}"))
    return "\n".join(rows) if len(rows) > 1 else None


def muse_usage(binary: str, timeout: int) -> int:
    """Use the documented MSP read method, with no session or model turn."""
    with tempfile.TemporaryDirectory(prefix="jamsession-muse-usage-") as directory:
        process = subprocess.Popen(
            [binary, "serve", "--no-session-log", "--disable-write", "--disable-shell"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=directory,
        )
        def send(frame: dict) -> None:
            process.stdin.write((json.dumps(frame) + "\n").encode())
            process.stdin.flush()
        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "jamsession", "version": "1"}}})
            deadline = time.monotonic() + timeout
            buffer = b""
            while time.monotonic() < deadline:
                ready, _, _ = select.select([process.stdout], [], [], max(0, min(0.2, deadline - time.monotonic())))
                if not ready:
                    continue
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    break
                buffer += data
                if len(buffer) > 1024 * 1024:
                    raise ValueError("Muse frame exceeds usage reader limit")
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    frame = json.loads(line)
                    if "error" in frame and frame.get("id") in (1, 2):
                        raise ValueError("Muse usage protocol request failed")
                    if frame.get("id") == 1:
                        if frame.get("result", {}).get("schema", {}).get("version") != 1:
                            raise ValueError("unsupported Muse protocol schema")
                        send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
                        send({"jsonrpc": "2.0", "id": 2, "method": "usage/read", "params": {}})
                    elif frame.get("id") == 2:
                        usage = frame.get("result", {}).get("usage")
                        if usage is None:
                            print("Muse has not observed subscription quota; no model call was made", file=sys.stderr)
                            return 3
                        if not isinstance(usage, dict):
                            raise ValueError("invalid Muse usage result")
                        text = muse_usage_text(usage)
                        if not text:
                            print("Muse has no unexpired subscription observation; no balance inferred", file=sys.stderr)
                            return 3
                        print(text)
                        return 0
            raise ValueError("Muse usage read timed out or host exited")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdin.close()
            process.stdout.close()


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in {"grok", "copilot", "claude-models", "devin", "muse"}:
        return 2
    provider, binary = sys.argv[1:3]
    try:
        timeout = max(1, int(sys.argv[3]))
    except ValueError:
        return 2
    if provider == "muse":
        try:
            return muse_usage(binary, timeout)
        except (OSError, ValueError, TypeError, OverflowError, AttributeError):
            print("Muse usage could not be read through its CLI protocol", file=sys.stderr)
            return 1
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    with tempfile.TemporaryDirectory(prefix="jamsession-usage-") as directory:
        process_command, environment = command(provider, binary, directory)
        try:
            process = subprocess.Popen(
                process_command,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                close_fds=True,
                cwd=directory if provider in {"claude-models", "devin"} else None,
                env=environment,
            )
        except OSError:
            os.close(master)
            os.close(slave)
            return 1
        os.close(slave)
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        screen = Screen()
        deadline = time.monotonic() + timeout
        send_usage_at = time.monotonic() + min(3, timeout / 2)
        accepted_trust = provider not in {"copilot", "claude-models"}
        sent_usage = False
        result = None
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], min(0.2, deadline - time.monotonic()))
                if ready:
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        break
                    if not data:
                        break
                    screen.feed(decoder.decode(data))
                    if b"\x1b[6n" in data:
                        os.write(master, f"\x1b[{screen.row + 1};{screen.column + 1}R".encode())
                    trust_text = screen.text()
                    trust_prompt = (
                        "Yes, I trust this folder" in trust_text
                        if provider == "claude-models"
                        else "Do you trust the files in this folder?" in trust_text
                    )
                    if not accepted_trust and trust_prompt:
                        # Ink-based TUIs can paint the prompt just before their
                        # input handler is ready. A short settle avoids choosing
                        # Claude's default "No, exit" option by racing startup.
                        time.sleep(0.5)
                        os.write(master, b"\x1b[B\r" if provider == "claude-models" else b"\r")
                        accepted_trust = True
                        send_usage_at = time.monotonic() + 3
                    result = visible_claude_models(screen) if provider == "claude-models" else visible_usage(provider, screen)
                    if result and (sent_usage or provider == "devin"):
                        break
                if provider != "devin" and accepted_trust and not sent_usage and time.monotonic() >= send_usage_at:
                    os.write(master, b"/model\r" if provider == "claude-models" else b"/usage\r")
                    sent_usage = True
            if result:
                print(result)
                return 0
            if os.environ.get("JAMSESSION_TUI_DEBUG"):
                print(screen.text(), file=sys.stderr)
            return 1
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            os.close(master)


if __name__ == "__main__":
    raise SystemExit(main())
