"""Unified CLI entries for the agent-workspace apps."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_USAGE = """usage: browser-harness <command> [args]

Apps:
  x-monitor                 start the self-healing X capture supervisor
  x-search <...>            query/search stored tweets
  page-text <url|--current> extract clean text/markdown from a URL
  google-search <query> [--page N]  search Google in the logged-in browser
  bing-search <query> [--page N]    search Bing in the logged-in browser
"""

_SCRIPTS = {
    "x-search": "x_search.py",
    "page-text": "page_text.py",
}


def _workspace() -> Path:
    """Locate the agent-workspace: repo checkout > per-user dir (seeded once)."""
    import shutil

    env = os.environ.get("BH_AGENT_WORKSPACE")
    if env:
        return Path(env)

    repo_ws = Path(__file__).resolve().parents[2] / "agent-workspace"
    if (repo_ws / "x_supervisor.py").exists():
        return repo_ws

    # Global install: seed the per-user workspace from the bundled templates.
    from browser_harness.paths import workspace_dir

    user_ws = workspace_dir()
    bundled = Path(__file__).resolve().parent / "_agent_workspace"
    if bundled.is_dir():
        try:
            for p in bundled.glob("*.py"):
                shutil.copy2(p, user_ws / p.name)
        except OSError:
            pass
    return user_ws


def _run_script(cmd: str, rest: list[str]) -> int:
    script = _workspace() / _SCRIPTS[cmd]
    if not script.exists():
        print(f"app script not found: {script}", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(script), *rest])


def _decode_bing_target(url: str) -> str | None:
    """Decode the real target URL from a Bing ``ck/a`` redirect link."""
    import base64
    import re

    m = re.search(r"[?&]u=([^&]+)", url)
    if not m:
        return None
    try:
        s = m.group(1)
        s += "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s).decode("utf-8", "replace")
    except Exception:
        return None


def _run_monitor(rest: list[str]) -> int:
    """Ensure the self-healing supervisor runs in a rmux pane (non-blocking)."""
    from browser_harness.rmux import Rmux

    supervisor = _workspace() / "x_supervisor.py"
    if not supervisor.exists():
        print(f"supervisor not found: {supervisor}", file=sys.stderr)
        return 1
    try:
        Rmux().ensure_session(
            "x-supervisor",
            command=f'"{sys.executable}" "{supervisor}"',
            ready_timeout=20,
        )
    except Exception as e:
        print(f"failed to start x-monitor: {e}", file=sys.stderr)
        return 1
    print("x-monitor supervisor running in rmux session 'x-supervisor'")
    print("poll with: browser-harness rmux status / rmux capture x-supervisor")
    return 0


def _run_search(engine: str, rest: list[str]) -> int:
    page = 1
    qparts: list[str] = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--page":
            try:
                page = max(1, int(rest[i + 1]))
                i += 2
            except (IndexError, ValueError):
                print("usage: --page <int>", file=sys.stderr)
                return 2
        else:
            qparts.append(a)
            i += 1
    query = " ".join(qparts).strip()
    if not query:
        print(f"usage: browser-harness {engine}-search <query> [--page N]", file=sys.stderr)
        return 2
    from browser_harness.admin import ensure_daemon

    ensure_daemon()
    ws = _workspace()
    if str(ws) not in sys.path:
        sys.path.insert(0, str(ws))
    from agent_helpers import bing_search, extract_url_content, google_search

    rows = google_search(query, limit=5, page=page) if engine == "google" else bing_search(query, limit=5, page=page)
    for i, r in enumerate(rows, 1):
        url = r.get("url", "")
        title = r.get("title", "")
        print(f"[{i}] {title}")
        print(f"    {url}")
        desc = (r.get("description") or "").strip().replace("\n", " ")
        target = _decode_bing_target(url) if "bing.com/ck" in url else url
        if target and target.startswith("http") and i <= 3:
            try:
                content = extract_url_content(target, markdown=False, use_browser=False)
                text = (content.get("text") or "").strip().replace("\n", " ")
                if text:
                    print(f"    {text[:600]}")
                elif desc:
                    print(f"    {desc[:600]}")
            except Exception:
                if desc:
                    print(f"    {desc[:600]}")
    return 0


def run_cli(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print(_USAGE)
        return 0 if args else 2
    cmd, rest = args[0], args[1:]
    if cmd == "x-monitor":
        return _run_monitor(rest)
    if cmd in _SCRIPTS:
        return _run_script(cmd, rest)
    if cmd in ("google-search", "bing-search"):
        return _run_search(cmd.split("-", 1)[0], rest)
    print(f"unknown command: {cmd}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2
