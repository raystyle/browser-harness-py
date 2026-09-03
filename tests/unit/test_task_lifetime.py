"""Task lifetime: --once/--batch scoped teardown + persistent idle watchdog."""

import asyncio
import time
from types import SimpleNamespace

from browser_harness import admin, daemon, run


# --- --once/--batch: invocation-scoped teardown ---

def test_scope_flag_routes_dispatch_and_runs_teardown(monkeypatch):
    calls = {"dispatch": [], "teardown": 0}

    def fake_teardown():
        calls["teardown"] += 1

    monkeypatch.setattr(run, "_dispatch", lambda args: calls["dispatch"].append(args))
    monkeypatch.setattr(admin, "teardown_scoped_stack", fake_teardown)

    run._run(["--once", "browsers"])
    assert calls["dispatch"] == [["browsers"]]  # flag stripped before dispatch
    assert calls["teardown"] == 1

    run._run(["--batch", "--version"])
    assert calls["teardown"] == 2

    calls["dispatch"].clear()
    run._run(["browsers"])
    assert calls["dispatch"] == [["browsers"]]
    assert calls["teardown"] == 2  # default scope: no teardown


def test_scope_teardown_runs_even_when_command_fails(monkeypatch):
    monkeypatch.setattr(run, "_dispatch", lambda args: (_ for _ in ()).throw(SystemExit(3)))
    torn = []
    monkeypatch.setattr(admin, "teardown_scoped_stack", lambda: torn.append(1))
    try:
        run._run(["--once", "anything"])
    except SystemExit as e:
        assert e.code == 3
    assert torn == [1]


def test_teardown_stops_only_what_we_started(monkeypatch):
    events = []
    monkeypatch.setattr(admin, "restart_daemon", lambda nm=None: events.append("daemon"))
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("chrome"))
    monkeypatch.setattr(admin, "daemon_alive", lambda nm: False)

    # Cold stack, nothing ours: no-op.
    admin._launched_chrome_here = False
    admin._started_daemon_here = False
    admin.teardown_scoped_stack()
    assert events == []

    # Everything ours: both come down, flags reset.
    admin._launched_chrome_here = True
    admin._started_daemon_here = True
    admin.teardown_scoped_stack()
    assert events == ["daemon", "chrome"]
    assert admin._launched_chrome_here is False
    assert admin._started_daemon_here is False


def test_teardown_yields_chrome_to_another_live_daemon(monkeypatch):
    events = []
    monkeypatch.setattr(admin, "restart_daemon", lambda nm=None: events.append("daemon"))
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("chrome"))
    monkeypatch.setattr(admin, "daemon_alive", lambda nm: nm == "x-monitor")

    admin._launched_chrome_here = True
    admin._started_daemon_here = True
    try:
        admin.teardown_scoped_stack()
    finally:
        admin._launched_chrome_here = False
        admin._started_daemon_here = False
    assert events == ["daemon"]  # our daemon stops; shared Chrome stays


# --- persistent: idle watchdog ---

def test_idle_timeout_env_parsing(monkeypatch):
    monkeypatch.delenv("BH_IDLE_TIMEOUT", raising=False)
    assert daemon._idle_timeout() == 1800.0
    monkeypatch.setenv("BH_IDLE_TIMEOUT", "0")
    assert daemon._idle_timeout() == 0.0
    monkeypatch.setenv("BH_IDLE_TIMEOUT", "not-a-number")
    assert daemon._idle_timeout() == 1800.0


def test_idle_watchdog_fires_after_timeout(monkeypatch):
    monkeypatch.setenv("BH_IDLE_TIMEOUT", "1")
    d = SimpleNamespace(
        last_activity=time.monotonic() - 10,
        stop=asyncio.Event(),
        _idle_exit=False,
    )
    asyncio.run(asyncio.wait_for(daemon._idle_watchdog(d), timeout=5))
    assert d._idle_exit is True
    assert d.stop.is_set()


def test_idle_watchdog_disabled(monkeypatch):
    monkeypatch.setenv("BH_IDLE_TIMEOUT", "0")
    d = SimpleNamespace(last_activity=time.monotonic() - 10_000, stop=asyncio.Event(), _idle_exit=False)
    asyncio.run(asyncio.wait_for(daemon._idle_watchdog(d), timeout=5))
    assert d._idle_exit is False  # returned immediately, never fired


def test_idle_exit_closes_chrome_only_when_last_daemon(monkeypatch):
    events = []
    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(admin, "_pinned_agent_cdp", lambda env=None: True)
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("chrome"))

    # Another daemon (x-monitor stack) alive -> browser stays.
    monkeypatch.setattr(daemon.ipc, "ping", lambda name, timeout=1.0: name == "x-monitor")
    daemon._stop_agent_chrome_if_last()
    assert events == []

    # Last daemon standing -> agent Chrome closed.
    monkeypatch.setattr(daemon.ipc, "ping", lambda name, timeout=1.0: False)
    daemon._stop_agent_chrome_if_last()
    assert events == ["chrome"]


def test_idle_exit_never_touches_remote_browser_model(monkeypatch):
    events = []
    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(admin, "_pinned_agent_cdp", lambda env=None: False)  # user's browser
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("chrome"))
    monkeypatch.setattr(daemon.ipc, "ping", lambda name, timeout=1.0: False)
    daemon._stop_agent_chrome_if_last()
    assert events == []  # remote/user model: nothing we own
