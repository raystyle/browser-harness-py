"""Launch the self-healing X capture supervisor (workspace app).

Starts the isolated agent Chrome (if needed), pins this stack to it via
BU_CDP_URL, and ensures the supervisor's rmux session. Non-blocking.

Run:   browser-harness x-monitor
Poll:  browser-harness rmux status / rmux capture x-supervisor
Stop:  browser-harness rmux kill x-supervisor   (kills the worker pane too)
"""

import os
import sys
from pathlib import Path

# Dedicated daemon so capture rounds never race ad-hoc CLI scripts.
os.environ.setdefault("BU_NAME", "x-monitor")


def main() -> int:
    from browser_harness.admin import _AGENT_PORT, _launch_agent_chrome
    from browser_harness.rmux import Rmux

    if not _launch_agent_chrome():
        print(f"failed to launch the isolated agent Chrome (port {_AGENT_PORT})", file=sys.stderr)
        return 1
    os.environ["BU_CDP_URL"] = f"http://127.0.0.1:{_AGENT_PORT}"
    # Under app routing, __file__ is the runner's path — APP_FILE is this app's.
    me = Path(globals().get("APP_FILE", __file__))
    supervisor = me.with_name("x-supervisor.py")
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


raise SystemExit(main())
