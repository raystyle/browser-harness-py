"""Task-scoped browser isolation: --once/--batch get their own stack."""

import os
import shutil
import socket

from browser_harness import paths, task_isolation as ti

_ENV_KEYS = ("BU_NAME", "BU_CDP_URL", "BU_CDP_WS", "BH_AGENT_CDP_PORT",
             "BH_AGENT_CHROME_PROFILE", "BH_ISOLATED_TASK")


def _clean_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def _seed_base_profile(home):
    base = home / "agent-chrome-profile"
    (base / "Default").mkdir(parents=True)
    (base / "Default" / "Preferences").write_text('{"profile": {"exit_type": "Normal"}}', encoding="utf-8")
    (base / "Local State").write_text("{}", encoding="utf-8")
    (base / "Default" / "Cache").mkdir()
    (base / "Default" / "Cache" / "big_blob").write_text("x" * 1000)
    (base / "DevToolsActivePort").write_text("9223\n/devtools/browser/abc")
    return base


def test_apply_isolates_once_tasks(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    monkeypatch.setattr(paths, "home_dir", lambda: tmp_path)
    _seed_base_profile(tmp_path)
    try:
        ti.apply_from_argv(["--once", "browsers"])
        name = os.environ["BU_NAME"]
        assert name.startswith("task-")
        assert os.environ["BH_ISOLATED_TASK"] == "1"
        assert 9230 <= int(os.environ["BH_AGENT_CDP_PORT"]) < 9261

        clone = tmp_path / "task-profiles" / name
        assert os.environ["BH_AGENT_CHROME_PROFILE"] == str(clone)
        # pinned to its own dedicated port — never user-Chrome discovery
        assert os.environ["BU_CDP_URL"] == f"http://127.0.0.1:{os.environ['BH_AGENT_CDP_PORT']}"
        # login payload carried, caches and stale port file dropped
        assert (clone / "Default" / "Preferences").exists()
        assert (clone / "Local State").exists()
        assert not (clone / "Default" / "Cache").exists()
        assert not (clone / "DevToolsActivePort").exists()
    finally:
        # apply() writes os.environ directly; monkeypatch only restores keys it
        # saw deleted. Pop explicitly or the leak poisons later suites.
        for k in _ENV_KEYS:
            os.environ.pop(k, None)


def test_apply_skips_persistent_shared_and_pinned(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    monkeypatch.setattr(paths, "home_dir", lambda: tmp_path)
    try:
        ti.apply_from_argv(["browsers"])                 # persistent default
        ti.apply_from_argv(["--persistent", "x"])
        ti.apply_from_argv(["--batch", "--shared", "x"])  # explicit opt-out
        assert "BU_NAME" not in os.environ

        monkeypatch.setenv("BU_NAME", "x-monitor")  # pinned stack: never detach
        ti.apply_from_argv(["--once", "x"])
        assert os.environ["BU_NAME"] == "x-monitor"
        assert "BH_ISOLATED_TASK" not in os.environ
    finally:
        for k in _ENV_KEYS:
            os.environ.pop(k, None)


def test_reserve_port_skips_busy_listeners_and_locked_ports():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 9230))
        s.listen(1)
        fd, _holder = ti.ipc.acquire_lock("task-port-9231")
        try:
            port, fd2 = ti._reserve_port()
            assert port not in (9230, 9231)  # listener and lock both respected
            os.close(fd2)
        finally:
            os.close(fd)


def test_tolerant_copy_skips_locked_files(tmp_path, monkeypatch):
    """A file Windows won't let us copy must degrade to a placeholder, not
    abort the whole clone."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "Default").mkdir(parents=True)
    (src / "Default" / "Cookies").write_text("locked")
    real_copy2 = shutil.copy2

    def picky_copy2(a, b, **kw):
        if str(a).endswith("Cookies"):
            raise PermissionError("file in use")
        return real_copy2(a, b, **kw)

    monkeypatch.setattr(shutil, "copy2", picky_copy2)
    ti._clone_profile(src, dst)
    assert (dst / "Default" / "Cookies").exists()           # placeholder keeps structure
    assert (dst / "Default" / "Cookies").read_text() == ""  # degraded, not carried

