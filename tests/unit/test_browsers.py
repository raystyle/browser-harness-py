import pytest

from browser_harness.browsers import _chrome_instances_linux


def _write_cmdline(root, pid, raw: bytes):
    d = root / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cmdline").write_bytes(raw)


@pytest.fixture
def fake_proc(monkeypatch, tmp_path):
    """Redirect the /proc scan of _chrome_instances_linux at a fake tree."""
    import pathlib

    real_iterdir = pathlib.Path.iterdir

    def iterdir(self, *args, **kwargs):
        # Path equality, not a string compare: on win32 str(Path("/proc"))
        # normalizes to "\\proc" and the redirect would never fire (M105).
        if self == pathlib.Path("/proc"):
            return real_iterdir(tmp_path, *args, **kwargs)
        return real_iterdir(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "iterdir", iterdir)
    return tmp_path


def test_parses_nul_separated_main_process(fake_proc):
    _write_cmdline(
        fake_proc, 100,
        b"/opt/google/chrome/chrome\0--user-data-dir=/home/u/p\0--remote-debugging-port=9224\0",
    )
    assert _chrome_instances_linux() == [
        {"pid": 100, "data_dir": "/home/u/p", "port": 9224},
    ]


def test_parses_space_joined_cmdline_after_chrome_rewrite(fake_proc):
    # Chrome rewrites its own Linux cmdline with canonicalized flags, and the
    # rewritten block is space-joined, not NUL-separated.
    _write_cmdline(
        fake_proc, 200,
        b"/opt/google/chrome/chrome --user-data-dir=/home/u/p --remote-debugging-port=9224 --headless=new",
    )
    assert _chrome_instances_linux() == [
        {"pid": 200, "data_dir": "/home/u/p", "port": 9224},
    ]


def test_skips_child_processes_and_other_binaries(fake_proc):
    _write_cmdline(
        fake_proc, 300,
        b"/opt/google/chrome/chrome\0--type=renderer\0--remote-debugging-port=9224\0",
    )
    _write_cmdline(fake_proc, 301, b"/usr/bin/firefox\0--remote-debugging-port=1\0")
    _write_cmdline(
        fake_proc, 302,
        b"/opt/google/chrome/chrome_crashpad_handler\0--monitor-self\0",
    )
    assert _chrome_instances_linux() == []


def test_main_process_without_flags_defaults(fake_proc):
    _write_cmdline(fake_proc, 400, b"/usr/bin/google-chrome-stable\0")
    assert _chrome_instances_linux() == [
        {"pid": 400, "data_dir": "default", "port": None},
    ]
