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
  google-search <query>     search Google in the logged-in browser
  bing-search <query>       search Bing in the logged-in browser
"""

_SCRIPTS = {
    "x-monitor": "x_supervisor.py",
    "x-search": "x_search.py",
    "page-text": "page_text.py",
}


def _workspace() -> Path:
    env = os.environ.get("BH_AGENT_WORKSPACE")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "agent-workspace"


def _run_script(cmd: str, rest: list[str]) -> int:
    script = _workspace() / _SCRIPTS[cmd]
    if not script.exists():
        print(f"app script not found: {script}", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(script), *rest])


def _run_search(engine: str, rest: list[str]) -> int:
    query = " ".join(rest).strip()
    if not query:
        print(f"usage: browser-harness {engine}-search <query>", file=sys.stderr)
        return 2
    from browser_harness.admin import ensure_daemon

    ensure_daemon()
    ws = _workspace()
    if str(ws) not in sys.path:
        sys.path.insert(0, str(ws))
    from agent_helpers import bing_search, extract_url_content, google_search

    rows = google_search(query, limit=5) if engine == "google" else bing_search(query, limit=5)
    for i, r in enumerate(rows, 1):
        url = r.get("url", "")
        title = r.get("title", "")
        print(f"[{i}] {title}")
        print(f"    {url}")
        if url.startswith("http") and i <= 3:
            try:
                content = extract_url_content(url, markdown=False, use_browser=False)
                text = (content.get("text") or "").strip().replace("\n", " ")
                print(f"    {text[:600]}")
            except Exception as e:
                print(f"    (extract failed: {e})")
    return 0


def run_cli(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print(_USAGE)
        return 0 if args else 2
    cmd, rest = args[0], args[1:]
    if cmd in _SCRIPTS:
        return _run_script(cmd, rest)
    if cmd in ("google-search", "bing-search"):
        return _run_search(cmd.split("-", 1)[0], rest)
    print(f"unknown command: {cmd}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2
