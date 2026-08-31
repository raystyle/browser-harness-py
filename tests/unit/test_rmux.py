from browser_harness import rmux


def test_rmux_binary_returns_tuple_or_none():
    det = rmux.rmux_binary()
    if det is not None:
        assert isinstance(det, tuple) and len(det) == 2
        assert isinstance(det[0], str) and det[0]
        assert det[1] is None or isinstance(det[1], str)


def test_parse_session_args():
    assert rmux._parse_session_args(["s1", "--command", "cmd", "--cwd", "d"]) == ("s1", "cmd", "d")
    assert rmux._parse_session_args(["s1"]) == ("s1", None, None)
    assert rmux._parse_session_args(["--command", "c", "s1"]) == ("s1", "c", None)
