import os
import sys
import time

# Windows default stdout/stderr encoding is cp1252
# which can't encode the 🐴 marker helpers prepend to tab titles (or anything
# else outside the locale charset). Force UTF-8 so `print(page_info())` and
# tracebacks carrying page titles don't UnicodeEncodeError on Windows. #124(4).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from .admin import (
    _version,
    NAME,
    daemon_alive,
    ensure_daemon,
    print_update_banner,
    require_existing_daemon,
    restart_daemon,
    run_doctor,
    run_doctor_fix_snap,
    run_doctor_json,
    run_update,
)
from . import recorder
from .helpers import *

HELP = """Browser Harness

Read SKILL.md for the default workflow and examples.

Typical usage:
  @'
  ensure_real_tab()
  print(page_info())
  '@ | browser-harness

Helpers are pre-imported. The daemon auto-starts and connects to the running browser.

Commands:
  browser-harness --version        print the installed version
  browser-harness --doctor         diagnose install, daemon, and browser state
  browser-harness doctor           same as --doctor
  browser-harness doctor --json [--require-existing-daemon]
                                    print machine-readable runtime health
  browser-harness doctor --fix-snap   print how to fix Snap Chromium blocking CDP (Linux)
  browser-harness mac-approve         approve Chrome's macOS remote debugging sheet
  browser-harness skill               print the browser-harness skill text
  browser-harness skills [sync]       show/sync the skill into agent CLI skill dirs (claude/codex)
  browser-harness recordings          show recording status and recent sessions
  browser-harness recordings --latest   print the newest recording directory
  browser-harness recordings enable   save browser actions locally by default
  browser-harness recordings disable  stop saving browser actions by default
  browser-harness video init <recording>      prepare a recording for editing
  browser-harness video review <recording>    compile and review the video
  browser-harness video export <recording> --reviewed   export a verified MP4
  browser-harness rmux list|status|new|ensure|send|keys|capture|kill|kill-server|version
                                    drive rmux sessions/panes for multiplexed browser scripts
  browser-harness browsers           list Chrome instances, tabs, and app-tab binding
  browser-harness chrome-mode [status|headed|headless]
                                    show/flip the agent Chrome headless or headed
                                    (headed = visible window for manual login)
  browser-harness current            show the tab/app the daemon is operating on now
  browser-harness <app> [args...]    run an agent-workspace app (apps/<app>.py):
                                      x-monitor, x-search, web-fetch,
                                      google-search, bing-search, cookies —
                                      installed by `browser-harness skills sync`
  browser-harness --update [-y]    pull the latest version (agents: pass -y)
  browser-harness --reload         stop the daemon so next call picks up code changes
"""

USAGE = """Usage:
  @'
  print(page_info())
  '@ | browser-harness

  browser-harness <app> [args...]       run agent-workspace/apps/<app>.py (APP_ARGS holds args)
"""


def _print_skill():
    from importlib import resources

    # SKILL.md is UTF-8 (contains emoji); locale-codec read crashes on gbk Windows
    print(resources.files("browser_harness").joinpath("SKILL.md").read_text(encoding="utf-8"), end="")


def workspace_app(name: str):
    """Path to browser-workspace/apps/<name>.py — the plugin-script entry, or None."""
    from .helpers import BROWSER_WORKSPACE

    if not name or "/" in name or "\\" in name or name.startswith("-"):
        return None
    app = BROWSER_WORKSPACE / "apps" / f"{name}.py"
    return app if app.is_file() else None


def _exit_code(result) -> int:
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    return 1


def _traced(name, fn):
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        step_start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            recorder.observe(name, args, kwargs, round(time.monotonic() - step_start, 3))
            raise exc
        recorder.observe(name, args, kwargs, round(time.monotonic() - step_start, 3))
        return result

    wrapper.__bh_traced__ = True
    return wrapper


def _install_helper_trace():
    from . import helpers

    g = globals()
    for name in dir(helpers):
        if name.startswith("_"):
            continue
        fn = g.get(name)
        if callable(fn) and not isinstance(fn, type) and not getattr(fn, "__bh_traced__", False):
            g[name] = _traced(name, fn)


def main():
    _run(sys.argv[1:])


def _run(args):
    if args and args[0] in {"-h", "--help"}:
        print(HELP)
        return
    if args and args[0] == "--version":
        print(_version() or "unknown")
        return
    if args and args[0] == "--doctor":
        sys.exit(run_doctor())
    if args and args[0] == "doctor":
        rest = args[1:]
        if rest == ["--fix-snap"]:
            sys.exit(run_doctor_fix_snap())
        if rest and set(rest).issubset({"--json", "--require-existing-daemon"}) \
                and "--json" in rest and len(rest) == len(set(rest)):
            sys.exit(run_doctor_json(require_existing_daemon="--require-existing-daemon" in rest))
        if rest:
            print("usage: browser-harness doctor [--fix-snap|--json [--require-existing-daemon]]", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_doctor())
    if args and args[0] == "mac-approve":
        from . import macos

        sys.exit(macos.run_cli(args[1:]))
    if args and args[0] == "skill":
        if len(args) != 1:
            print("usage: browser-harness skill", file=sys.stderr)
            sys.exit(2)
        _print_skill()
        return
    if args and args[0] == "skills":
        from . import skills

        sys.exit(skills.run_cli(args[1:]))
    if args and args[0] == "recordings":
        rest = args[1:]
        if rest == ["--latest"]:
            latest = recorder.latest_recording()
            if latest is None:
                print("no recordings found", file=sys.stderr)
                sys.exit(1)
            print(latest)
            return
        if rest in (["enable"], ["disable"]):
            enabled = rest == ["enable"]
            recorder.set_auto_recording(enabled)
            print(f"auto-recording preference {'enabled' if enabled else 'disabled'}")
            return
        if rest:
            print("usage: browser-harness recordings [--latest|enable|disable]", file=sys.stderr)
            sys.exit(2)
        enabled, source = recorder.auto_recording_setting()
        print(f"auto-recording: {'on' if enabled else 'off'} ({source})")
        active = recorder.recording_dir()
        print(f"active: {active or 'none'}")
        recent = recorder.recordings()
        print(f"latest: {recent[0] if recent else 'none'}")
        return
    if args and args[0] == "video":
        from . import video

        sys.exit(video.run_cli(args[1:]))
    if args and args[0] == "rmux":
        from . import rmux

        sys.exit(rmux.run_cli(args[1:]))
    if args and args[0] == "browsers":
        from . import browsers

        sys.exit(browsers.run_cli(args[1:]))
    if args and args[0] == "chrome-mode":
        from .admin import run_chrome_mode

        sys.exit(run_chrome_mode(args[1:]))
    if args and args[0] == "current":
        from . import browsers

        sys.exit(browsers.run_current(args[1:]))
    if args and args[0] == "--update":
        yes = any(a in {"-y", "--yes"} for a in args[1:])
        sys.exit(run_update(yes=yes))
    if args and args[0] == "--reload":
        restart_daemon()
        print("daemon stopped — will restart fresh on next call")
        return
    if args and args[0] == "--debug-clicks":
        os.environ["BH_DEBUG_CLICKS"] = "1"
        args = args[1:]
    code = None
    if not args and not sys.stdin.isatty():
        code = sys.stdin.read()
        if not code.strip():
            sys.exit(USAGE)
    elif args:
        app = workspace_app(args[0])
        if app is not None:
            code = app.read_text(encoding="utf-8")
            globals()["APP_ARGS"] = args[1:]
            # The exec'd app's __file__ would be THIS module's path; expose the
            # app's own location for sibling lookups (APP_FILE).
            globals()["APP_FILE"] = str(app)
    if code is None:
        sys.exit(USAGE)
    print_update_banner()
    require_existing = os.environ.get("BH_REQUIRE_EXISTING_DAEMON") == "1"
    try:
        if require_existing:
            require_existing_daemon()
        else:
            ensure_daemon()
    except RuntimeError as e:
        # Setup/permission errors are instructions for calling agent
        print(f"browser-harness: {e}", file=sys.stderr)
        sys.exit(1)
    _install_helper_trace()
    exec(code, globals())


if __name__ == "__main__":
    main()
