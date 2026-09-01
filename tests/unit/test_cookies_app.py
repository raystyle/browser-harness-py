import importlib.util
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[2] / "src" / "browser_harness" / "references" / "apps" / "cookies.py"


def _load():
    spec = importlib.util.spec_from_file_location("cookies_app", _APP)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("cookies_app", mod)
    spec.loader.exec_module(mod)
    return mod


cookies_app = _load()


def test_normalize_endpoint():
    assert cookies_app.normalize_endpoint("127.0.0.1:9223") == "http://127.0.0.1:9223"
    assert cookies_app.normalize_endpoint("http://127.0.0.1:9224/") == "http://127.0.0.1:9224"
    try:
        cookies_app.normalize_endpoint("  ")
    except ValueError:
        pass
    else:
        raise AssertionError("empty endpoint must raise")


def test_domain_matches_dots_and_subdomains():
    assert cookies_app.domain_matches(".x.com", "x.com")
    assert cookies_app.domain_matches("x.com", "x.com")
    assert cookies_app.domain_matches("api.x.com", "x.com")
    assert not cookies_app.domain_matches("notx.com", "x.com")
    assert not cookies_app.domain_matches("", "x.com")


def test_filter_cookies_without_domains_keeps_all():
    cs = [{"domain": ".x.com", "name": "a"}, {"domain": "other.com", "name": "b"}]
    assert len(cookies_app.filter_cookies(cs, [])) == 2
    picked = cookies_app.filter_cookies(cs, ["x.com"])
    assert [c["name"] for c in picked] == ["a"]


def test_sanitize_for_set_strips_output_only_and_bad_samesite():
    raw = {
        "name": "auth_token", "value": "v", "domain": ".x.com", "path": "/",
        "expires": 1234.0, "httpOnly": True, "secure": True, "sameSite": "no_restriction",
        "size": 18, "session": False, "sourceSnapshotURL": "https://x.com/",
        "priority": "HIGH",
    }
    out = cookies_app.sanitize_for_set(raw)
    assert "size" not in out and "session" not in out and "sourceSnapshotURL" not in out
    assert "sameSite" not in out  # Chrome rejects anything but Strict/Lax/None
    assert out["priority"] == "HIGH" and out["httpOnly"] is True
