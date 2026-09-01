import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from browser_harness import run


def test_stdin_executes_code():
    stdout = StringIO()
    fake_stdin = StringIO("print('hello from stdin')")

    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"), \
         patch("sys.stdin", fake_stdin), \
         patch("sys.stdout", stdout):
        run.main()

    assert stdout.getvalue().strip() == "hello from stdin"


def test_require_existing_daemon_never_auto_starts(monkeypatch):
    monkeypatch.setenv("BH_REQUIRE_EXISTING_DAEMON", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.require_existing_daemon") as mock_require, \
         patch("browser_harness.run.ensure_daemon") as mock_ensure, \
         patch("browser_harness.run.print_update_banner"):
        run.main()

    mock_require.assert_called_once_with()
    mock_ensure.assert_not_called()


def test_c_flag_is_rejected():
    with patch.object(sys, "argv", ["browser-harness", "-c", "print('old path')"]), \
         patch("sys.stdin", StringIO("print('ignored')")):
        try:
            run.main()
        except SystemExit as e:
            assert "@'" in str(e)
        else:
            raise AssertionError("-c should be rejected")


def test_no_args_interactive_stdin_prints_usage():
    fake_stdin = StringIO("")
    fake_stdin.isatty = lambda: True

    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", fake_stdin):
        try:
            run.main()
        except SystemExit as e:
            assert "@'" in str(e)
        else:
            raise AssertionError("interactive no-args invocation should exit with usage")


def test_no_args_empty_stdin_prints_usage():
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("")):
        try:
            run.main()
        except SystemExit as e:
            assert "@'" in str(e)
        else:
            raise AssertionError("empty stdin should exit with usage")


def test_cli_doctor_fix_snap_invokes_guide():
    with patch.object(sys, "argv", ["browser-harness", "doctor", "--fix-snap"]), \
         patch("browser_harness.run.run_doctor_fix_snap", return_value=0) as m:
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 0
    m.assert_called_once()


def test_cli_doctor_rejects_unknown_flags():
    err = StringIO()
    with patch.object(sys, "argv", ["browser-harness", "doctor", "--bogus"]), patch("sys.stderr", err):
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 2
    assert "usage" in err.getvalue().lower()
