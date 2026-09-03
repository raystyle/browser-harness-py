"""Continuously detect whether there is an operable browser, auto-opening Chrome
when none is running.

"Operable" = a Chromium browser is running AND the daemon is connected to it
(remote debugging enabled). When no browser is running, it launches the user's
browser (same profile, honouring BH_NO_THROTTLE / BH_CHROME_EXTRA_FLAGS) and
keeps watching until the daemon connects.

Run:  uv run python browser-workspace/browser_watch.py
Env:  BW_INTERVAL (seconds between checks, default 10)
      BW_MAX_CHECKS (0 = run forever)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time


INTERVAL = float(os.environ.get("BW_INTERVAL") or "10")
MAX_CHECKS = int(os.environ.get("BW_MAX_CHECKS") or "0")
LAUNCH_COOLDOWN = float(os.environ.get("BW_LAUNCH_COOLDOWN") or "60")


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


def _operable(s):
    return bool(s and s.get("chrome_running") and s.get("daemon", {}).get("browser_ready"))


def _auto_open_browser():
    from browser_harness.admin import _launch_browser

    try:
        return _launch_browser() is not None
    except Exception:
        return False


def _detail(s):
    if not s:
        return "doctor failed"
    d = s.get("daemon", {})
    return (
        f"chrome_running={s.get('chrome_running')}, "
        f"daemon_alive={d.get('alive')}, "
        f"browser_ready={d.get('browser_ready')}"
    )


def main():
    prev = None
    checks = 0
    last_launch = 0.0
    print("[browser-watch] started", flush=True)
    while True:
        checks += 1
        if MAX_CHECKS and checks > MAX_CHECKS:
            break
        try:
            s = _doctor_json()
            op = _operable(s)
            if not op and time.time() - last_launch > LAUNCH_COOLDOWN:
                launched = _auto_open_browser()
                print(
                    f"[{time.strftime('%H:%M:%S')}] not operable -> auto-open "
                    f"{'ok' if launched else 'FAILED'}",
                    flush=True,
                )
                last_launch = time.time()
                s = _doctor_json()  # refresh after launch
                op = _operable(s)
            if op != prev:
                state = "OPERABLE" if op else "NOT-OPERABLE"
                print(f"[{time.strftime('%H:%M:%S')}] STATE CHANGE -> {state} ({_detail(s)})", flush=True)
                prev = op
            else:
                print(f"[{time.strftime('%H:%M:%S')}] {'operable' if op else 'not operable'} ({_detail(s)})", flush=True)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] error: {e!r}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
