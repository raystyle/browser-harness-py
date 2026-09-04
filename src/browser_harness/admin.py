import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import _ipc as ipc
from . import paths


def _process_start_time(pid):
    """Opaque process-start-time fingerprint at PID, or None if unavailable.

    Two reads returning the same non-None value mean the PID still refers to
    the same process; a different value means the PID was reused. Used by
    restart_daemon() to keep the force-kill recovery path working even when
    the daemon has already torn down its IPC socket (e.g. during a slow
    remote shutdown), without falling back to "trust the pid file" — which
    would re-introduce the PID-reuse hazard.

    Linux:   /proc/<pid>/stat field 22 (starttime in clock ticks since boot).
    macOS:   `ps -o lstart= -p <pid>` (an absolute timestamp string).
    Windows: GetProcessTimes via ctypes (FILETIME creation time, 100-ns since 1601).
    Anywhere else: returns None; restart_daemon falls back to its strict
    identify-only check, which is safer than no check at all.
    """
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", "rb") as f:
                raw = f.read().decode("ascii", errors="replace")
        except (FileNotFoundError, PermissionError, OSError):
            return None
        # Field 2 is `(comm)`; comm can contain spaces and parens, so split off
        # everything after the LAST `)` and index from there.
        try:
            tail = raw[raw.rindex(")") + 2:].split()
            return tail[19]  # starttime is field 22 (0-indexed: 21 - skipped 2 = 19)
        except (ValueError, IndexError):
            return None
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                stderr=subprocess.DEVNULL, timeout=2,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        s = out.decode("ascii", errors="replace").strip()
        return s or None
    if sys.platform == "win32":
        # Read the kernel-reported creation time via GetProcessTimes as a
        # 64-bit FILETIME (100-ns intervals since 1601-01-01) so restart_daemon
        # can fingerprint the process before SIGTERM.
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
            ]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
        except (OSError, AttributeError):
            return None
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return None
        try:
            creation = wintypes.FILETIME()
            exit_ft = wintypes.FILETIME()
            kernel_ft = wintypes.FILETIME()
            user_ft = wintypes.FILETIME()
            ok = kernel32.GetProcessTimes(
                h, ctypes.byref(creation), ctypes.byref(exit_ft),
                ctypes.byref(kernel_ft), ctypes.byref(user_ft),
            )
            if not ok:
                return None
            return (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        finally:
            kernel32.CloseHandle(h)
    return None


def _load_env():
    workspace = paths.workspace_dir()
    for p in (paths.home_dir() / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def _load_env_file(p):
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("BU_NAME", "default")
GITHUB_RELEASE_API = "https://api.github.com/repos/raystyle/browser-harness/releases/latest"
GITHUB_REPO_URL = "https://github.com/raystyle/browser-harness"
VERSION_CACHE = paths.config_dir() / "version-cache.json"
VERSION_CACHE_TTL = 24 * 3600
DOCTOR_TEXT_LIMIT = 140


def _log_tail(name):
    try:
        return ipc.log_path(name or NAME).read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1]
    except (FileNotFoundError, IndexError, OSError):
        return None


def _needs_chrome_remote_debugging_prompt(msg):
    """True when Chrome needs the inspect-page permission flow."""
    lower = (msg or "").lower()
    return (
        "devtoolsactiveport not found" in lower
        or "enable chrome://inspect" in lower
        or "not live yet" in lower
        or (
            "ws handshake failed" in lower
            and (
                "403" in lower
                or "opening handshake" in lower
                or "timed out" in lower
                or "timeout" in lower
            )
        )
    )


def _needs_chrome_permission_popup(msg):
    """True when Chrome is reachable but waiting on the per-session Allow popup."""
    lower = (msg or "").lower()
    return "permission-blocked" in lower


def _chrome_not_running(msg):
    """True when the daemon found no running supported browser"""
    return "chrome-not-running" in (msg or "").lower()


def _is_local_chrome_mode(env=None):
    """True when the daemon discovers a local Chrome instead of a remote CDP WS."""
    env = env or {}
    return not (
        env.get("BU_CDP_WS")
        or env.get("BU_CDP_URL")
        or os.environ.get("BU_CDP_WS")
        or os.environ.get("BU_CDP_URL")
    )


def _pinned_agent_cdp(env=None):
    """True when BU_CDP_URL pins the isolated agent Chrome (loopback:<agent port>).

    Only this endpoint may be auto-launched by ensure_daemon; any other CDP
    endpoint is externally provisioned and must not be probed or started.
    """
    env = env or {}
    raw = env.get("BU_CDP_URL") or os.environ.get("BU_CDP_URL")
    if not raw:
        return False
    from urllib.parse import urlparse

    try:
        parsed = urlparse(raw if "//" in raw else f"http://{raw}")
        return (
            parsed.hostname in ("127.0.0.1", "localhost", "::1")
            and parsed.port == _agent_port()
        )
    except ValueError:
        return False


def daemon_alive(name=None):
    # Ping handshake (not a bare connect) so a stale .port file + port reuse
    # after a daemon crash doesn't make us mistake an unrelated listener for ours.
    return ipc.ping(name or NAME, timeout=1.0)


def daemon_browser_kind(name=None):
    """'cdp' | 'local' as self-reported by a live daemon, else None.

    None covers unreachable daemons and pre-browser_kind daemons still running
    from an older version."""
    c = None
    try:
        c, token = ipc.connect(name or NAME, timeout=1.0)
        response = ipc.request(c, token, {"meta": "ping"})
        kind = response.get("browser_kind") if isinstance(response, dict) else None
        return kind if kind in {"cdp", "local"} else None
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError, ValueError):
        return None
    finally:
        if c:
            c.close()


def _daemon_endpoint_names():
    # BH_RUNTIME_DIR isolates one daemon per dir → no filename-prefix discovery,
    # just check whether our local endpoint exists. Without BH_RUNTIME_DIR, or
    # with BH_RUNTIME_DIR_SHARED=1, _RUNTIME is shared and we glob `bu-*.<suffix>`
    # to find every daemon in that runtime dir.
    suffix = ".port" if ipc.IS_WINDOWS else ".sock"
    if ipc.BH_RUNTIME_DIR and not ipc.BH_RUNTIME_DIR_SHARED:
        return [NAME] if (ipc._RUNTIME / f"bu{suffix}").exists() else []
    names = []
    for p in sorted(ipc._RUNTIME.glob(f"bu-*{suffix}")):
        raw = p.name[3:-len(suffix)]
        try:
            ipc._check(raw)
        except ValueError:
            continue
        names.append(raw)
    return names


def _daemon_browser_connection(name):
    c = None
    try:
        c, token = ipc.connect(name, timeout=1.0)
        response = ipc.request(c, token, {"meta": "connection_status"})
        if "error" in response:
            return None
        page = response.get("page")
        if page:
            page = {"title": page.get("title") or "(untitled)", "url": page.get("url") or ""}
        return {"name": name, "page": page}
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError, KeyError, ValueError, json.JSONDecodeError):
        return None
    finally:
        if c:
            c.close()


def daemon_browser_ready(name=None):
    """Whether the selected daemon has a healthy attached browser connection."""
    return _daemon_browser_connection(name or NAME) is not None


def browser_connections():
    """Live browser-harness daemons with healthy CDP browser connections and their attached page."""
    out = []
    for name in _daemon_endpoint_names():
        conn = _daemon_browser_connection(name)
        if conn:
            out.append(conn)
    return out


def active_browser_connections():
    """Count live browser-harness daemons with a healthy CDP browser connection."""
    return len(browser_connections())


def _doctor_short_text(value, limit=None):
    limit = limit or DOCTOR_TEXT_LIMIT
    value = str(value)
    return value if len(value) <= limit else value[:limit - 3] + "..."


def _is_snap_browser(path: str) -> bool:
    """True when a Chrome binary path lives under /snap/ (Snap confinement on Linux)."""
    return bool(path) and "/snap/" in path.lower()


def _doctor_snap_probe_path(path: str) -> str:
    raw = str(path)
    try:
        resolved = os.path.realpath(raw)
    except OSError:
        resolved = raw
    return raw if _is_snap_browser(raw) else resolved


def _doctor_probe_chrome_binary_for_snap():
    """Return (label, probe_path) for the first Chrome/Chromium binary found, else (None, None).

    Honors BH_CHROME_PATH and CHROME_PATH before searching PATH for common names.
    """
    import shutil

    for key in ("BH_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        p = Path(raw).expanduser()
        try:
            if p.is_file():
                return (p.name, _doctor_snap_probe_path(str(p)))
        except OSError:
            continue
    for cmd in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium"):
        w = shutil.which(cmd)
        if not w:
            continue
        try:
            return (cmd, _doctor_snap_probe_path(w))
        except OSError:
            continue
    return (None, None)


def _snap_linux_headless_doc_url():
    return "https://github.com/raystyle/browser-harness/blob/main/docs/snap-linux-headless.md"


def run_doctor_fix_snap():
    """Print steps to replace Snap Chromium with a native Chrome for CDP. Always exit 0."""
    doc = _snap_linux_headless_doc_url()
    print("browser-harness doctor --fix-snap")
    print()
    print("Snap-packaged Chromium cannot expose DevTools the way browser-harness needs.")
    print(f"Full background: {doc}")
    print()
    print("1. Install Google Chrome from Google's .deb (not the Snap store):")
    print("   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
    print("   sudo apt install ./google-chrome-stable_current_amd64.deb")
    print()
    print("2. Point the harness (and your shell) at the native binary so PATH does not")
    print("   pick the Snap wrapper first. Example for bash (~/.bashrc or session env):")
    print("   export BH_CHROME_PATH=/usr/bin/google-chrome-stable")
    print("   # CHROME_PATH is also honored by doctor's snap probe if you prefer that name.")
    print()
    print("3. Launch Chrome from that path (Way 2) or open Chrome normally (Way 1),")
    print("   enable remote debugging per install.md, then verify:")
    print("   browser-harness --doctor")
    print()
    return 0


# Scoped-task lifecycle bookkeeping (--once/--batch): a task only tears down
# what IT cold-started. Chrome/daemon already running at task start belongs to
# a persistent task or monitoring stack and is never touched.
_launched_chrome_here = False
_started_daemon_here = False


def _remove_task_profile():
    """Delete this isolated task's profile clone (task-isolation teardown).

    Guarded to the task-profiles root so a mis-set environment can never
    rmtree anything outside it."""
    raw = os.environ.get("BH_AGENT_CHROME_PROFILE") or ""
    if not raw:
        return
    try:
        p = Path(raw).expanduser()
        from .paths import home_dir

        if (home_dir() / "task-profiles") in p.parents:
            shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def teardown_scoped_stack():
    """End-of-invocation cleanup for --once/--batch tasks (see run.py).

    Rule: only stop what this process started. A scoped task that found the
    stack already up (persistent task's Chrome, monitoring daemon) leaves it
    exactly as found; a cold-started stack (daemon + agent Chrome) is taken
    back down. The Chrome stop yields to any other live daemon that may have
    attached to it — except on an isolated task stack (BH_ISOLATED_TASK=1),
    whose browser is exclusively this task's.

    Chrome goes down before the daemon: its graceful close (CDP Browser.close)
    rides on the still-live daemon."""
    global _launched_chrome_here, _started_daemon_here
    isolated = os.environ.get("BH_ISOLATED_TASK") == "1"
    if _launched_chrome_here:
        try:
            if not isolated:
                for other in ("default", "x-monitor"):
                    if other != NAME and daemon_alive(other):
                        print("browser-harness: scoped teardown: another daemon is attached -- leaving agent Chrome up")
                        break
                else:
                    _stop_agent_chrome()
            else:
                _stop_agent_chrome()  # task browser is exclusively ours
        except Exception as exc:
            print(f"browser-harness: scoped teardown: chrome stop skipped: {exc}", file=sys.stderr)
    try:
        if _started_daemon_here:
            restart_daemon()  # stop-only semantics (docstring: callers follow with a fresh start)
    except Exception as exc:
        print(f"browser-harness: scoped teardown: daemon stop skipped: {exc}", file=sys.stderr)
    if isolated:
        _remove_task_profile()
    _launched_chrome_here = False
    _started_daemon_here = False


def ensure_daemon(wait=60.0, name=None, env=None):
    """Idempotent. Self-heals stale daemon, closed Chrome (launches it), cold
    Chrome, and missing Allow on chrome://inspect."""
    if daemon_alive(name):
        # Stale daemons accept connects AND reply to meta:* (pure Python) even when the
        # CDP WS to Chrome is dead — probe with a real CDP call and require "result".
        # Must go through ipc.connect so this works on Windows (TCP loopback) too;
        # raw AF_UNIX here would fail on every warm call and churn the daemon.
        for last in (False, True):
            try:
                s, token = ipc.connect(name or NAME, timeout=3.0)
                resp = ipc.request(s, token, {"method": "Target.getTargets", "params": {}})
                if "result" in resp: return
            except Exception:
                pass
            if not last: time.sleep(0.5)
        restart_daemon(name)

    import subprocess, sys
    local = _is_local_chrome_mode(env)
    if not local and _pinned_agent_cdp(env):
        # The pinned agent Chrome is the only browser this daemon may touch;
        # start it up front instead of letting get_ws_url dead-wait 30s.
        if not _agent_chrome_running() and _launch_agent_chrome():
            print("browser-harness: agent Chrome isn't running — launching it.", file=sys.stderr)
    launched_browser = None
    opened_inspect = False
    for _ in range(3):
        e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
        try:
            stderr_sink = open(ipc.log_path(name or NAME), "ab")
        except OSError:
            stderr_sink = subprocess.DEVNULL
        p = subprocess.Popen(
            [sys.executable, "-m", "browser_harness.daemon"],
            env=e, stdout=subprocess.DEVNULL, stderr=stderr_sink, **ipc.spawn_kwargs(),
        )
        if name in (None, NAME):
            global _started_daemon_here
            _started_daemon_here = True  # scoped teardown stops what we cold-started
        if stderr_sink is not subprocess.DEVNULL:
            stderr_sink.close()
        spawned = time.time()
        deadline = spawned + wait
        hinted = not local
        while time.time() < deadline:
            if daemon_alive(name):
                _cleanup_unattached_browser_launch(launched_browser)
                return
            if p.poll() is not None: break
            if not hinted and time.time() - spawned > 2 and (_log_tail(name) or "").startswith("handshake-wait"):
                action = (
                    "run `browser-harness mac-approve` in another shell or click Allow"
                    if sys.platform == "darwin"
                    else "click Allow"
                )
                print(
                    f'browser-harness: Chrome is asking "Allow remote debugging?" — {action} to continue.',
                    file=sys.stderr,
                )
                hinted = True
            time.sleep(0.2)
        msg = _log_tail(name) or ""
        if local and msg.startswith("handshake-wait"):
            restart_daemon(name)
            raise RuntimeError(
                "permission-blocked: Chrome's Allow popup was not clicked in time -- wait for the user to click Allow, then retry."
            )
        if local and _needs_chrome_permission_popup(msg):
            print('browser-harness: Chrome is asking "Allow remote debugging?". Click Allow in Chrome, then retry browser work.', file=sys.stderr)
            restart_daemon(name)
            raise RuntimeError(
                "permission-blocked: wait for the user to click Allow in the Chrome permission popup before retrying."
            )
        if local and launched_browser is None and _chrome_not_running(msg):
            # Chrome is closed — launch the browser and retry
            restart_daemon(name)
            launched_browser = _launch_browser()
            if launched_browser is None:
                raise RuntimeError(
                    "chrome-not-running: no supported browser is running and none could be launched -- ask the user to open Chrome, then retry."
                )
            print("browser-harness: Chrome isn't running — launching it. If Chrome shows an \"Allow remote debugging?\" popup, click Allow.", file=sys.stderr)
            from .daemon import supported_browser_running
            boot_deadline = time.time() + 15
            while time.time() < boot_deadline and not supported_browser_running():
                time.sleep(0.3)
            continue
        if local and not opened_inspect and _needs_chrome_remote_debugging_prompt(msg):
            opened_inspect = True
            from .daemon import remote_debugging_toggle_profiles, remote_debugging_user_enabled
            if remote_debugging_user_enabled():
                # chrome://inspect toggle is already on — connection died
                print('browser-harness: Chrome is asking "Allow remote debugging?". Click Allow in Chrome, then retry browser work.', file=sys.stderr)
                restart_daemon(name)
                raise RuntimeError(
                    "permission-blocked: wait for the user to click Allow in the Chrome permission popup before retrying."
                )
            restart_daemon(name)
            _open_chrome_inspect_once()
            if remote_debugging_toggle_profiles():
                # Toggle already ticked from a previous run, but Chrome 144+
                # wants new Allow for this browser run.
                todo = 'click Allow on Chrome\'s "Allow remote debugging?" popup (the checkbox is already ticked; if no popup appears, untick and re-tick it)'
            else:
                todo = 'tick "Allow remote debugging for this browser instance" and click Allow on the popup'
            raise RuntimeError(
                f"remote-debugging-setup: opened chrome://inspect/#remote-debugging in Chrome -- ask the user to {todo}. "
                "Warn them Chrome shows ONE more Allow popup when the harness connects on the next attempt (per-connection approval; it is expected, not a re-ask). "
                "Retry after the user confirms; do not retry before."
            )
        raise RuntimeError(msg or f"daemon {name or NAME} didn't come up -- check {ipc.log_path(name or NAME)}")


def require_existing_daemon(name=None):
    """Require a healthy existing daemon without spawning or reconnecting.

    Trusted orchestrators use this after they provision a scoped CDP transport.
    Failing closed prevents a later CLI call from silently discovering a
    different local Chrome when that orchestrator-owned daemon dies.
    """
    daemon_name = name or NAME
    if not daemon_alive(daemon_name):
        raise RuntimeError(f"required daemon {daemon_name!r} is not running")
    try:
        s, token = ipc.connect(daemon_name, timeout=3.0)
        try:
            resp = ipc.request(s, token, {"method": "Target.getTargets", "params": {}})
        finally:
            s.close()
    except Exception as exc:
        raise RuntimeError(f"required daemon {daemon_name!r} is unhealthy: {exc}") from exc
    if not isinstance(resp, dict) or "result" not in resp:
        raise RuntimeError(f"required daemon {daemon_name!r} failed its CDP health check")


def _pid_alive(pid):
    """Cross-platform liveness probe for the shutdown wait.

    os.kill(pid, 0) is unusable on Windows: signal 0 is CTRL_C_EVENT there —
    for a detached daemon it errors (falsely "dead"), for a console process
    it would inject a real Ctrl+C. OpenProcess(SYNCHRONIZE) is the safe check.
    """
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # POSIX EPERM: exists but owned by another user
    except OSError:
        return False


def restart_daemon(name=None, require_clean=False):
    """Best-effort daemon shutdown + socket/pid cleanup.

    Name is historical: callers typically follow this with another
    `browser-harness` invocation, which auto-spawns a fresh daemon via
    ensure_daemon(). The function itself only stops.

    With require_clean=True, an unavailable daemon or any response other than
    {"ok": true} raises before endpoint cleanup or process termination.

    Identity is verified via ipc.identify() before any process signal, so
    a stale pid file whose number has been reused by an unrelated process
    is never SIGTERM'd. If the daemon is unreachable, we just clean up the
    pid file and socket and return — never escalate to a kill-by-pid-file.
    """
    import signal

    name = name or NAME
    pid_path = str(ipc.pid_path(name))

    daemon_pid = ipc.identify(name, timeout=5.0)
    daemon_alive = daemon_pid is not None or ipc.ping(name, timeout=1.0)
    if require_clean and not daemon_alive:
        raise RuntimeError(f"daemon {name!r} is unavailable for required clean shutdown")
    daemon_start = _process_start_time(daemon_pid)

    if daemon_alive:
        c = None
        try:
            c, token = ipc.connect(name, timeout=50.0 if require_clean else 5.0)
            response = ipc.request(c, token, {"meta": "shutdown"})
            if require_clean and (
                not isinstance(response, dict)
                or response.get("ok") is not True
                or bool(response.get("error"))
            ):
                error = response.get("error") if isinstance(response, dict) else None
                raise RuntimeError(error or f"daemon {name!r} did not confirm clean shutdown")
        except Exception as exc:
            if require_clean:
                if isinstance(exc, RuntimeError):
                    raise
                raise RuntimeError(
                    f"daemon {name!r} did not confirm clean shutdown: {exc}"
                ) from exc
        finally:
            if c is not None:
                close = getattr(c, "close", None)
                if close:
                    close()

    if daemon_pid is not None:
        for _ in range(75):
            if not _pid_alive(daemon_pid):
                break
            time.sleep(0.2)
        else:
            verified_pid = ipc.identify(name, timeout=1.0)
            same_process = verified_pid == daemon_pid or (
                daemon_start is not None
                and _process_start_time(daemon_pid) == daemon_start
            )
            if same_process:
                try:
                    os.kill(daemon_pid, signal.SIGTERM)
                except (ProcessLookupError, OSError, SystemError, OverflowError):
                    pass

    ipc.cleanup_endpoint(name)
    try:
        os.unlink(pid_path)
    except FileNotFoundError:
        pass


def _version():
    """Installed version of the browser-harness package. Empty string if unknown."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("browser-harness")
        except PackageNotFoundError:
            return ""
    except Exception:
        return ""


def _repo_dir():
    """Return the repo root if this install is an editable git clone, else None."""
    for p in Path(__file__).resolve().parents:
        if (p / ".git").is_dir():
            return p
    return None


def _install_mode():
    """"git" for editable clone, "installed" for a uv tool install, "unknown" otherwise."""
    if _repo_dir():
        return "git"
    return "installed" if _version() else "unknown"


def _cache_read():
    try:
        return json.loads(VERSION_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _cache_write(data):
    try:
        VERSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_CACHE.write_text(json.dumps(data))
        try:
            os.chmod(VERSION_CACHE, 0o600)
        except OSError:
            pass
    except OSError:
        pass


def _latest_release_tag(force=False):
    """Return the latest GitHub release tag for this fork, or None."""
    cache = _cache_read()
    now = time.time()
    if not force and cache.get("tag") and now - cache.get("fetched_at", 0) < VERSION_CACHE_TTL:
        # A cached tag that is not newer than the installed version proves
        # nothing: the cache may predate both a manual upgrade and a newer
        # release (verified twice: 0.5.0-cache hid 0.6.1, 0.6.1-cache hid
        # 0.6.2). Only a tag > installed may short-circuit; else refetch.
        cur = _version()
        if not cur or _version_tuple(cache["tag"]) > _version_tuple(cur):
            return cache["tag"]
    try:
        tag = json.loads(urllib.request.urlopen(GITHUB_RELEASE_API, timeout=5).read()).get("tag_name") or ""
    except Exception:
        return cache.get("tag")  # fall back to last known
    tag = tag.lstrip("v")
    _cache_write({**cache, "tag": tag, "fetched_at": now})
    return tag or None


def _version_tuple(v):
    """Best-effort PEP 440-ish parse: alpha < beta < rc < final."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?", v or "", re.I)
    if not m:
        return (0, 0, 0, 3, 0)
    nums = [int(p) for p in m.group(1).split(".")[:3]]
    nums.extend([0] * (3 - len(nums)))
    pre = (m.group(2) or "").lower()
    pre_rank = {"a": 0, "b": 1, "rc": 2}.get(pre, 3)
    pre_num = int(m.group(3) or 0)
    return (*nums, pre_rank, pre_num)


def check_for_update():
    """(current, latest, newer_available). latest may be None if the API was unreachable and no cache exists."""
    cur = _version()
    latest = _latest_release_tag()
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    return cur, latest, newer


def print_update_banner(out=None):
    """Print the update banner to stderr once per day. Silent when up-to-date or offline."""
    import sys
    if os.environ.get("BH_UPDATE_CHECK", "").strip().lower() in {"0", "false", "no", "off"}:
        return
    out = out or sys.stderr
    cache = _cache_read()
    today = time.strftime("%Y-%m-%d")
    if cache.get("banner_shown_on") == today:
        return
    cur, latest, newer = check_for_update()
    if not newer:
        return
    print(f"[browser-harness] update available: {cur} -> {latest}", file=out)
    print(f"[browser-harness] agents: run `browser-harness --update -y` to upgrade and restart the daemon", file=out)
    _cache_write({**cache, "banner_shown_on": today})


def _chrome_running():
    """Cross-platform best-effort check for a running Chromium-based browser."""
    import platform, subprocess
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.check_output(["tasklist"], text=True, errors="replace", timeout=5)
            names = ("chrome.exe", "msedge.exe", "helium.exe")
        else:
            out = subprocess.check_output(["ps", "-A", "-o", "comm="], text=True, errors="replace", timeout=5)
            names = ("Google Chrome", "chrome", "chromium", "Microsoft Edge", "msedge", "helium")
        return any(n.lower() in out.lower() for n in names)
    except Exception:
        return False


_BROWSER_LAUNCH = (
    # (profile-dir fragment, macOS app name, POSIX commands, Windows `start` target)
    ("chrome canary", "Google Chrome Canary", ("google-chrome-canary",), "chrome"),
    ("chromium", "Chromium", ("chromium", "chromium-browser"), "chromium"),
    ("chrome", "Google Chrome", ("google-chrome-stable", "google-chrome"), "chrome"),
    ("edge", "Microsoft Edge", ("microsoft-edge", "microsoft-edge-stable"), "msedge"),
    ("brave", "Brave Browser", ("brave-browser", "brave"), "brave"),
    ("arc", "Arc", (), None),
    ("dia", "Dia", (), None),
    ("comet", "Comet", (), None),
)
_DEFAULT_LAUNCH = (
    "Google Chrome",
    ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "microsoft-edge"),
    "chrome",
)


def _browser_launch_spec(base):
    """(mac app, posix commands, windows target) for the browser w profile dir"""
    tail = "/".join(p.lower() for p in Path(base).parts[-2:])
    for frag, mac_app, posix_cmds, win_target in _BROWSER_LAUNCH:
        if frag in tail:
            return (mac_app, posix_cmds, win_target)
    return _DEFAULT_LAUNCH


def _browser_binary_matches_profile(binary, base):
    """True when an explicit browser binary belongs to ``base``."""
    name = Path(binary).name.lower().removesuffix(".exe")
    mac_app, posix_cmds, win_target = _browser_launch_spec(base)
    candidates = (mac_app, *posix_cmds, win_target)

    def normalize(value):
        return "".join(char for char in (value or "").lower() if char.isalnum())

    normalized_name = normalize(name)
    return any(normalized_name == normalize(candidate) for candidate in candidates)


def _profile_directory_args(base):
    """Relaunch skips Chrome's profile picker"""
    if not base:
        return []
    try:
        state = json.loads((Path(base) / "Local State").read_text(encoding="utf-8", errors="replace"))
        last = ((state.get("profile") or {}).get("last_used")) or "Default"
    except (OSError, ValueError, AttributeError):
        last = "Default"
    if not isinstance(last, str) or not (Path(base) / last).is_dir():
        return []
    return [f"--profile-directory={last}"]


_NO_THROTTLE_FLAGS = (
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion",
)


def _agent_port():
    """CDP port of the isolated agent Chrome: BH_AGENT_CDP_PORT or 9223.

    A WSL2 mirrored-network host shares loopback with the Windows side, where
    the Windows stack already owns 9223; WSL points this at its own port so
    the two agent Chromes never collide.
    """
    raw = (os.environ.get("BH_AGENT_CDP_PORT") or "").strip()
    try:
        return int(raw) if raw else 9223
    except ValueError:
        return 9223


_AGENT_PORT = _agent_port()


def _agent_profile():
    """Agent Chrome user-data-dir: BH_AGENT_CHROME_PROFILE or <BH_HOME>/agent-chrome-profile."""
    raw = os.environ.get("BH_AGENT_CHROME_PROFILE")
    if raw:
        return Path(raw).expanduser().resolve()
    from .paths import home_dir

    return home_dir() / "agent-chrome-profile"


def _agent_chrome_running() -> bool:
    import urllib.request

    try:
        urllib.request.urlopen(f"http://127.0.0.1:{_AGENT_PORT}/json/version", timeout=2)
        return True
    except Exception:
        return False


def _chrome_path():
    import platform
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


def _headless_flags():
    """Headless flags for agent Chrome.

    BH_CHROME_HEADLESS=1 forces headless; =0 keeps a window even where the
    auto-detect below would kick in. Unset: headless only on Linux with no
    DISPLAY and no WAYLAND_DISPLAY — a machine with no screen can't host a
    browser window, and WSLg boxes that want headless opt in explicitly.
    """
    raw = (os.environ.get("BH_CHROME_HEADLESS") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return []
    enabled = raw in ("1", "true", "yes", "on")
    if not enabled and sys.platform.startswith("linux"):
        enabled = not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if not enabled:
        return []
    flags = ["--headless=new", "--disable-gpu"]
    # Chrome refuses to start as root without it (containers, WSL as root).
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        flags.append("--no-sandbox")
    return flags


def _normalize_chrome_exit_type():
    """Mark the agent profile's last exit as clean so the next launch doesn't
    show the 'Chrome didn't shut down correctly' restore bubble.

    Every stop path kills by pid, and on Windows os.kill is always
    TerminateProcess — SIGTERM included — so Chrome never writes its clean
    exit_type and the profile stays flagged Crashed. Patch Preferences while
    Chrome is down: after a stop (the kill we just did), and before a launch
    (the belt for power loss / foreign killers). Must only run with Chrome
    stopped, or its own exit rewrite lands on top of ours."""
    pref_path = _agent_profile() / "Default" / "Preferences"
    try:
        prefs = json.loads(pref_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    profile = prefs.get("profile")
    if not isinstance(profile, dict) or profile.get("exit_type") in (None, "Normal"):
        return
    profile["exit_type"] = "Normal"
    try:
        pref_path.write_text(json.dumps(prefs), encoding="utf-8")
    except OSError:
        pass


def _launch_agent_chrome() -> bool:
    """Start the isolated agent Chrome if it is not already up. Blocks up to 20s.

    The user-data-dir flag must stay unquoted (M101: quoting once leaked the
    launch into the user's default profile). Concurrent callers (chrome-mode
    flip, x-monitor worker respawn, two CLI cold starts) serialize on a
    kernel lock, same primitive as the daemon single-instance guard (M109):
    the check→Popen→port-ready window is several seconds wide, and a loser
    racing through it double-launches — on macOS `open -na` materializes that
    as a real second instance (S008 遗留 race). The loser instead out-waits
    the holder and piggybacks on its Chrome."""
    import platform
    import subprocess
    import time

    if _agent_chrome_running():
        return True
    fd, _holder = ipc.acquire_lock(f"agent-chrome-{_AGENT_PORT}")
    if fd is None:
        deadline = time.time() + 30  # out-wait the holder's 20s launch window
        while time.time() < deadline:
            if _agent_chrome_running():
                return True
            time.sleep(0.5)
        return False
    try:
        if _agent_chrome_running():  # re-check under the lock: holder may have finished
            return True
        chrome = _chrome_path()
        if not chrome:
            return False
        _normalize_chrome_exit_type()
        flags = [
            f"--user-data-dir={_agent_profile()}",
            f"--remote-debugging-port={_AGENT_PORT}",
            "--hide-crash-restore-bubble",  # belt: a mid-session real crash must not nag either
            *_NO_THROTTLE_FLAGS,
            *_headless_flags(),
            *_extra_chrome_flags(),
        ]
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", "-na", "Google Chrome", "--args", *flags])
            else:
                subprocess.Popen([chrome, *flags], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return False
        global _launched_chrome_here
        _launched_chrome_here = True  # scoped teardown stops what we cold-started
        deadline = time.time() + 20
        while time.time() < deadline:
            if _agent_chrome_running():
                return True
            time.sleep(0.5)
        return False
    finally:
        os.close(fd)


def _agent_chrome_headless() -> bool | None:
    """Live headless state of the agent Chrome from its UA; None if not running."""
    try:
        info = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{_AGENT_PORT}/json/version", timeout=2))
    except Exception:
        return None
    return "HeadlessChrome" in (info.get("User-Agent") or "")


def _agent_chrome_pids() -> list[int]:
    """Main-process pids of the isolated agent Chrome — never the user's Chrome.

    Matched by user-data-dir (or CDP port) against the process list, so a flip
    can stop exactly the agent instance without pkill-style collateral damage.
    """
    import platform

    from . import browsers

    system = platform.system()
    if system == "Windows":
        instances = browsers._chrome_instances_windows()
    elif system == "Linux":
        instances = browsers._chrome_instances_linux()
    elif system == "Darwin":
        instances = browsers._chrome_instances_darwin()
    else:
        return []
    profile = _agent_profile()
    pids = []
    for inst in instances:
        data_dir = inst.get("data_dir") or ""
        if not data_dir or data_dir == "default":
            continue
        try:
            same_dir = Path(data_dir).expanduser().resolve() == profile
        except OSError:
            same_dir = False
        if same_dir or inst.get("port") == _AGENT_PORT:
            pids.append(inst["pid"])
    return pids


def _graceful_close_agent_chrome(timeout: float = 15.0) -> bool:
    """Close the agent Chrome the CDP way, relayed by the live daemon:
    Browser.close lets Chrome write its own clean shutdown state. pid kills
    stay the fallback for when no daemon is reachable. True iff the debug
    port died (the daemon judges by that event, not by the command reply)."""
    try:
        c, token = ipc.connect(NAME, timeout=2.0)
    except Exception:
        return False
    try:
        c.settimeout(timeout)
        return bool(ipc.request(c, token, {"meta": "close_browser"}).get("closed"))
    except Exception:
        return False
    finally:
        c.close()


def _stop_agent_chrome(timeout: float = 10.0) -> bool:
    """Stop the agent Chrome. Graceful first (CDP Browser.close via the live
    daemon — Chrome writes clean exit state itself); pid kills only fallback."""
    import signal

    if _graceful_close_agent_chrome():
        return True

    pids = _agent_chrome_pids()
    if not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    deadline = time.time() + timeout
    while time.time() < deadline and _agent_chrome_running():
        time.sleep(0.3)
    if _agent_chrome_running():
        for pid in pids:
            try:
                # No SIGKILL on Windows (AttributeError — the escalation itself
                # used to crash there); os.kill on Windows is always
                # TerminateProcess, so the SIGTERM re-send IS the force kill.
                os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
            except (ProcessLookupError, PermissionError, OSError):
                pass
    if not _agent_chrome_running():
        _normalize_chrome_exit_type()  # pid kills leave exit_type=Crashed; the
        # next launch would greet with the restore bubble (Windows TerminateProcess)
    return True


def _set_env_value(key: str, value: str) -> None:
    """Persist key=value in BH_HOME/.env — replace the existing line or append.

    .env stays the single source of truth for the launch mode: the next CLI
    call (and the daemon it spawns) reloads it via setdefault.
    """
    env_path = paths.home_dir() / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        lines = []
    prefix = f"{key}="
    out, replaced = [], False
    for line in lines:
        if not replaced and line.strip().startswith(prefix) and not line.strip().startswith("#"):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def run_chrome_mode(args: list[str]) -> int:
    """Show or flip the agent Chrome between headless and headed.

    All apps inherit the mode (they ride the same agent Chrome), which is what
    makes manual login entry possible: flip headed, log in by hand in the
    visible window, flip back — cookies persist in the agent profile. The
    flip rewrites BH_CHROME_HEADLESS in BH_HOME/.env, stops the daemons (they
    baked the old mode at spawn) and the agent Chrome, and relaunches fresh;
    a running x-monitor stack is brought back after (idempotent).
    """
    mode = args[0] if args else "status"
    if mode not in ("status", "headed", "headless") or len(args) != 1:
        print("usage: browser-harness chrome-mode [status|headed|headless]", file=sys.stderr)
        return 2
    if mode == "status":
        raw = (os.environ.get("BH_CHROME_HEADLESS") or "").strip().lower() or "(unset — auto)"
        live = _agent_chrome_headless()
        state = "not running" if live is None else ("headless" if live else "headed")
        print("browser-harness chrome-mode")
        print(f"  .env BH_CHROME_HEADLESS: {raw}")
        print(f"  agent Chrome now:        {state}")
        return 0

    target = mode == "headless"
    live = _agent_chrome_headless()
    if live == target:
        _set_env_value("BH_CHROME_HEADLESS", "1" if target else "0")
        print(f"agent Chrome already {'headless' if target else 'headed'} — .env aligned")
        return 0
    if not _pinned_agent_cdp(None):
        print(
            "chrome-mode applies to the isolated agent Chrome model "
            "(BU_CDP_URL/BU_CDP_WS); this daemon attaches to a user browser",
            file=sys.stderr,
        )
        return 1

    if not target:
        print("opening a visible agent Chrome window for manual login — "
              "log in by hand there, then `browser-harness chrome-mode headless`")
    _set_env_value("BH_CHROME_HEADLESS", "1" if target else "0")
    os.environ["BH_CHROME_HEADLESS"] = "1" if target else "0"

    had_x_monitor = False
    try:
        from .rmux import Rmux

        r = Rmux()
        if r.server_running():
            had_x_monitor = r.has_session("x-supervisor")
            if had_x_monitor:
                # Quiesce the stack BEFORE touching daemons/Chrome: a live
                # worker that notices its daemon gone respawns it via its own
                # ensure path, relaunching Chrome mid-flip with the stale mode
                # and racing the flip's own stop/launch (S008 double-launch).
                # _restart_x_monitor() brings the whole stack back afterwards.
                print("stopping x-monitor rmux stack (a live worker would respawn mid-flip)...")
                for session in ("x-monitor", "x-supervisor"):
                    try:
                        r.kill_session(session)
                    except Exception:
                        pass
    except Exception:
        pass
    for nm in (NAME, "x-monitor"):
        try:
            if daemon_alive(nm):
                print(f"stopping {nm} daemon (it baked the old mode)...")
                restart_daemon(nm)
        except Exception as exc:
            print(f"daemon {nm} stop skipped: {exc}")
    if _agent_chrome_headless() is not None:
        print("stopping agent Chrome...")
        _stop_agent_chrome()
    try:
        ensure_daemon()  # spawns a fresh daemon that launches Chrome in the new mode
    except RuntimeError as exc:
        print(f"browser-harness: {exc}", file=sys.stderr)
        return 1
    if had_x_monitor:
        print("restoring x-monitor...")
        _restart_x_monitor()
    live = _agent_chrome_headless()
    state = "not running" if live is None else ("headless" if live else "headed")
    print(f"agent Chrome now: {state}")
    return 0 if live == target else 1


def _extra_chrome_flags():
    """Flags appended only when harness itself launches Chrome.

    An already-running Chrome (with an existing session) is attached as-is;
    flags cannot be applied to a process that was not started with them.
    """
    flags = [f for f in (os.environ.get("BH_CHROME_EXTRA_FLAGS") or "").split() if f]
    if (os.environ.get("BH_NO_THROTTLE") or "").strip().lower() in ("1", "true", "yes", "on"):
        flags.extend(_NO_THROTTLE_FLAGS)
    return flags


def _launch_browser():
    """Prefers the browser whose profile already has perm box checked.

    Returns ``(process, profile)`` on success. ``process`` is available only
    when we launched the browser directly; ``profile`` is the user-data dir we
    expect that browser to use. The caller uses both to clean up a direct
    launch that never becomes reachable over CDP.
    """
    import platform, shutil, subprocess
    from .daemon import PROFILES, remote_debugging_toggle_profiles

    enabled = remote_debugging_toggle_profiles()
    known_profiles = enabled + [
        base for base in PROFILES if base not in enabled and (base / "Local State").exists()
    ]
    system = platform.system()
    extra = _extra_chrome_flags()
    for key in ("BH_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if raw and Path(raw).expanduser().is_file():
            try:
                binary = Path(raw).expanduser()
                process = subprocess.Popen(
                    [str(binary)] + extra,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **ipc.spawn_kwargs(),
                )
                profile = next(
                    (base for base in known_profiles if _browser_binary_matches_profile(binary, base)),
                    None,
                ) if system not in ("Darwin", "Windows") else None
                return process, profile
            except (OSError, subprocess.SubprocessError):
                # A path that exists but can't execute (permissions, wrong arch)
                # must fall through to normal discovery, not abort
                continue

    base = enabled[0] if enabled else next((b for b in PROFILES if (b / "Local State").exists()), None)
    mac_app, posix_cmds, win_target = _browser_launch_spec(base) if base else _DEFAULT_LAUNCH
    profile_args = _profile_directory_args(base)
    try:
        if system == "Darwin":
            tail = profile_args + extra
            cmd = ["open", "-a", mac_app] + (["--args"] + tail if tail else [])
            r = subprocess.run(cmd, timeout=10, check=False, capture_output=True)
            if r.returncode != 0 and mac_app != "Google Chrome":
                # Different app → its profile dir may not match; launch plain
                r = subprocess.run(["open", "-a", "Google Chrome"] + (["--args"] + tail if tail else []), timeout=10, check=False, capture_output=True)
            return (None, base) if r.returncode == 0 else None
        if system == "Windows":
            # `start <name>` resolves browsers via App Paths without knowing the install dir
            subprocess.Popen(["cmd", "/c", "start", "", win_target or "chrome"] + profile_args + extra, **ipc.spawn_kwargs())
            return None, base
        for cmd in posix_cmds or _DEFAULT_LAUNCH[1]:
            w = shutil.which(cmd)
            if w:
                process = subprocess.Popen(
                    [w] + profile_args + extra,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **ipc.spawn_kwargs(),
                )
                return process, base
        return None
    except (OSError, subprocess.SubprocessError):
        return None


def _cleanup_unattached_browser_launch(launch):
    """Stop a browser we launched when the daemon attached somewhere else."""
    if not launch:
        return
    process, profile = launch
    if process is None or profile is None or process.poll() is not None:
        return

    from .daemon import _devtools_port_live

    if _devtools_port_live(profile):
        return

    import signal

    try:
        if ipc.IS_WINDOWS:
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        pass


def _open_chrome_inspect():
    """Open chrome://inspect/#remote-debugging so the user can tick the checkbox."""
    import platform, subprocess, webbrowser
    url = "chrome://inspect/#remote-debugging"
    if platform.system() == "Darwin":
        try:
            r = subprocess.run([
                "osascript",
                "-e", 'tell application "Google Chrome" to activate',
                "-e", f'tell application "Google Chrome" to open location "{url}"',
            ], timeout=5, check=False, capture_output=True)
            if r.returncode == 0:
                return True
        except Exception:
            pass
    try:
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False


INSPECT_REOPEN_TTL = 180.0  # seconds open new chrome://inspect tab


def _open_chrome_inspect_once():
    """Open chrome://inspect at most once per INSPECT_REOPEN_TTL across invocations"""
    marker = paths.inspect_marker()
    try:
        if time.time() - marker.stat().st_mtime < INSPECT_REOPEN_TTL:
            return
    except OSError:
        pass
    if not _open_chrome_inspect():
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        pass


def run_doctor():
    """Read-only diagnostics. Exit 0 iff everything looks healthy."""
    import platform, sys
    cur = _version()
    mode = _install_mode()
    chrome = _chrome_running()
    daemon = daemon_alive()
    connections = browser_connections()
    latest = _latest_release_tag()
    # Only claim an update when we know the installed version — `cur or "(unknown)"`
    # for display would otherwise be parsed as (0,) and flag every latest as newer.
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    cur_display = cur or "(unknown)"
    doc_url = _snap_linux_headless_doc_url()

    def row(label, ok, detail=""):
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")

    print("browser-harness doctor")
    print(f"  platform          {platform.system()} {platform.release()}")
    print(f"  python            {sys.version.split()[0]}")
    print(f"  version           {cur_display} ({mode})")
    if latest:
        print(f"  latest release    {latest}" + (" (update available)" if newer else ""))
    else:
        print("  latest release    (could not reach GitHub releases)")
    if platform.system() == "Linux":
        bname, bpath = _doctor_probe_chrome_binary_for_snap()
        if bname and bpath and _is_snap_browser(bpath):
            print("[snap-detect]")
            print(f"Browser: {bname} (snap) — WARNING: Snap confinement prevents CDP binding.")
            print(f"  Fix: Install Chrome natively (see docs/snap-linux-headless.md)")
            print(f"  Docs: {doc_url}")
    row("chrome running", chrome, "" if chrome else "start chrome/edge")
    row("daemon alive", daemon, "" if daemon else "see install.md")
    row("active browser connections", bool(connections), str(len(connections)))
    for conn in connections:
        page = conn.get("page")
        if page:
            title = _doctor_short_text(page["title"])
            url = _doctor_short_text(page["url"])
            print(f"        {conn['name']} — active page: {title} — {url}")
        else:
            print(f"        {conn['name']} — active page: (no real page)")
    try:
        from .rmux import rmux_binary
        rmux_det = rmux_binary()
    except Exception:
        rmux_det = None
    row("rmux", bool(rmux_det), f"{rmux_det[1]} ({rmux_det[0]})" if rmux_det else "not installed (needed by x-monitor)")
    # Core health = chrome + daemon.
    return 0 if (chrome and daemon) else 1


def run_doctor_json(require_existing_daemon=False):
    """Print a stable, non-networked runtime health report as JSON.

    The strict mode is intended for trusted orchestrators that provision an
    exact named daemon. It checks only that selected daemon and its live CDP
    connection; it never starts, repairs, or discovers another daemon.
    """
    strict = bool(require_existing_daemon)
    chrome = None if strict else _chrome_running()
    browser_ready = daemon_browser_ready(NAME)
    daemon = browser_ready or daemon_alive(NAME)
    healthy = (daemon and browser_ready) if strict else (browser_ready or (chrome and daemon))
    try:
        from .rmux import rmux_binary
        rmux_det = rmux_binary()
    except Exception:
        rmux_det = None
    report = {
        "schema_version": 1,
        "healthy": healthy,
        "require_existing_daemon": strict,
        "version": _version() or None,
        "install_mode": _install_mode(),
        "chrome_running": chrome,
        "daemon": {
            "name": NAME,
            "alive": daemon,
            "browser_ready": browser_ready,
        },
        "rmux": {
            "installed": bool(rmux_det),
            "version": rmux_det[1] if rmux_det else None,
            "path": rmux_det[0] if rmux_det else None,
        },
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if healthy else 1


def _prompt_yes(question, default_yes=True, yes=False):
    if yes:
        return True
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        ans = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return default_yes
    if not ans:
        return default_yes
    return ans.startswith("y")


def _stop_stack_for_upgrade():
    """Best-effort stop of the running stack (rmux sessions + daemons) before
    replacing the tool venv. Windows refuses to delete files a running process
    holds, so both rmux-spawned workers and the daemons lock ``Scripts\\``
    (M102, twice verified).

    Returns True when the x-monitor supervisor session was running, so the
    caller can bring the monitoring stack back after the upgrade."""
    had_x_monitor = False
    try:
        from .rmux import Rmux
        r = Rmux()
        if r.server_running():
            had_x_monitor = r.has_session("x-supervisor")
            print("stopping rmux sessions (x-supervisor/x-worker)...")
            r.kill_server()
    except Exception as exc:
        print(f"rmux stop skipped: {exc}")
    for nm in (NAME, "x-monitor"):
        try:
            if daemon_alive(nm):
                print(f"stopping {nm} daemon...")
                restart_daemon(nm)
        except Exception as exc:
            print(f"daemon {nm} stop skipped: {exc}")
    return had_x_monitor


def _restart_x_monitor():
    """Bring the x-monitor stack back after an upgrade (idempotent app)."""
    exe = shutil.which("browser-harness")
    if exe:
        argv = [exe, "x-monitor"]
    else:
        argv = [sys.executable, "-c",
                "import sys; sys.argv = ['browser-harness', 'x-monitor']; "
                "from browser_harness.run import main; main()"]
    return subprocess.run(argv).returncode


def _provision_after_update():
    """Sync packaged skills + workspace payload (apps, domain-skills) so the
    machine matches the repo without a separate `skills sync` step."""
    try:
        from . import skills
        return skills.run_cli(["sync"])
    except Exception as exc:
        print(f"warning: skills/workspace sync failed: {exc} — run `browser-harness skills sync`",
              file=sys.stderr)
        return 1


def _relayed_tool_upgrade(had_x_monitor):
    """Hand the venv replacement to a shell that does NOT run from the venv.

    On Windows the update command itself executes from the tool venv's
    Scripts\\ and locks it, so an in-process `uv tool install` can never
    succeed — worse, it can half-demolish the install (verified: shim alive,
    package gone). The relayed shell waits for this process to exit, then
    installs, re-provisions, and restores the x-monitor stack when needed.

    Returns True when the relay was spawned successfully."""
    parent = os.getpid()
    tail = "browser-harness skills sync"
    if had_x_monitor:
        tail += "; browser-harness x-monitor"
    tail += "; browser-harness --version"
    script = (
        "for ($i = 0; $i -lt 150; $i++) {"
        f" if (-not (Get-Process -Id {parent} -ErrorAction SilentlyContinue)) {{ break }};"
        " Start-Sleep -Milliseconds 200 }; "
        f"uv tool install --force git+{GITHUB_REPO_URL}; "
        f"if ($LASTEXITCODE -eq 0) {{ {tail} }} "
        "else { Write-Host 'browser-harness upgrade failed; restore the stack with: browser-harness x-monitor' }"
    )
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        return False
    try:
        subprocess.Popen([shell, "-NoProfile", "-Command", script])
        return True
    except OSError as exc:
        print(f"relay spawn failed: {exc}", file=sys.stderr)
        return False


def run_update(yes=False):
    """Upgrade to the latest release and realign the machine with the repo.

    Installed mode is seamless: stop the running stack (rmux + daemons, so the
    venv is replaceable — M102), `uv tool install` the default-branch head (main), re-provision
    skills + workspace apps, and bring the x-monitor stack back if it was
    running. Exit 0 on success, non-zero on failure."""
    import subprocess, sys
    cur, latest, newer = check_for_update()
    # Only short-circuit as "up to date" when we actually know the installed
    # version. Otherwise `newer=False` just means "couldn't compare" — proceed.
    if cur and latest and not newer:
        print(f"browser-harness is up to date ({cur}).")
        _provision_after_update()  # realign skills/workspace even when the version matches
        return 0
    if cur and latest:
        print(f"updating browser-harness: {cur} -> {latest}")
    elif latest:
        print(f"installed version unknown; will try to update to {latest}.")
    else:
        print("could not reach GitHub releases; will try to update anyway.")

    mode = _install_mode()
    restart_stack = False
    if mode == "git":
        repo = _repo_dir()
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True)
        if status.returncode != 0:
            print(f"git status failed: {status.stderr.strip()}", file=sys.stderr)
            return 1
        if status.stdout.strip():
            print(f"refusing to update: uncommitted changes in {repo}", file=sys.stderr)
            print("commit or stash them first, or run `git -C %s pull` yourself." % repo, file=sys.stderr)
            return 1
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"])
        if r.returncode != 0:
            return r.returncode
    elif mode == "installed":
        restart_stack = _stop_stack_for_upgrade()
        if sys.platform == "win32" and _relayed_tool_upgrade(restart_stack):
            # The relay owns install + provision + stack-restore once we exit.
            # Invalidate the version cache now so the new install isn't flagged
            # against a stale cached tag.
            cache = _cache_read()
            cache.pop("banner_shown_on", None)
            cache.pop("tag", None)
            cache.pop("fetched_at", None)
            _cache_write(cache)
            print("update continues in this console — the running CLI cannot replace its own venv (M102);"
                  " this command returns now.")
            return 0
        if sys.platform == "win32":
            print("relay unavailable; trying in-place upgrade (the venv may be locked, M102)…", file=sys.stderr)
        tool_upgrade = subprocess.run([
            "uv", "tool", "install", "--force",
            f"git+{GITHUB_REPO_URL}",
        ])
        if tool_upgrade.returncode != 0:
            print("hint: a running browser-harness process can lock the venv on Windows (M102); close it and retry.",
                  file=sys.stderr)
            if restart_stack:
                _restart_x_monitor()  # best-effort: the old binary may still work
            return tool_upgrade.returncode
    else:
        print("unknown install mode; can't auto-update.", file=sys.stderr)
        return 1

    # Invalidate banner/tag cache so doctor reflects the new release immediately
    # (the tag cache otherwise lags up to VERSION_CACHE_TTL).
    cache = _cache_read()
    cache.pop("banner_shown_on", None)
    cache.pop("tag", None)
    cache.pop("fetched_at", None)
    _cache_write(cache)

    _provision_after_update()
    if mode == "installed":
        if restart_stack:
            print("restarting x-monitor...")
            if _restart_x_monitor() != 0:
                print("x-monitor restart failed; run `browser-harness x-monitor`.", file=sys.stderr)
        else:
            print("daemon stopped; it will auto-restart on next `browser-harness` call.")
    elif daemon_alive():
        if _prompt_yes("restart the running daemon so it picks up the new code?", default_yes=True, yes=yes):
            restart_daemon()
            print("daemon stopped; it will auto-restart on next `browser-harness` call.")
        else:
            print("daemon left running on old code. run `browser-harness` and it'll use the new code after the daemon recycles.")
    print("update complete.")
    return 0
