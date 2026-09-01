"""Enumerate Chrome instances and their tabs (agent vs user, app-tab binding)."""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import urllib.request


_APP_TABS = {
    "x.com": "X",
    "google.com": "Google",
    "bing.com": "Bing",
}


def _chrome_instances_windows() -> list[dict]:
    """Return ``[{pid, data_dir, port}]`` for Chrome main processes."""
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -notmatch '--type=' } | "
        "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, errors="replace", timeout=20,
        ).stdout
    except Exception:
        return []
    instances = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        pid, cmd = line.split("|", 1)
        m_dir = re.search(r"--user-data-dir=\"([^\"]+)\"|--user-data-dir=([^\s]+)", cmd)
        m_prof = re.search(r"--profile-directory=\"([^\"]+)\"|--profile-directory=([^\s]+)", cmd)
        m_port = re.search(r"--remote-debugging-port=(\d+)", cmd)
        data_dir = (m_dir.group(1) or m_dir.group(2)) if m_dir else ((m_prof.group(1) or m_prof.group(2)) if m_prof else "default")
        port = int(m_port.group(1)) if m_port else None
        try:
            instances.append({"pid": int(pid), "data_dir": data_dir, "port": port})
        except ValueError:
            continue
    return instances


_MAIN_PROCESS_BASENAMES = (
    "chrome", "google-chrome", "google-chrome-stable", "google-chrome-beta",
    "google-chrome-unstable", "chromium", "chromium-browser",
    "microsoft-edge", "microsoft-edge-stable", "brave-browser", "brave",
)


def _chrome_instances_linux() -> list[dict]:
    """Return ``[{pid, data_dir, port}]`` for Chrome main processes via /proc.

    Mirrors the Windows CIM query: main processes only (no ``--type=`` child),
    same flag parsing, so the downstream agent/user classification is shared.
    """
    from pathlib import Path

    instances = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return []
    for proc in entries:
        if not proc.name.isdigit():
            continue
        try:
            raw = (proc / "cmdline").read_bytes()
        except OSError:
            continue
        argv = [a.decode("utf-8", errors="replace") for a in raw.split(b"\0") if a]
        # Chrome rewrites its own cmdline on Linux (canonicalized flags) and the
        # rewritten block is space-joined, not NUL-separated. `ps` shows one too.
        if len(argv) == 1 and " " in argv[0]:
            argv = argv[0].split()
        if not argv or Path(argv[0]).name.lower() not in _MAIN_PROCESS_BASENAMES:
            continue
        if any(a.startswith("--type=") for a in argv[1:]):
            continue  # renderer/gpu/utility child process
        data_dir = next((a.split("=", 1)[1] for a in argv if a.startswith("--user-data-dir=")), "default")
        port_raw = next((a.split("=", 1)[1] for a in argv if a.startswith("--remote-debugging-port=")), "")
        try:
            port = int(port_raw) if port_raw.isdigit() else None
            instances.append({"pid": int(proc.name), "data_dir": data_dir, "port": port})
        except ValueError:
            continue
    return sorted(instances, key=lambda i: i["pid"])


def _tabs_for_port(port: int) -> list[dict] | None:
    """Return page tabs via ``/json/list``, or ``None`` if unavailable."""
    try:
        r = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
    except Exception:
        return None
    return [t for t in r if t.get("type") == "page"]


def _port_live(port: int) -> bool:
    """True when something answers TCP on the port (an HTTP 404 still counts)."""
    import socket

    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _inspect_toggle_ports() -> list[dict]:
    """DevToolsActivePort files under the standard profile dirs.

    These ports come from the chrome://inspect remote-debugging toggle, not
    from command-line flags, so ``--remote-debugging-port`` parsing never sees
    them — the blind spot that makes a toggle-enabled user Chrome look
    unreachable while a daemon is actually riding it."""
    from browser_harness.daemon import profile_dirs

    out = []
    for base in profile_dirs():
        try:
            lines = (base / "DevToolsActivePort").read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        port = lines[0].strip() if lines else ""
        if not port.isdigit():
            continue
        out.append({"profile": str(base), "port": int(port), "live": _port_live(int(port))})
    return out


def _app_for_url(url: str) -> str:
    for key, name in _APP_TABS.items():
        if key in url:
            return name
    return "-"


def run_cli(args: list[str]) -> int:
    system = platform.system()
    if system == "Windows":
        instances = _chrome_instances_windows()
    elif system == "Linux":
        instances = _chrome_instances_linux()
    else:
        print("browsers: Windows/Linux enumeration only for now", file=sys.stderr)
        return 1
    print("browser-harness browsers")
    if not instances:
        print("  (no Chrome instances found)")
        return 0
    for inst in instances:
        kind = "agent" if "agent-chrome-profile" in inst["data_dir"] else "user"
        print(f"  [{kind}] pid={inst['pid']} profile={inst['data_dir']} port={inst['port'] or '-'}")
        tabs = _tabs_for_port(inst["port"]) if inst["port"] else None
        if tabs is None:
            print("        tabs: remote debugging not reachable on this instance")
            continue
        print(f"        {len(tabs)} tabs")
        for i, t in enumerate(tabs, 1):
            url = t.get("url") or ""
            title = (t.get("title") or "").strip().replace("\n", " ")
            app = _app_for_url(url)
            print(f"          {i}. [{app}] {title[:40]} — {url[:90]}")
    toggles = _inspect_toggle_ports()
    if toggles:
        print("  [inspect-toggle] DevToolsActivePort files (chrome://inspect toggle; not visible in the command line):")
        for t in toggles:
            state = "live" if t["live"] else "stale-file"
            print(f"        port={t['port']} {state:11s} {t['profile']}")
    # rmux 服务 / 会话 / 窗格
    try:
        from browser_harness.rmux import Rmux

        st = Rmux().server_status()
        print(f"  [rmux] running={st['running']} sessions={len(st['sessions'])} panes={len(st['panes'])}")
        for p in st["panes"]:
            print(f"          {p['session']}:{p['pane']}  {p['command']}")
    except Exception:
        print("  [rmux] unavailable")
    return 0


def run_current(args: list[str]) -> int:
    """Show the tab the daemon is currently operating on and its app."""
    from browser_harness.helpers import cdp, current_tab

    try:
        cur = current_tab()
    except Exception as e:
        print(f"browsers current: {e}", file=sys.stderr)
        return 1
    url = cur.get("url") or ""
    title = (cur.get("title") or "").strip().replace("\n", " ")
    app = _app_for_url(url)
    print("browser-harness current")
    print(f"  app:   {app}")
    print(f"  title: {title}")
    print(f"  url:   {url}")
    print(f"  target: {cur.get('targetId') or cur.get('target_id')}")
    # Debug-attach state: which tabs are CDP-attached, and which is current.
    try:
        pages = [t for t in cdp("Target.getTargets").get("targetInfos", []) if t.get("type") == "page"]
        attached = [t for t in pages if t.get("attached")]
        cur_id = cur.get("targetId") or cur.get("target_id")
        print(f"  attach: {len(attached)}/{len(pages)} tabs attached")
        for t in pages:
            tid = t.get("targetId", "")
            app = _app_for_url(t.get("url") or "")
            marker = "*" if tid == cur_id else " "
            print(f"    {marker} {tid[:14]} [{app}] attached={bool(t.get('attached'))}")
    except Exception:
        print("  attach: unavailable")
    return 0
