"""Built-in app subcommands (X monitor / search / page text)."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


_USAGE = """usage: browser-harness <command> [args]

Apps:
  x-monitor                 start isolated Chrome + self-healing X capture
  x-search <...>            query/search stored tweets
  web-fetch <url|--current> extract clean text/markdown from a URL
  google-search <query> [--page N]  search Google in the logged-in browser
  bing-search <query> [--page N]    search Bing in the logged-in browser
"""

_AGENT_PORT = 9223
_NO_THROTTLE_FLAGS = (
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion",
)


def _agent_profile() -> Path:
    raw = os.environ.get("BH_AGENT_CHROME_PROFILE")
    if raw:
        return Path(raw).expanduser().resolve()
    from browser_harness.paths import home_dir

    return home_dir() / "agent-chrome-profile"


def _agent_chrome_running() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{_AGENT_PORT}/json/version", timeout=2)
        return True
    except Exception:
        return False


def _chrome_path() -> str | None:
    import shutil

    for key in ("BH_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if raw and Path(raw).expanduser().is_file():
            return raw
    if platform.system() == "Windows":
        for c in (
            r"C:\Program Files\Google\Chrome Dev\Application\chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ):
            if Path(c).exists():
                return c
        return shutil.which("chrome")
    if platform.system() == "Darwin":
        p = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return p if Path(p).exists() else shutil.which("google-chrome")
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")


def _launch_agent_chrome() -> bool:
    if _agent_chrome_running():
        return True
    chrome = _chrome_path()
    if not chrome:
        return False
    flags = [
        f"--user-data-dir={_agent_profile()}",
        f"--remote-debugging-port={_AGENT_PORT}",
        *_NO_THROTTLE_FLAGS,
    ]
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", "-na", "Google Chrome", "--args", *flags])
        else:
            subprocess.Popen([chrome, *flags], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    deadline = time.time() + 20
    while time.time() < deadline:
        if _agent_chrome_running():
            return True
        time.sleep(0.5)
    return False


def _decode_bing_target(url: str) -> str | None:
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
    import browser_harness
    from browser_harness.rmux import Rmux

    if not _launch_agent_chrome():
        print(f"failed to launch the isolated agent Chrome (port {_AGENT_PORT})", file=sys.stderr)
        return 1
    os.environ["BU_CDP_URL"] = f"http://127.0.0.1:{_AGENT_PORT}"
    # The X stack drives the browser through its own daemon so capture rounds
    # never race ad-hoc CLI scripts for the default daemon's tab attachment.
    os.environ.setdefault("BU_NAME", "x-monitor")
    supervisor = Path(browser_harness.__file__).parent / "x_supervisor.py"
    try:
        Rmux().ensure_session(
            "x-supervisor",
            command=f'"{sys.executable}" "{supervisor}"',
            ready_timeout=20,
        )
    except Exception as e:
        print(f"failed to start x-monitor: {e}", file=sys.stderr)
        return 1
    print(f"x-monitor running (isolated Chrome on {_AGENT_PORT}, rmux session 'x-supervisor')")
    print("poll: browser-harness rmux status / rmux capture x-supervisor")
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
    from browser_harness.agent_helpers import bing_search, extract_url_content, google_search

    ensure_daemon()
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
    if cmd == "x-search":
        from browser_harness import x_search

        return x_search.main(rest) or 0
    if cmd == "web-fetch":
        from browser_harness import web_fetch

        return web_fetch.main(rest) or 0
    if cmd in ("google-search", "bing-search"):
        return _run_search(cmd.split("-", 1)[0], rest)
    print(f"unknown command: {cmd}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2
