"""Task-scoped browser isolation: --once/--batch get their own browser stack.

User-directed model (2026-09-04): each task operates its own browser, never
multiple tasks jockeying tabs on one shared Chrome. An invocation-scoped task
therefore gets a dedicated stack — BU_NAME, debug port, and a best-effort
clone of the base login profile — torn down entirely at invocation end.

Opt-outs: an explicit --shared flag, or a pinned stack (BU_NAME / BU_CDP_URL /
BU_CDP_WS already set — monitoring stacks, remote-browser models).

The task stack pins itself via BU_CDP_URL=http://127.0.0.1:<port> — the same
"dedicated automation Chrome" contract dev/x-monitor stacks use — so the
daemon can only ever reach this task's browser, never the user's Chrome
(local-mode discovery hunts user profiles and 9222/9223, which is exactly
what a task stack must not do).

apply_from_argv() MUST run before admin/helpers are imported: they bind
BU_NAME and the agent port/profile at import time. run.py calls it at module
top, ahead of every browser_harness import.
"""
import os
import shutil
import socket
import sys
import uuid
from pathlib import Path

from . import _ipc as ipc

# 9223 = installed stack, 9224 = WSL, 9225 = Windows dev (R006); tasks take
# 9230+ so a task browser can never collide with a named stack.
_PORT_RANGE = range(9230, 9261)
_IGNORE = shutil.ignore_patterns(
    "*Cache*", "Service Worker", "blob_storage", "Crashpad", "Singleton*"
)
# Held for process lifetime: the kernel drops it when we exit, so a reserved
# port can never be double-picked (bind-probe-then-close is TOCTOU — two
# concurrent tasks both saw 9230 free and the loser's daemon attached the
# winner's Chrome, silently un-isolating them).
_PORT_FD = None


def _load_env_files():
    """Same .env chain helpers/daemon/admin load — the pin check below must
    see the env the daemon will actually run with (a dev checkout pins its
    stack via <BH_HOME>/.env, which normal imports haven't loaded yet)."""
    from . import paths

    for p in (paths.home_dir() / ".env", paths.workspace_dir() / ".env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def apply_from_argv(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("--once", "--batch"):
        return
    if "--shared" in argv:
        return
    from . import paths

    _load_env_files()
    if any(os.environ.get(k) for k in ("BU_NAME", "BU_CDP_URL", "BU_CDP_WS")):
        return  # caller (or .env) pinned a stack — isolation would detach them from it

    name = "task-" + uuid.uuid4().hex[:8]
    profile = paths.home_dir() / "task-profiles" / name
    _clone_profile(_base_profile(), profile)
    os.environ["BU_NAME"] = name
    reserved = _reserve_port()
    if reserved is None:
        return  # no free slot in the task range — fall back to the shared
        # stack (the launch lock serializes callers there) rather than fail.
    port, fd = reserved
    os.environ["BH_AGENT_CDP_PORT"] = str(port)
    os.environ["BH_AGENT_CHROME_PROFILE"] = str(profile)
    os.environ["BU_CDP_URL"] = f"http://127.0.0.1:{port}"
    os.environ["BH_ISOLATED_TASK"] = "1"
    # A task browser starts cold (fresh clone, first run) — ordinary round
    # trips brush the 5s default until it warms. setdefault: user wins.
    os.environ.setdefault("BH_IPC_TIMEOUT", "10")


def _reserve_port():
    """Pick and kernel-reserve a task port. Returns (port, fd) — keep the fd
    open for the process lifetime, or the reservation evaporates."""
    global _PORT_FD
    for port in _PORT_RANGE:
        fd, _holder = ipc.acquire_lock(f"task-port-{port}")
        if fd is None:
            continue  # another task reserved it
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                os.close(fd)  # a non-task listener owns it
                continue
        _PORT_FD = fd
        return port, fd
    return None


def _base_profile():
    """Profile whose login state the task clone carries."""
    raw = (os.environ.get("BH_AGENT_CHROME_PROFILE") or "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_dir() else None
    from . import paths

    return paths.home_dir() / "agent-chrome-profile"


def _tolerant_copy(src, dst, *, follow_symlinks=True):
    """copy2 that skips locked files instead of aborting the whole clone —
    the base Chrome may be running while we copy (Windows holds some files).
    A missing file degrades that one thing to fresh-profile behavior."""
    try:
        return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
    except OSError:
        try:
            Path(dst).touch()
        except OSError:
            pass
        return dst


def _clone_profile(src, dst) -> None:
    if not src or not src.is_dir():
        return  # nothing to carry; the task starts with a fresh profile
    try:
        shutil.copytree(src, dst, ignore=_IGNORE, copy_function=_tolerant_copy)
    except OSError:
        pass  # partial clone is fine — Chrome fills any gaps on first launch
    # A stale DevToolsActivePort would point recovery at a dead port.
    try:
        (dst / "DevToolsActivePort").unlink()
    except OSError:
        pass
