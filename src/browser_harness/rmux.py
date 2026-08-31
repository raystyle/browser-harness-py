"""rmux integration: detect rmux and drive multiplexed browser script sessions.

The official Python SDK ``librmux`` 0.6.1 targets rmux 0.6.1 and is not
compatible with the installed rmux 0.10.0 (its ``start-server`` is a no-op on
Windows, and the default socket name embeds a per-process hash). This module
drives the ``rmux`` CLI directly -- the same thing the SDK does internally --
using a fixed ``-L <label>`` so a session's daemon is reachable across
processes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import _ipc as ipc


DEFAULT_LABEL = "browser-harness"


_USAGE = """usage: browser-harness rmux <command> [args]

Commands:
  list                        list sessions
  new <name> [--command C] [--cwd D]   create a detached session
  ensure <name> [--command C] [--cwd D]  create if missing
  status                      show server state and sessions
  send <name> <text>          send a shell command (text + Enter)
  keys <name> <key...>        send raw keys
  capture <name>              print pane content
  kill <name>                 kill a session
  version                     print rmux version
"""


def _parse_session_args(args):
    name = command = cwd = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--command":
            command = args[i + 1]
            i += 2
        elif a == "--cwd":
            cwd = args[i + 1]
            i += 2
        elif not a.startswith("--") and name is None:
            name = a
            i += 1
        else:
            i += 1
    return name, command, cwd


def rmux_binary():
    """Return ``(path, version)`` for the installed rmux, or ``None``."""
    path = shutil.which("rmux")
    if not path:
        win = Path.home() / "AppData" / "Local" / "rmux" / "bin" / "rmux.exe"
        if win.exists():
            path = str(win)
    if not path:
        return None
    version = None
    try:
        r = subprocess.run([path, "-V"], capture_output=True, text=True, timeout=10)
        version = (r.stdout or r.stderr).strip()
    except Exception:
        pass
    return path, version


class Rmux:
    """Thin, SDK-shaped wrapper over the ``rmux`` CLI."""

    def __init__(self, binary=None, label=None):
        det = rmux_binary() if binary is None else (str(binary), None)
        if not det or not det[0]:
            raise RuntimeError("rmux is not installed")
        self.binary, self.version = det
        self.label = label or os.environ.get("BH_RMUX_LABEL") or DEFAULT_LABEL

    def _argv(self, *args):
        return [self.binary, "-L", self.label, *[str(a) for a in args]]

    def _run(self, *args, check=False, capture=True, timeout=30):
        return subprocess.run(
            self._argv(*args),
            capture_output=capture,
            text=True,
            errors="replace",
            timeout=timeout,
            check=check,
        )

    def list_sessions(self):
        r = self._run("list-sessions", "-F", "#{session_name}")
        if r.returncode != 0:
            return []
        return [line for line in r.stdout.splitlines() if line.strip()]

    def server_running(self):
        """True when the daemon for this label is up (no session created)."""
        return self._run("list-sessions").returncode == 0

    def server_status(self):
        """Return ``{"running": bool, "sessions": [...]}`` for this label."""
        sessions = self.list_sessions()
        return {"running": bool(sessions) or self.server_running(), "sessions": sessions}

    def has_session(self, name):
        return self._run("has-session", "-t", name).returncode == 0

    def new_session(self, name, command=None, cwd=None, detached=True):
        args = ["new-session"]
        if detached:
            args.append("-d")
        args += ["-s", name]
        if cwd:
            args += ["-c", str(cwd)]
        if command:
            args.append(command)
        # The daemon inherits our pipes and keeps them open, so spawn detached.
        subprocess.Popen(
            self._argv(*args),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **ipc.spawn_kwargs(),
        )
        return name

    def ensure_session(self, name, command=None, cwd=None, ready_timeout=10.0):
        if self.has_session(name):
            return name
        self.new_session(name, command=command, cwd=cwd)
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            if self.has_session(name):
                return name
            time.sleep(0.2)
        raise RuntimeError(f"rmux session {name!r} did not become ready")

    def send_keys(self, target, *keys):
        return self._run("send-keys", "-t", target, *[str(k) for k in keys])

    def send_text(self, target, text):
        return self._run("send-keys", "-t", target, "-l", str(text))

    def send_command(self, target, text):
        self.send_text(target, text)
        return self.send_keys(target, "Enter")

    def capture_pane(self, target):
        try:
            r = self._run("capture-pane", "-p", "-t", target)
            return r.stdout if r.returncode == 0 else ""
        except Exception:
            return ""

    def kill_session(self, name):
        return self._run("kill-session", "-t", name)


def run_cli(args):
    if not args or args[0] in ("-h", "--help", "help"):
        print(_USAGE)
        return 0 if args else 2
    cmd, rest = args[0], args[1:]
    det = rmux_binary()
    if cmd == "version":
        if det:
            print(det[1] or "rmux (unknown version)")
            return 0
        print("rmux is not installed", file=sys.stderr)
        return 1
    if not det:
        print("rmux is not installed", file=sys.stderr)
        return 1
    r = Rmux()
    try:
        if cmd == "list":
            for s in r.list_sessions():
                print(s)
            return 0
        if cmd == "status":
            st = r.server_status()
            print("running:", st["running"])
            print("sessions:", ", ".join(st["sessions"]) or "(none)")
            return 0
        if cmd in ("new", "ensure"):
            name, command, cwd = _parse_session_args(rest)
            if not name:
                print("usage: browser-harness rmux new <name> [--command C] [--cwd D]", file=sys.stderr)
                return 2
            if cmd == "new":
                r.new_session(name, command=command, cwd=cwd)
            else:
                r.ensure_session(name, command=command, cwd=cwd)
            print(name)
            return 0
        if cmd == "send":
            if len(rest) < 2:
                print("usage: browser-harness rmux send <name> <text>", file=sys.stderr)
                return 2
            r.send_command(rest[0], rest[1])
            return 0
        if cmd == "keys":
            if len(rest) < 2:
                print("usage: browser-harness rmux keys <name> <key...>", file=sys.stderr)
                return 2
            r.send_keys(rest[0], *rest[1:])
            return 0
        if cmd == "capture":
            if len(rest) != 1:
                print("usage: browser-harness rmux capture <name>", file=sys.stderr)
                return 2
            sys.stdout.write(r.capture_pane(rest[0]))
            return 0
        if cmd == "kill":
            if len(rest) != 1:
                print("usage: browser-harness rmux kill <name>", file=sys.stderr)
                return 2
            r.kill_session(rest[0])
            return 0
        print(f"unknown rmux command: {cmd}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"rmux: {e}", file=sys.stderr)
        return 1
