import io
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from browser_harness import admin


class FakeSocket:
    def __init__(self, response=b'{"target_id":"target-1","session_id":"session-1","page":null}\n'):
        self.response = response
        self.closed = False
        self.sent = b""

    def sendall(self, data):
        self.sent += data

    def recv(self, _size):
        out, self.response = self.response, b""
        return out

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, pid=123, returncode=None):
        self.pid = pid
        self.returncode = returncode
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="os.killpg is POSIX-only")
def test_cleanup_unattached_browser_launch_stops_posix_process_group(monkeypatch):
    process = FakeProcess()
    killed = []
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr("browser_harness.daemon._devtools_port_live", lambda _profile: False)
    monkeypatch.setattr(admin.os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    admin._cleanup_unattached_browser_launch((process, Path("/profile")))

    assert killed == [(123, signal.SIGTERM)]


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="os.killpg is POSIX-only")
def test_cleanup_unattached_browser_launch_keeps_cdp_browser(monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr("browser_harness.daemon._devtools_port_live", lambda _profile: True)
    monkeypatch.setattr(admin.os, "killpg", lambda _pid, _sig: pytest.fail("must keep the attached browser"))

    admin._cleanup_unattached_browser_launch((process, Path("/profile")))


def test_cleanup_unattached_browser_launch_ignores_unowned_launch(monkeypatch):
    monkeypatch.setattr(
        "browser_harness.daemon._devtools_port_live",
        lambda _profile: pytest.fail("must not probe an unowned launch"),
    )

    admin._cleanup_unattached_browser_launch((None, Path("/profile")))


@pytest.mark.parametrize("env_key", ["BH_CHROME_PATH", "CHROME_PATH"])
@pytest.mark.skipif(not hasattr(os, "killpg"), reason="os.killpg is POSIX-only")
def test_explicit_chrome_path_retains_matching_profile_on_linux(monkeypatch, tmp_path, env_key):
    binary = tmp_path / "google-chrome-stable"
    binary.touch()
    profile = tmp_path / ".config" / "google-chrome"
    (profile / "Default").mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    process = FakeProcess()

    other_key = "CHROME_PATH" if env_key == "BH_CHROME_PATH" else "BH_CHROME_PATH"
    monkeypatch.setenv(env_key, str(binary))
    monkeypatch.delenv(other_key, raising=False)
    monkeypatch.setattr("browser_harness.daemon.PROFILES", [profile])
    monkeypatch.setattr("browser_harness.daemon.remote_debugging_toggle_profiles", lambda: [profile])
    monkeypatch.setattr("browser_harness.daemon._devtools_port_live", lambda _profile: False)
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: process)
    killed = []
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    launch = admin._launch_browser()
    assert launch == (process, profile)

    admin._cleanup_unattached_browser_launch(launch)
    assert killed == [(process.pid, signal.SIGTERM)]


@pytest.mark.parametrize("system", ["Darwin", "Windows"])
@pytest.mark.skipif(not hasattr(os, "killpg"), reason="os.killpg is POSIX-only")
def test_explicit_chrome_path_remains_unowned_without_platform_cleanup(monkeypatch, tmp_path, system):
    binary = tmp_path / ("chrome.exe" if system == "Windows" else "Google Chrome")
    binary.touch()
    profile = tmp_path / ".config" / "google-chrome"
    (profile / "Default").mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    process = FakeProcess()

    monkeypatch.setenv("BH_CHROME_PATH", str(binary))
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr("browser_harness.daemon.PROFILES", [profile])
    monkeypatch.setattr("browser_harness.daemon.remote_debugging_toggle_profiles", lambda: [profile])
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(admin.os, "killpg", lambda *_args: pytest.fail("must not terminate an unowned browser"))

    launch = admin._launch_browser()
    assert launch == (process, None)

    admin._cleanup_unattached_browser_launch(launch)
    assert process.terminated is False


def test_explicit_unknown_browser_path_remains_unowned(monkeypatch, tmp_path):
    binary = tmp_path / "custom-browser"
    binary.touch()
    profile = tmp_path / ".config" / "google-chrome"
    profile.mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    process = FakeProcess()

    monkeypatch.setenv("BH_CHROME_PATH", str(binary))
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr("browser_harness.daemon.PROFILES", [profile])
    monkeypatch.setattr("browser_harness.daemon.remote_debugging_toggle_profiles", lambda: [profile])
    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: process)

    assert admin._launch_browser() == (process, None)


@pytest.mark.parametrize("value", ["0", "false", "NO", " off "])
def test_update_banner_can_be_disabled_without_network_or_cache_access(monkeypatch, value):
    monkeypatch.setenv("BH_UPDATE_CHECK", value)
    monkeypatch.setattr(admin, "_cache_read", lambda: pytest.fail("cache should not be read"))
    monkeypatch.setattr(admin, "check_for_update", lambda: pytest.fail("network should not run"))

    admin.print_update_banner()


def test_update_banner_remains_enabled_by_default(monkeypatch):
    monkeypatch.delenv("BH_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(admin, "_cache_read", lambda: {"banner_shown_on": "1970-01-01"})
    called = []

    def fake_check_for_update():
        called.append(True)
        return "0.1.0", "0.1.0", False

    monkeypatch.setattr(admin, "check_for_update", fake_check_for_update)

    admin.print_update_banner()

    assert called == [True]


def test_local_chrome_mode_is_false_when_env_provides_remote_cdp():
    assert not admin._is_local_chrome_mode({"BU_CDP_WS": "ws://example.test/devtools/browser/1"})


def test_require_existing_daemon_fails_without_spawning(monkeypatch):
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)

    with pytest.raises(RuntimeError, match="required daemon 'scoped' is not running"):
        admin.require_existing_daemon("scoped")


def test_require_existing_daemon_probes_cdp(monkeypatch):
    sock = FakeSocket(response=b'{"result":{"targetInfos":[]}}\n')
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda _name, timeout: (sock, None))

    admin.require_existing_daemon("scoped")

    assert b'"method": "Target.getTargets"' in sock.sent
    assert sock.closed is True


def test_local_chrome_mode_is_false_when_process_env_provides_remote_cdp(monkeypatch):
    monkeypatch.setenv("BU_CDP_WS", "ws://example.test/devtools/browser/1")

    assert not admin._is_local_chrome_mode()


def test_handshake_timeout_needs_chrome_remote_debugging_prompt():
    msg = "CDP WS handshake failed: timed out during opening handshake"

    assert admin._needs_chrome_remote_debugging_prompt(msg)


def test_handshake_403_needs_chrome_remote_debugging_prompt():
    msg = "CDP WS handshake failed: server rejected WebSocket connection: HTTP 403"

    assert admin._needs_chrome_remote_debugging_prompt(msg)


def test_stale_websocket_does_not_open_chrome_inspect():
    msg = "no close frame received or sent"

    assert not admin._needs_chrome_remote_debugging_prompt(msg)


def test_daemon_endpoint_names_discovers_valid_socket_names(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", None)  # shared-tmpdir mode
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    (tmp_path / "bu-default.sock").touch()
    (tmp_path / "bu-remote_1.sock").touch()
    (tmp_path / "bu-invalid.name.sock").touch()
    (tmp_path / "not-bu-default.sock").touch()

    assert admin._daemon_endpoint_names() == ["default", "remote_1"]


def test_daemon_endpoint_names_with_bh_runtime_dir_returns_local_name_when_sock_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR_SHARED", False)
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    monkeypatch.setattr(admin, "NAME", "session-xyz")
    (tmp_path / "bu.sock").touch()

    assert admin._daemon_endpoint_names() == ["session-xyz"]


def test_daemon_endpoint_names_with_bh_runtime_dir_returns_empty_when_sock_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR_SHARED", False)
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    monkeypatch.setattr(admin, "NAME", "session-xyz")

    assert admin._daemon_endpoint_names() == []


def test_daemon_endpoint_names_with_shared_bh_runtime_dir_discovers_named_sockets(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR_SHARED", True)
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    (tmp_path / "bu-default.sock").touch()
    (tmp_path / "bu-work.sock").touch()
    (tmp_path / "bu-invalid.name.sock").touch()
    (tmp_path / "bu.sock").touch()  # stale isolated-runtime endpoint

    assert admin._daemon_endpoint_names() == ["default", "work"]


def test_active_browser_connections_counts_only_healthy_daemons(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default", "stale", "remote"])

    def fake_connect(name, timeout=1.0):
        if name == "stale":
            raise ConnectionRefusedError()
        if name == "remote":
            return FakeSocket(b'{"error":"no close frame received or sent"}\n'), None
        return FakeSocket(), None

    monkeypatch.setattr(admin.ipc, "connect", fake_connect)

    assert admin.active_browser_connections() == 1


def test_daemon_browser_ready_checks_the_selected_daemon(monkeypatch):
    calls = []
    monkeypatch.setattr(
        admin,
        "_daemon_browser_connection",
        lambda name: calls.append(name) or {"name": name, "page": None},
    )

    assert admin.daemon_browser_ready("work")
    assert calls == ["work"]


def test_active_browser_connections_skips_daemons_reporting_cdp_disconnected(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default", "stale"])

    def fake_connect(name, timeout=1.0):
        if name == "stale":
            return FakeSocket(b'{"error":"cdp_disconnected"}\n'), None
        return FakeSocket(), None

    monkeypatch.setattr(admin.ipc, "connect", fake_connect)

    assert admin.active_browser_connections() == 1


def test_browser_connections_returns_attached_page(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default"])
    response = (
        b'{"target_id":"target-1","session_id":"session-1",'
        b'"page":{"targetId":"target-1","title":"Cat - Wikipedia","url":"https://en.wikipedia.org/wiki/Cat"}}\n'
    )
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout=1.0: (FakeSocket(response), None))

    assert admin.browser_connections() == [
        {
            "name": "default",
            "page": {"title": "Cat - Wikipedia", "url": "https://en.wikipedia.org/wiki/Cat"},
        }
    ]


def test_chrome_running_detects_helium_on_linux(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "subprocess.check_output",
        lambda *args, **kwargs: "systemd\nhelium\nxdg-desktop-portal\n",
    )

    assert admin._chrome_running()


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/snap/chromium/1234/usr/lib/chromium-browser/chromium-browser", True),
        ("/SNAP/foo", True),
        ("/usr/bin/google-chrome-stable", False),
        ("", False),
    ],
)
def test_is_snap_browser(path, expected):
    assert admin._is_snap_browser(path) == expected


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation requires Developer Mode on Windows")
def test_doctor_probe_preserves_snap_bin_env_symlink(monkeypatch, tmp_path):
    target = tmp_path / "usr" / "bin" / "snap"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n")
    snap_bin = tmp_path / "snap" / "bin"
    snap_bin.mkdir(parents=True)
    chromium = snap_bin / "chromium"
    chromium.symlink_to(target)

    monkeypatch.setenv("BH_CHROME_PATH", str(chromium))
    monkeypatch.delenv("CHROME_PATH", raising=False)

    name, path = admin._doctor_probe_chrome_binary_for_snap()

    assert name == "chromium"
    assert path == str(chromium)
    assert admin._is_snap_browser(path)


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation requires Developer Mode on Windows")
def test_doctor_probe_preserves_snap_bin_path_symlink(monkeypatch, tmp_path):
    target = tmp_path / "usr" / "bin" / "snap"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n")
    snap_bin = tmp_path / "snap" / "bin"
    snap_bin.mkdir(parents=True)
    chromium = snap_bin / "chromium"
    chromium.symlink_to(target)

    monkeypatch.delenv("BH_CHROME_PATH", raising=False)
    monkeypatch.delenv("CHROME_PATH", raising=False)

    def fake_which(cmd):
        return str(chromium) if cmd == "chromium" else None

    monkeypatch.setattr("shutil.which", fake_which)

    name, path = admin._doctor_probe_chrome_binary_for_snap()

    assert name == "chromium"
    assert path == str(chromium)
    assert admin._is_snap_browser(path)


def test_run_doctor_prints_snap_detect_on_linux_when_probe_is_snap(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: False)
    monkeypatch.setattr(admin, "daemon_alive", lambda: False)
    monkeypatch.setattr(admin, "browser_connections", lambda: [])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_doctor_probe_chrome_binary_for_snap", lambda: ("chromium", "/snap/chromium/1/usr/bin/chromium"))
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 1

    out = capsys.readouterr().out
    assert "[snap-detect]" in out
    assert "Browser: chromium (snap)" in out
    assert "Snap confinement prevents CDP binding" in out
    assert "docs/snap-linux-headless.md" in out


def test_run_doctor_skips_snap_detect_on_non_linux(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "browser_connections", lambda: [])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_doctor_probe_chrome_binary_for_snap", lambda: ("chromium", "/snap/chromium/1/usr/bin/chromium"))
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "[snap-detect]" not in out


def test_run_doctor_fix_snap_prints_steps(capsys):
    assert admin.run_doctor_fix_snap() == 0
    out = capsys.readouterr().out
    assert "browser-harness doctor --fix-snap" in out
    assert "BH_CHROME_PATH" in out
    assert "google-chrome-stable_current_amd64.deb" in out
    assert "browser-harness --doctor" in out


def test_run_doctor_prints_active_browser_connections_and_active_pages(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "browser_connections", lambda: [
        {
            "name": "default",
            "page": {"title": "Example", "url": "https://example.test"},
        },
        {
            "name": "cats",
            "page": {"title": "Cat - Wikipedia", "url": "https://en.wikipedia.org/wiki/Cat"},
        },
    ])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "[ok  ] active browser connections — 2" in out
    assert "        default — active page: Example — https://example.test" in out
    assert "        cats — active page: Cat - Wikipedia — https://en.wikipedia.org/wiki/Cat" in out


def test_doctor_page_output_truncates_long_text(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "DOCTOR_TEXT_LIMIT", 20)
    monkeypatch.setattr(admin, "browser_connections", lambda: [
        {
            "name": "default",
            "page": {"title": "A very long page title", "url": "https://example.test/very/long/path"},
        }
    ])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "A very long page ..." in out
    assert "https://example.t..." in out


def test_restart_daemon_does_not_signal_when_daemon_unreachable(monkeypatch, tmp_path):
    """If ipc.identify() returns None (daemon gone), restart_daemon must NOT
    fall back to reading the pid file and SIGTERMing whatever owns that PID —
    that's the PID-reuse hazard. It should only clean up files."""
    pid_path = tmp_path / "default.pid"
    # A pid file with a PID that, if signaled, would hit an unrelated process.
    # The whole point is that we don't read or trust this number.
    pid_path.write_text("99999")

    kill_calls = []
    monkeypatch.setattr(admin.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: None)
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: False)
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)

    # Should not raise, should not signal, should still clean up the pid file.
    admin.restart_daemon("default")

    assert kill_calls == [], (
        f"restart_daemon SIGTERM'd a PID despite identify() returning None — "
        f"this is the PID-reuse hazard the function is meant to avoid. Calls: {kill_calls}"
    )
    assert not pid_path.exists(), "stale pid file should be cleaned up"


def test_restart_daemon_signals_pid_returned_by_identify_not_pid_file(monkeypatch, tmp_path):
    """The PID we signal must come from the live daemon's self-report, never
    from the pid file. If a stale pid file disagrees, the live daemon's PID wins."""
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")  # bogus stale value — must be ignored

    live_pid = 4242

    kill_calls = []
    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        # First os.kill(pid, 0) probe: report process is gone so we exit the loop
        # without escalating. We just want to see WHICH pid was probed.
        if sig == 0:
            raise ProcessLookupError

    class FakeIPC:
        def __init__(self):
            self.shutdown_sent = False
        def identify(self, name, timeout=5.0):
            return live_pid
        def connect(self, name, timeout):
            return ("conn", "tok")
        def request(self, conn, tok, msg):
            if msg.get("meta") == "shutdown":
                self.shutdown_sent = True
            return {"ok": True}
        def pid_path(self, name):
            return pid_path
        def cleanup_endpoint(self, name):
            pass

    fake = FakeIPC()
    monkeypatch.setattr(admin.os, "kill", fake_kill)
    monkeypatch.setattr(admin.ipc, "identify", fake.identify)
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", fake.connect)
    monkeypatch.setattr(admin.ipc, "request", fake.request)
    monkeypatch.setattr(admin.ipc, "pid_path", fake.pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", fake.cleanup_endpoint)

    admin.restart_daemon("default")

    assert fake.shutdown_sent, "expected shutdown IPC to be sent"
    assert kill_calls, "expected at least one os.kill probe"
    pids_signaled = {pid for pid, _ in kill_calls}
    assert pids_signaled == {live_pid}, (
        f"restart_daemon must only signal the PID returned by identify(); "
        f"signaled pids: {pids_signaled}, expected {{{live_pid}}} (and NOT 99999)"
    )
    assert not pid_path.exists()


def test_restart_daemon_sends_shutdown_to_pre_upgrade_daemon_without_pid_in_ping(monkeypatch, tmp_path):
    """Backward compat: a pre-upgrade daemon's ping reply has {pong:True} but
    no `pid` field, so identify() returns None. The shutdown IPC must STILL be
    sent (so the daemon exits cleanly), but no os.kill happens (we have no
    verified PID to safely signal)."""
    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")  # bogus stale value

    kill_calls = []
    shutdown_calls = []

    def fake_request(conn, tok, msg):
        if msg.get("meta") == "shutdown":
            shutdown_calls.append(msg)
        return {"ok": True}

    monkeypatch.setattr(admin.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: None)
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)  # old daemon: alive but no pid
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", fake_request)
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)

    admin.restart_daemon("default")

    assert shutdown_calls, (
        "restart_daemon must send shutdown IPC to a pre-upgrade daemon even "
        "when identify() can't return a PID — otherwise upgrades orphan the "
        "old daemon while deleting its socket and pid file."
    )
    assert kill_calls == [], (
        f"no os.kill should fire when we don't have a verified PID, "
        f"but got: {kill_calls}"
    )
    assert not pid_path.exists()


def test_restart_daemon_skips_sigterm_if_pid_was_reused_during_wait(monkeypatch, tmp_path):
    """A second identify() runs immediately before the SIGTERM. If the daemon
    exited and the PID was reused mid-wait, identify() will return None (or a
    different PID) and we must NOT signal — that's the PID-reuse race during
    the 15s wait window."""
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")
    live_pid = 4242

    kill_calls = []

    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        # All os.kill(pid, 0) probes succeed → loop exhausts → reaches the
        # SIGTERM branch. (We're simulating a "wedged" daemon that the wait
        # loop can't tell apart from a daemon whose PID got reused.)

    # First identify() call (top of restart_daemon) returns the live PID.
    # Second identify() call (right before SIGTERM) returns None — simulating
    # the daemon having exited and its PID having been reused by an unrelated
    # process. The function must NOT escalate to SIGTERM in that state.
    identify_responses = iter([live_pid, None])
    monkeypatch.setattr(admin.os, "kill", fake_kill)
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: next(identify_responses))
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", lambda conn, tok, msg: {"ok": True})
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)
    # Speed up the wait loop so the test finishes quickly. The loop polls 75
    # times at 0.2s = 15s; with sleep neutralized it runs in microseconds.
    monkeypatch.setattr(admin.time, "sleep", lambda _s: None)

    admin.restart_daemon("default")

    sigterms = [(pid, sig) for pid, sig in kill_calls if sig == signal.SIGTERM]
    assert sigterms == [], (
        f"restart_daemon issued SIGTERM despite the re-verify identify() "
        f"returning None (PID was reused during the 15s wait). Calls: {kill_calls}"
    )
    assert not pid_path.exists()


def test_restart_daemon_sigterms_via_start_time_fingerprint_when_socket_gone(monkeypatch, tmp_path):
    """Slow-shutdown recovery: the daemon's serve() tears down the IPC socket
    BEFORE the process exits (the daemon then runs slow cleanup like remote
    `stop` PATCH calls that can hang). In that window, identify() returns None
    even though the process is still our daemon. SIGTERM must still fire when
    the PID's start-time fingerprint hasn't changed since we first identified
    it — that's strong evidence of "same process, just slow to exit."
    """
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")
    live_pid = 4242

    kill_calls = []

    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        # All os.kill(pid, 0) probes succeed; loop exhausts → SIGTERM gate runs.

    # First identify() returns live_pid. Second identify() returns None — the
    # daemon has torn down its IPC during shutdown but the process is still
    # finishing up cleanup work, so the start-time fingerprint is unchanged.
    identify_responses = iter([live_pid, None])
    # Both _process_start_time() calls return the same fingerprint, signaling
    # "still the same process." This is the legitimate-slow-shutdown case.
    monkeypatch.setattr(admin, "_process_start_time", lambda pid: "STARTED_AT_X")
    monkeypatch.setattr(admin.os, "kill", fake_kill)
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: next(identify_responses))
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", lambda conn, tok, msg: {"ok": True})
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)
    monkeypatch.setattr(admin.time, "sleep", lambda _s: None)

    admin.restart_daemon("default")

    sigterms = [(pid, sig) for pid, sig in kill_calls if sig == signal.SIGTERM]
    assert sigterms == [(live_pid, signal.SIGTERM)], (
        f"slow-shutdown daemon (identify=None but unchanged start-time) must "
        f"still receive SIGTERM. signal calls: {kill_calls}"
    )


def test_restart_daemon_skips_sigterm_when_start_time_changed_during_wait(monkeypatch, tmp_path):
    """If the start-time fingerprint of the original PID has CHANGED, the PID
    was reused by another process. Even though identify() also returns None,
    we must skip SIGTERM — start-time mismatch is the signal that protects
    against killing an unrelated reused-PID process."""
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")
    live_pid = 4242

    kill_calls = []
    monkeypatch.setattr(admin.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))

    identify_responses = iter([live_pid, None])
    # First start-time read at top of restart_daemon: "ORIGINAL".
    # Second start-time read in the safety gate: "DIFFERENT" — proof of reuse.
    start_time_responses = iter(["ORIGINAL", "DIFFERENT"])
    monkeypatch.setattr(admin, "_process_start_time", lambda pid: next(start_time_responses))
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: next(identify_responses))
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", lambda conn, tok, msg: {"ok": True})
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)
    monkeypatch.setattr(admin.time, "sleep", lambda _s: None)

    admin.restart_daemon("default")

    sigterms = [(pid, sig) for pid, sig in kill_calls if sig == signal.SIGTERM]
    assert sigterms == [], (
        f"start-time mismatch indicates PID reuse — restart_daemon must NOT "
        f"SIGTERM. signal calls: {kill_calls}"
    )


# --- _process_start_time helper ---

def test_process_start_time_returns_stable_fingerprint_for_self():
    """The start-time of the current process should be readable on Linux,
    macOS, and Windows, and stable across two reads."""
    import os as _os, sys
    if sys.platform.startswith("linux") or sys.platform == "darwin" or sys.platform == "win32":
        pid = _os.getpid()
        first = admin._process_start_time(pid)
        second = admin._process_start_time(pid)
        assert first is not None, "expected a fingerprint for the current PID"
        assert first == second, (
            f"two reads of the same PID should return the same fingerprint; "
            f"got {first!r} vs {second!r}"
        )


def test_process_start_time_returns_none_for_invalid_pid():
    """Bad inputs (None, 0, negatives, non-int) and PIDs with no live process
    must return None rather than raising."""
    for bad in (None, 0, -1, -42, "not-an-int", 1.5, True, False):
        assert admin._process_start_time(bad) is None, (
            f"expected None for invalid pid {bad!r}"
        )
    # 2**31 - 1 is the largest pid_t; in practice no live process at that PID.
    assert admin._process_start_time((1 << 31) - 1) is None


def test_extra_chrome_flags_empty_by_default(monkeypatch):
    monkeypatch.delenv("BH_NO_THROTTLE", raising=False)
    monkeypatch.delenv("BH_CHROME_EXTRA_FLAGS", raising=False)
    assert admin._extra_chrome_flags() == []


def test_extra_chrome_flags_no_throttle_and_custom(monkeypatch):
    monkeypatch.setenv("BH_NO_THROTTLE", "1")
    monkeypatch.setenv("BH_CHROME_EXTRA_FLAGS", "--foo=1 --bar")
    assert admin._extra_chrome_flags() == ["--foo=1", "--bar"] + list(admin._NO_THROTTLE_FLAGS)


def test_launch_browser_appends_extra_flags(monkeypatch, tmp_path):
    binary = tmp_path / "chrome.exe"
    binary.touch()
    process = FakeProcess()
    seen = {}
    monkeypatch.setenv("BH_NO_THROTTLE", "1")
    monkeypatch.setenv("BH_CHROME_PATH", str(binary))
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr("browser_harness.daemon.PROFILES", [])
    monkeypatch.setattr("browser_harness.daemon.remote_debugging_toggle_profiles", lambda: [])
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        return process

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    admin._launch_browser()

    assert seen["cmd"][0] == str(binary)
    assert "--disable-background-timer-throttling" in seen["cmd"]
    assert "--disable-backgrounding-occluded-windows" in seen["cmd"]
    assert "--disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion" in seen["cmd"]


# --- run_update seamless-upgrade loop (M102 + workspace provisioning) ---

class FakeCompleted:
    returncode = 0


def test_stop_stack_kills_rmux_and_both_daemons(monkeypatch):
    state = {"killed_server": False}

    class FakeRmux:
        def __init__(self):
            pass

        def server_running(self):
            return True

        def has_session(self, name):
            return name == "x-supervisor"

        def kill_server(self):
            state["killed_server"] = True

    stopped = []
    monkeypatch.setattr("browser_harness.rmux.Rmux", FakeRmux)
    monkeypatch.setattr(admin, "daemon_alive", lambda name=None: name in ("default", "x-monitor"))
    monkeypatch.setattr(admin, "restart_daemon", lambda name=None, **_kw: stopped.append(name))

    assert admin._stop_stack_for_upgrade() is True
    assert state["killed_server"] is True
    assert stopped == ["default", "x-monitor"]


def test_stop_stack_without_rmux_returns_false(monkeypatch):
    def boom():
        raise RuntimeError("rmux is not installed")

    monkeypatch.setattr("browser_harness.rmux.Rmux", boom)
    monkeypatch.setattr(admin, "daemon_alive", lambda name=None: False)
    monkeypatch.setattr(admin, "restart_daemon", lambda name=None, **_kw: pytest.fail("no daemon to stop"))
    assert admin._stop_stack_for_upgrade() is False


def test_provision_after_update_runs_skills_sync(monkeypatch):
    seen = []
    import browser_harness.skills as skills_mod
    monkeypatch.setattr(skills_mod, "run_cli", lambda args: seen.append(args) or 0)
    assert admin._provision_after_update() == 0
    assert seen == [["sync"]]


def test_run_update_installed_stops_before_uv_and_restores(monkeypatch):
    calls = []
    import sys as _sys
    monkeypatch.setattr(_sys, "platform", "linux")  # in-process path; win32 relays

    monkeypatch.setattr(admin, "check_for_update", lambda: ("0.5.1", "0.6.0", True))
    monkeypatch.setattr(admin, "_install_mode", lambda: "installed")
    monkeypatch.setattr(admin, "_stop_stack_for_upgrade", lambda: calls.append("stop") or True)
    monkeypatch.setattr(admin, "_provision_after_update", lambda: calls.append("provision") or 0)
    monkeypatch.setattr(admin, "_restart_x_monitor", lambda: calls.append("restart") or 0)
    monkeypatch.setattr(admin, "_cache_read", lambda: {"banner_shown_on": "x", "tag": "0.5.1", "fetched_at": 1})
    written = {}
    monkeypatch.setattr(admin, "_cache_write", lambda c: written.update(c))

    def fake_run(argv, **_kw):
        calls.append(("uv", tuple(argv[:2])))
        return FakeCompleted()

    monkeypatch.setattr(admin.subprocess, "run", fake_run)
    monkeypatch.setattr(admin, "daemon_alive", lambda name=None: False)

    assert admin.run_update(yes=True) == 0
    # order: stack stopped BEFORE uv replaces the venv; provision+restart after.
    assert calls[0] == "stop"
    assert calls[1] == ("uv", ("uv", "tool"))
    assert "provision" in calls and "restart" in calls
    assert calls.index("provision") < calls.index("restart")
    # tag cache invalidated so doctor shows the fresh release immediately
    assert "tag" not in written and "fetched_at" not in written and "banner_shown_on" not in written


def test_run_update_installed_uv_failure_hints_m102(monkeypatch, capsys):
    import sys as _sys
    monkeypatch.setattr(_sys, "platform", "linux")
    monkeypatch.setattr(admin, "check_for_update", lambda: ("0.5.1", "0.6.0", True))
    monkeypatch.setattr(admin, "_install_mode", lambda: "installed")
    monkeypatch.setattr(admin, "_stop_stack_for_upgrade", lambda: True)
    monkeypatch.setattr(admin, "_provision_after_update", lambda: pytest.fail("must not provision a failed update"))

    class Fail:
        returncode = 5

    monkeypatch.setattr(admin.subprocess, "run", lambda argv, **_kw: Fail())
    assert admin.run_update(yes=True) == 5
    assert "M102" in capsys.readouterr().err


def test_run_update_uptodate_still_provisions(monkeypatch, capsys):
    monkeypatch.setattr(admin, "check_for_update", lambda: ("0.6.0", "0.6.0", False))
    monkeypatch.setattr(admin, "_install_mode", lambda: pytest.fail("must short-circuit before install mode"))
    provided = []
    monkeypatch.setattr(admin, "_provision_after_update", lambda: provided.append(1) or 0)
    monkeypatch.setattr(admin.subprocess, "run", lambda argv, **_kw: pytest.fail("no uv call when up to date"))

    assert admin.run_update(yes=True) == 0
    assert provided == [1]
    assert "up to date" in capsys.readouterr().out


def test_run_update_windows_relays_and_returns(monkeypatch, capsys):
    import sys as _sys
    monkeypatch.setattr(_sys, "platform", "win32")
    relay_args = []

    monkeypatch.setattr(admin, "check_for_update", lambda: ("0.6.1", "0.6.2", True))
    monkeypatch.setattr(admin, "_install_mode", lambda: "installed")
    monkeypatch.setattr(admin, "_stop_stack_for_upgrade", lambda: True)
    monkeypatch.setattr(admin, "_relayed_tool_upgrade",
                        lambda had: relay_args.append(had) or True)
    monkeypatch.setattr(admin.subprocess, "run",
                        lambda argv, **_kw: pytest.fail("relay must own the install"))
    monkeypatch.setattr(admin, "_cache_read", lambda: {"banner_shown_on": "x", "tag": "0.6.1", "fetched_at": 1})
    written = {}
    monkeypatch.setattr(admin, "_cache_write", lambda c: written.update(c))

    assert admin.run_update(yes=True) == 0
    assert relay_args == [True]  # x-monitor was running -> relay told to restore it
    out = capsys.readouterr().out
    assert "cannot replace its own venv" in out
    assert "tag" not in written and "fetched_at" not in written


def test_run_update_windows_relay_failure_falls_back_in_process(monkeypatch, capsys):
    import sys as _sys
    monkeypatch.setattr(_sys, "platform", "win32")
    calls = []

    monkeypatch.setattr(admin, "check_for_update", lambda: ("0.6.1", "0.6.2", True))
    monkeypatch.setattr(admin, "_install_mode", lambda: "installed")
    monkeypatch.setattr(admin, "_stop_stack_for_upgrade", lambda: calls.append("stop") or True)
    monkeypatch.setattr(admin, "_relayed_tool_upgrade", lambda had: False)
    monkeypatch.setattr(admin, "_provision_after_update", lambda: calls.append("provision") or 0)
    monkeypatch.setattr(admin, "_restart_x_monitor", lambda: calls.append("restart") or 0)
    monkeypatch.setattr(admin, "_cache_read", lambda: {})
    monkeypatch.setattr(admin, "_cache_write", lambda c: None)
    monkeypatch.setattr(admin.subprocess, "run", lambda argv, **_kw: FakeCompleted())
    monkeypatch.setattr(admin, "daemon_alive", lambda name=None: False)

    assert admin.run_update(yes=True) == 0
    assert calls == ["stop", "provision", "restart"]
    assert "relay unavailable" in capsys.readouterr().err


def test_relayed_tool_upgrade_builds_pwsh_wait_and_tail(monkeypatch):
    spawned = []

    class FakePopen:
        def __init__(self, argv, **_kw):
            spawned.append(argv)

    monkeypatch.setattr(admin.shutil, "which", lambda name: "C:/pwsh.exe" if name == "pwsh" else None)
    monkeypatch.setattr(admin.subprocess, "Popen", FakePopen)

    assert admin._relayed_tool_upgrade(had_x_monitor=True) is True
    argv = spawned[0]
    assert argv[0] == "C:/pwsh.exe" and argv[1] == "-NoProfile" and argv[2] == "-Command"
    script = argv[3]
    assert "Get-Process -Id" in script and "uv tool install --force" in script
    assert "@main" not in script  # default branch is main; suffix is redundant
    assert "browser-harness skills sync; browser-harness x-monitor" in script

    admin._relayed_tool_upgrade(had_x_monitor=False)
    assert "skills sync; browser-harness x-monitor" not in spawned[1][3]

    monkeypatch.setattr(admin.shutil, "which", lambda name: None)
    assert admin._relayed_tool_upgrade(had_x_monitor=True) is False


def test_latest_release_tag_refetches_when_cache_not_newer(monkeypatch):
    # fresh cache (0.6.1) but installed is 0.6.1 too -> cache can't prove
    # "no update"; must refetch and see the newer release.
    monkeypatch.setattr(admin, "_cache_read", lambda: {"tag": "0.6.1", "fetched_at": time.time()})
    monkeypatch.setattr(admin, "_version", lambda: "0.6.1")
    monkeypatch.setattr(admin.urllib.request, "urlopen",
                        lambda _url, timeout=0: io.BytesIO(b'{"tag_name":"v0.6.3"}'))
    written = {}
    monkeypatch.setattr(admin, "_cache_write", lambda c: written.update(c))
    assert admin._latest_release_tag() == "0.6.3"
    assert written["tag"] == "0.6.3"


def test_latest_release_tag_cache_hits_when_newer_than_installed(monkeypatch, capsys):
    # cached 0.6.3 > installed 0.6.1: short-circuit without network; even a
    # dead network must not change the answer.
    monkeypatch.setattr(admin, "_cache_read", lambda: {"tag": "0.6.3", "fetched_at": time.time()})
    monkeypatch.setattr(admin, "_version", lambda: "0.6.1")
    monkeypatch.setattr(admin.urllib.request, "urlopen",
                        lambda _url, timeout=0: pytest.fail("cache hit must not hit the network"))
    assert admin._latest_release_tag() == "0.6.3"


# --- WSL/Linux headless adaptation: configurable agent port + headless launch ---


def test_agent_port_defaults_to_9223(monkeypatch):
    monkeypatch.delenv("BH_AGENT_CDP_PORT", raising=False)
    assert admin._agent_port() == 9223


def test_agent_port_env_override(monkeypatch):
    monkeypatch.setenv("BH_AGENT_CDP_PORT", "9224")
    assert admin._agent_port() == 9224
    monkeypatch.setenv("BH_AGENT_CDP_PORT", "not-a-port")
    assert admin._agent_port() == 9223


def test_pinned_agent_cdp_follows_configured_port(monkeypatch):
    # WSL2 mirrored networking: the Windows stack owns 9223, WSL moves its own
    # agent Chrome to 9224 — the auto-launch pin must follow that port.
    monkeypatch.delenv("BH_AGENT_CDP_PORT", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    assert admin._pinned_agent_cdp({"BU_CDP_URL": "http://127.0.0.1:9223"}) is True
    assert admin._pinned_agent_cdp({"BU_CDP_URL": "http://127.0.0.1:9224"}) is False
    monkeypatch.setenv("BH_AGENT_CDP_PORT", "9224")
    assert admin._pinned_agent_cdp({"BU_CDP_URL": "http://127.0.0.1:9224"}) is True
    assert admin._pinned_agent_cdp({"BU_CDP_URL": "http://127.0.0.1:9223"}) is False
    # Remote endpoints stay externally provisioned — never auto-launched.
    assert admin._pinned_agent_cdp({"BU_CDP_URL": "http://192.168.88.1:9224"}) is False


def test_headless_flags_explicit_states(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("BH_CHROME_HEADLESS", "1")
    assert admin._headless_flags()[:2] == ["--headless=new", "--disable-gpu"]
    monkeypatch.setenv("BH_CHROME_HEADLESS", "0")
    assert admin._headless_flags() == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="auto-detect branch is Linux-only")
def test_headless_flags_auto_detects_displayless_linux(monkeypatch):
    monkeypatch.delenv("BH_CHROME_HEADLESS", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    assert admin._headless_flags() == []
    monkeypatch.delenv("DISPLAY")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert admin._headless_flags() == []
    monkeypatch.delenv("WAYLAND_DISPLAY")
    assert admin._headless_flags()[:2] == ["--headless=new", "--disable-gpu"]


def test_launch_agent_chrome_passes_headless_and_extra_flags(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(admin, "_agent_profile", lambda: tmp_path / "agent-chrome-profile")
    monkeypatch.setattr(admin, "_AGENT_PORT", 9224)
    monkeypatch.setattr(admin, "_chrome_path", lambda: "/usr/bin/google-chrome")
    monkeypatch.setenv("BH_CHROME_HEADLESS", "1")
    monkeypatch.setenv("BH_CHROME_EXTRA_FLAGS", "--window-size=1280,800")
    monkeypatch.setenv("BH_NO_THROTTLE", "")

    # Flip running->True on the launch call so the wait loop exits immediately.
    state = {"running": False}
    monkeypatch.setattr(admin, "_agent_chrome_running", lambda: state["running"])

    def fake_popen(argv, **_kwargs):
        calls.append(argv)
        state["running"] = True

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    assert admin._launch_agent_chrome() is True
    argv = calls[0]
    assert "--remote-debugging-port=9224" in argv
    assert f"--user-data-dir={tmp_path / 'agent-chrome-profile'}" in argv
    assert "--headless=new" in argv and "--disable-gpu" in argv
    assert "--window-size=1280,800" in argv


def test_launch_agent_chrome_loser_waits_instead_of_double_launch(monkeypatch):
    """S008 race fix: with the launch lock held by another process, a caller
    must never Popen — it waits and piggybacks on the holder's Chrome."""
    import os as _os

    monkeypatch.setattr(admin, "_AGENT_PORT", 9231)
    fd, _holder = admin.ipc.acquire_lock("agent-chrome-9231")
    try:
        checks = iter([False, False, True])
        monkeypatch.setattr(admin, "_agent_chrome_running", lambda: next(checks, True))
        popen_calls = []
        monkeypatch.setattr("subprocess.Popen", lambda *a, **k: popen_calls.append(a))
        assert admin._launch_agent_chrome() is True
        assert popen_calls == []  # loser never launches
    finally:
        _os.close(fd)


def test_launch_agent_chrome_concurrent_callers_launch_once(monkeypatch):
    """Two simultaneous cold starts must coalesce into exactly one Popen."""
    from threading import Barrier, Thread

    monkeypatch.setattr(admin, "_AGENT_PORT", 9232)
    monkeypatch.setattr(admin, "_chrome_path", lambda: "/usr/bin/google-chrome")
    monkeypatch.setattr(admin, "_agent_profile", lambda: Path("/tmp/agent-profile"))
    monkeypatch.setenv("BH_CHROME_HEADLESS", "1")
    state = {"running": False}
    popen = {"count": 0}

    def fake_popen(*a, **k):
        popen["count"] += 1
        state["running"] = True

    monkeypatch.setattr(admin, "_agent_chrome_running", lambda: state["running"])
    monkeypatch.setattr("subprocess.Popen", fake_popen)

    barrier = Barrier(2)
    results = []

    def worker():
        barrier.wait()
        results.append(admin._launch_agent_chrome())

    threads = [Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert popen["count"] == 1
    assert results == [True, True]


def _fake_version_endpoint(monkeypatch, payload=None):
    """Point _agent_chrome_headless's /json/version probe at a fake payload.

    payload=None simulates the endpoint being down (Chrome not running)."""

    def fake_urlopen(url, timeout=0):
        if payload is None:
            raise OSError("connection refused")
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(admin.urllib.request, "urlopen", fake_urlopen)


def test_agent_chrome_headless_reads_ua(monkeypatch):
    _fake_version_endpoint(monkeypatch, {"User-Agent": "x HeadlessChrome/152.0.0.0 y"})
    assert admin._agent_chrome_headless() is True
    _fake_version_endpoint(monkeypatch, {"User-Agent": "x Chrome/152.0.0.0 y"})
    assert admin._agent_chrome_headless() is False


def test_agent_chrome_headless_none_when_not_running(monkeypatch):
    _fake_version_endpoint(monkeypatch, None)
    assert admin._agent_chrome_headless() is None


def test_set_env_value_replaces_existing_line(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_HOME", str(tmp_path))
    env = tmp_path / ".env"
    env.write_text(
        "# browser-harness env\nBU_CDP_URL=http://127.0.0.1:9223\nBH_CHROME_HEADLESS=1\n",
        encoding="utf-8",
    )
    admin._set_env_value("BH_CHROME_HEADLESS", "0")
    text = env.read_text(encoding="utf-8")
    assert "BH_CHROME_HEADLESS=0" in text
    assert "BH_CHROME_HEADLESS=1" not in text
    assert "BU_CDP_URL=http://127.0.0.1:9223" in text
    assert "# browser-harness env" in text


def test_set_env_value_appends_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_HOME", str(tmp_path))
    admin._set_env_value("BH_CHROME_HEADLESS", "1")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "BH_CHROME_HEADLESS=1\n"


def test_agent_chrome_pids_matches_agent_profile_only(monkeypatch, tmp_path):
    from browser_harness import browsers

    profile = (tmp_path / "agent-chrome-profile")
    instances = [
        {"pid": 10, "data_dir": str(profile), "port": 9223},
        {"pid": 11, "data_dir": str(tmp_path / "user-profile"), "port": None},
        {"pid": 12, "data_dir": "default", "port": 9223},
    ]
    monkeypatch.setattr(admin, "_agent_profile", lambda: profile)
    monkeypatch.setattr(browsers, "_chrome_instances_windows", lambda: instances)
    monkeypatch.setattr(browsers, "_chrome_instances_linux", lambda: instances)
    monkeypatch.setattr(browsers, "_chrome_instances_darwin", lambda: instances)
    assert admin._agent_chrome_pids() == [10]


def test_chrome_mode_status_reports_env_and_live(monkeypatch, capsys):
    monkeypatch.setenv("BH_CHROME_HEADLESS", "1")
    monkeypatch.setattr(admin, "_agent_chrome_headless", lambda: True)
    assert admin.run_chrome_mode(["status"]) == 0
    out = capsys.readouterr().out
    assert "BH_CHROME_HEADLESS: 1" in out
    assert "agent Chrome now:        headless" in out


def test_chrome_mode_rejects_unknown_mode(monkeypatch):
    assert admin.run_chrome_mode(["fullscreen"]) == 2


def test_chrome_mode_already_in_mode_aligns_env(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BH_HOME", str(tmp_path))
    monkeypatch.setenv("BH_CHROME_HEADLESS", "1")
    monkeypatch.setattr(admin, "_agent_chrome_headless", lambda: True)
    assert admin.run_chrome_mode(["headless"]) == 0
    assert "already headless" in capsys.readouterr().out
    assert "BH_CHROME_HEADLESS=1" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_chrome_mode_flip_quiesces_rmux_stack_before_stopping_daemons(monkeypatch, tmp_path):
    """S008 double-launch root cause: the flip used to leave the rmux
    supervisor/worker alive while stopping the x-monitor daemon — the worker
    respawned its daemon and relaunched Chrome (stale mode) mid-flip. The
    stack must be killed FIRST, daemons/Chrome after, restore last."""
    events = []

    class FakeRmux:
        def server_running(self):
            return True

        def has_session(self, name):
            return name == "x-supervisor"

        def kill_session(self, name):
            events.append(f"kill:{name}")

    monkeypatch.setattr("browser_harness.rmux.Rmux", FakeRmux)
    monkeypatch.setenv("BH_HOME", str(tmp_path))
    monkeypatch.setenv("BU_CDP_URL", "http://127.0.0.1:9223")
    monkeypatch.setattr(admin, "daemon_alive", lambda nm: True)
    monkeypatch.setattr(admin, "restart_daemon", lambda nm=None: events.append(f"daemon:{nm}"))
    # live state by call: target-check (headed) -> stop-check (running) -> result (headless)
    headless_by_call = iter([False, False, True])
    monkeypatch.setattr(admin, "_agent_chrome_headless", lambda: next(headless_by_call, True))
    monkeypatch.setattr(admin, "_stop_agent_chrome", lambda: events.append("chrome-stop"))
    monkeypatch.setattr(admin, "ensure_daemon", lambda *a, **k: events.append("ensure"))
    monkeypatch.setattr(admin, "_restart_x_monitor", lambda: events.append("restore"))

    assert admin.run_chrome_mode(["headless"]) == 0

    assert events.index("kill:x-monitor") < events.index("daemon:default")
    assert events.index("kill:x-supervisor") < events.index("daemon:x-monitor")
    assert events.index("daemon:x-monitor") < events.index("chrome-stop")
    assert events.index("chrome-stop") < events.index("ensure")
    assert events.index("ensure") < events.index("restore")
