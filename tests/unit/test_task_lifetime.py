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
    monkeypatch.delenv("BH_ISOLATED_TASK", raising=False)

    # Cold stack, nothing ours: no-op.
    admin._launched_chrome_here = False
    admin._started_daemon_here = False
    admin.teardown_scoped_stack()
    assert events == []

    # Everything ours: both come down — chrome first (graceful close rides on
    # the still-live daemon), then the daemon — flags reset.
    admin._launched_chrome_here = True
    admin._started_daemon_here = True
    admin.teardown_scoped_stack()
    assert events == ["chrome", "daemon"]
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

    async def no_graceful(d, timeout=8.0):
        return False

    monkeypatch.setattr(daemon, "_close_browser_gracefully", no_graceful)

    # Another daemon (x-monitor stack) alive -> browser stays.
    monkeypatch.setattr(daemon.ipc, "ping", lambda name, timeout=1.0: name == "x-monitor")
    asyncio.run(daemon._stop_agent_chrome_if_last(SimpleNamespace()))
    assert events == []

    # Last daemon standing -> agent Chrome closed.
    monkeypatch.setattr(daemon.ipc, "ping", lambda name, timeout=1.0: False)
    asyncio.run(daemon._stop_agent_chrome_if_last(SimpleNamespace()))
    assert events == ["chrome"]


def test_idle_exit_prefers_graceful_cdp_close(monkeypatch):
    """Browser.close (via our own CDP connection) is the first choice; the
    pid-precise stop only runs when the graceful close fails."""
    events = []
    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(admin, "_pinned_agent_cdp", lambda env=None: True)
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("pid-stop"))
    monkeypatch.setattr(daemon.ipc, "ping", lambda name, timeout=1.0: False)

    async def graceful(d, timeout=8.0):
        return True

    monkeypatch.setattr(daemon, "_close_browser_gracefully", graceful)
    asyncio.run(daemon._stop_agent_chrome_if_last(SimpleNamespace()))
    assert events == []  # graceful success: pid path never touched


def test_idle_exit_never_touches_remote_browser_model(monkeypatch):
    events = []
    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(admin, "_pinned_agent_cdp", lambda env=None: False)  # user's browser
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("chrome"))
    monkeypatch.setattr(daemon.ipc, "ping", lambda name, timeout=1.0: False)
    asyncio.run(daemon._stop_agent_chrome_if_last(SimpleNamespace()))
    assert events == []  # remote/user model: nothing we own


# --- graceful close: the port-death event is the verdict (Issue #3 rule) ---


def test_close_browser_gracefully_judges_by_port_event(monkeypatch):
    sent = []

    class FakeCDP:
        async def send_raw(self, method, params, session_id=None):
            sent.append(method)
            raise asyncio.CancelledError()  # browser died before replying — reply loss must not matter

    monkeypatch.setattr(daemon, "_debug_port_live", lambda: False)  # port dead = success event
    d = SimpleNamespace(cdp=FakeCDP())
    assert asyncio.run(daemon._close_browser_gracefully(d)) is True
    assert sent == ["Browser.close"]


def test_close_browser_gracefully_silent_deadline_is_false(monkeypatch):
    class FakeCDP:
        async def send_raw(self, *a, **k):
            return {}  # clean reply, but the port never dies

    monkeypatch.setattr(daemon, "_debug_port_live", lambda: True)
    ticks = iter([0.0, 0.0, 100.0])  # deadline init, while-pass, while-exit

    async def nosleep(_s):
        pass

    # Replace daemon's module refs wholesale — patching time.monotonic on the
    # real module would leak into asyncio's own clock (event-loop internals
    # consume the tick sequence).
    monkeypatch.setattr(daemon, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    monkeypatch.setattr(daemon, "asyncio", SimpleNamespace(sleep=nosleep, wait_for=asyncio.wait_for))
    d = SimpleNamespace(cdp=FakeCDP())
    assert asyncio.run(daemon._close_browser_gracefully(d, timeout=8.0)) is False


def test_isolated_teardown_stops_browser_and_deletes_task_profile(monkeypatch, tmp_path):
    """An isolated task stack is exclusively ours: no other-daemon yielding,
    and the cloned profile goes away with it."""
    events = []
    home = tmp_path / "bh-home"
    task_profile = home / "task-profiles" / "task-abcd1234"
    task_profile.mkdir(parents=True)
    monkeypatch.setenv("BH_ISOLATED_TASK", "1")
    monkeypatch.setenv("BH_AGENT_CHROME_PROFILE", str(task_profile))
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("chrome"))
    monkeypatch.setattr(admin, "restart_daemon", lambda nm=None: events.append("daemon"))
    # even with another daemon alive, an isolated browser still comes down
    monkeypatch.setattr(admin, "daemon_alive", lambda nm: nm == "x-monitor")
    import browser_harness.paths as paths

    monkeypatch.setattr(paths, "home_dir", lambda: home)

    admin._launched_chrome_here = True
    admin._started_daemon_here = True
    try:
        admin.teardown_scoped_stack()
    finally:
        admin._launched_chrome_here = False
        admin._started_daemon_here = False
    assert events == ["chrome", "daemon"]
    assert not task_profile.exists()
