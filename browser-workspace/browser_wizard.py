"""Wizard-style progressive browser + app-tab setup with reminders.

Steps: 1) Chrome running, 2) remote debugging enabled, 3) daemon connected,
4) one tab per app (X / Google / Bing). Each step detects, auto-fixes what it
can, and reminds the user for what only they can do (toggle / click Allow).

Run:  uv run python browser-workspace/browser_wizard.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import webbrowser


def _doctor_json():
    r = subprocess.run(
        [sys.executable, "-m", "browser_harness.run", "doctor", "--json"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=40,
    )
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def _chrome_running():
    s = _doctor_json()
    return bool(s and s.get("chrome_running"))


def _browser_ready():
    s = _doctor_json()
    return bool(s and s.get("daemon", {}).get("browser_ready"))


def _remote_debugging_enabled():
    try:
        from browser_harness.daemon import remote_debugging_toggle_profiles

        return bool(remote_debugging_toggle_profiles())
    except Exception:
        return False


def _auto_open():
    try:
        from browser_harness.admin import _launch_browser

        return _launch_browser() is not None
    except Exception:
        return False


def _run_browser(script, timeout=60):
    try:
        r = subprocess.run(
            [sys.executable, "-m", "browser_harness.run"],
            input=script,
            text=True,
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        return r.stdout
    except Exception as e:
        return f"error: {e!r}"


def _wait(cond, seconds, interval=1):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(interval)
    return False


def main():
    print("== browser-harness setup wizard ==", flush=True)

    if not _chrome_running():
        print("[1/5] Chrome not running -> auto-opening...", flush=True)
        _auto_open()
        if not _wait(_chrome_running, 20):
            print("  [REMIND] Chrome didn't open. Open it manually, then rerun.", flush=True)
            return 1
    print("[1/5] Chrome running: ok", flush=True)

    if not _remote_debugging_enabled():
        print("[2/5] Remote debugging not enabled.", flush=True)
        print("  [REMIND] Enable chrome://inspect/#remote-debugging -> 'Allow remote debugging'.", flush=True)
        webbrowser.open("chrome://inspect/#remote-debugging")
        if not _wait(_remote_debugging_enabled, 60, 2):
            print("  [REMIND] Still not enabled. Tick the toggle, then rerun.", flush=True)
            return 1
    print("[2/5] Remote debugging enabled: ok", flush=True)

    if not _browser_ready():
        print("[3/5] Connecting daemon (click 'Allow remote debugging?' if Chrome asks).", flush=True)
        _run_browser("print(page_info())")
        if not _wait(_browser_ready, 30, 1):
            print("  [REMIND] Click 'Allow remote debugging?' in Chrome, then rerun.", flush=True)
            return 1
    print("[3/5] Daemon connected: ok", flush=True)

    print("[4/5] Setting up app tabs (X / Google / Bing)...", flush=True)
    out = _run_browser("print(setup_browser_apps())")
    print("  tabs: " + " ".join(out.strip().split())[:240], flush=True)

    print("[5/5] Scanning tabs for Cloudflare / anti-bot blocks...", flush=True)
    out = _run_browser("import json; print(json.dumps(scan_tabs_for_blocks(), ensure_ascii=False))")
    try:
        blocks = json.loads(out.strip().splitlines()[-1])
    except Exception:
        blocks = {}
    if blocks:
        print("  [ALERT] blocked tabs detected:", flush=True)
        for url, sigs in blocks.items():
            print(f"    {url[:90]} -> {sigs}", flush=True)
    else:
        print("  no blocks detected", flush=True)

    print("DONE — browser operable, one tab per app.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
