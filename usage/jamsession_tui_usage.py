#!/usr/bin/env python3
"""Read supported interactive /usage screens through a disposable local PTY."""

import codecs
import errno
import fcntl
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


def command(provider: str, binary: str, directory: str) -> tuple[list[str], dict[str, str]]:
    environment = os.environ.copy()
    if provider == "grok":
        environment["TERM"] = "xterm-256color"
        environment["COLORTERM"] = "truecolor"
        return [binary, "--fullscreen", "--no-alt-screen"], environment
    environment["TERM"] = "dumb"
    return [binary, "--screen-reader", "--mode", "plan", "-C", directory], environment


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in {"grok", "copilot"}:
        return 2
    provider, binary = sys.argv[1:3]
    try:
        timeout = max(1, int(sys.argv[3]))
    except ValueError:
        return 2
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    with tempfile.TemporaryDirectory(prefix="jamsession-usage-") as directory:
        process_command, environment = command(provider, binary, directory)
        try:
            process = subprocess.Popen(process_command, stdin=slave, stdout=slave, stderr=slave, close_fds=True, env=environment)
        except OSError:
            os.close(master)
            os.close(slave)
            return 1
        os.close(slave)
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        screen = Screen()
        deadline = time.monotonic() + timeout
        send_usage_at = time.monotonic() + min(3, timeout / 2)
        accepted_trust = provider != "copilot"
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
                    if not accepted_trust and "Do you trust the files in this folder?" in screen.text():
                        os.write(master, b"\r")
                        accepted_trust = True
                    result = visible_usage(provider, screen)
                    if sent_usage and result:
                        break
                if not sent_usage and time.monotonic() >= send_usage_at:
                    os.write(master, b"/usage\r")
                    sent_usage = True
            if result:
                print(result)
                return 0
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
