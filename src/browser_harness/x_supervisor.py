"""rmux-backed supervisor for x_worker.py (self-healing X capture).

Self-heal = auto-detect anomaly + auto-alert + auto-recover:
  - detect: session alive? heartbeat fresh? worker output healthy?
  - alert:  log + stderr
  - recover: kill the session and respawn the worker in a fresh rmux pane

Run (standalone):  uv run python agent-workspace/x_supervisor.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from browser_harness.rmux import Rmux


_HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(_HERE, "x_worker.py")


def _data_dir():
    """Repo agent-workspace (dev) else per-user workspace dir (global install)."""
    repo = os.path.normpath(os.path.join(_HERE, "..", "..", "agent-workspace"))
    if os.path.isdir(repo):
        return repo
    from browser_harness.paths import workspace_dir

    return str(workspace_dir())


HEARTBEAT = os.environ.get("X_HEARTBEAT") or os.path.join(_data_dir(), "x_worker.heartbeat")
LOG = os.environ.get("X_SUPERVISOR_LOG") or os.path.join(_data_dir(), "x_supervisor.log")

SESSION = os.environ.get("X_RMUX_SESSION") or "x-monitor"
HEARTBEAT_TIMEOUT = float(os.environ.get("X_HEARTBEAT_TIMEOUT") or "120")
CHECK_INTERVAL = float(os.environ.get("X_CHECK_INTERVAL") or "15")
MAX_CHECKS = int(os.environ.get("X_MAX_CHECKS") or "0")  # 0 = run forever
SPAWN_GRACE = float(os.environ.get("X_SPAWN_GRACE") or "15")


def _alert(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _heartbeat_age():
    p = Path(HEARTBEAT)
    if not p.exists():
        return None
    try:
        return time.time() - p.stat().st_mtime
    except OSError:
        return None


def _spawn(rmux):
    cmd = f'"{sys.executable}" "{WORKER}"'
    rmux.ensure_session(SESSION, command=cmd, ready_timeout=20)
    _alert(f"worker spawned: session={SESSION} cmd={cmd}")
    time.sleep(SPAWN_GRACE)


def main():
    rmux = Rmux()
    _alert("supervisor started")
    _spawn(rmux)
    checks = 0
    while True:
        checks += 1
        if MAX_CHECKS and checks > MAX_CHECKS:
            break
        try:
            alive = rmux.has_session(SESSION)
            age = _heartbeat_age()
            if not alive:
                _alert(f"anomaly: session {SESSION!r} not alive -> recover")
                _spawn(rmux)
            elif age is None:
                _alert("anomaly: heartbeat missing -> recover")
                rmux.kill_session(SESSION)
                time.sleep(1.0)
                _spawn(rmux)
            elif age > HEARTBEAT_TIMEOUT:
                _alert(f"anomaly: heartbeat stale ({age:.0f}s > {HEARTBEAT_TIMEOUT:.0f}s) -> recover")
                rmux.kill_session(SESSION)
                time.sleep(1.0)
                _spawn(rmux)
            else:
                print(f"[supervisor] healthy (heartbeat {age:.0f}s ago)", flush=True)
        except Exception as e:
            _alert(f"supervisor error: {e!r}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
