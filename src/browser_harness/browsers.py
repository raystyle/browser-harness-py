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


def _tabs_for_port(port: int) -> list[dict] | None:
    """Return page tabs via ``/json/list``, or ``None`` if unavailable."""
    try:
        r = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
    except Exception:
        return None
    return [t for t in r if t.get("type") == "page"]


def _app_for_url(url: str) -> str:
    for key, name in _APP_TABS.items():
        if key in url:
            return name
    return "-"


def run_cli(args: list[str]) -> int:
    if platform.system() != "Windows":
        print("browsers: Windows enumeration only for now", file=sys.stderr)
        return 1
    instances = _chrome_instances_windows()
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
