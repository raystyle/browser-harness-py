import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-workspace"))

import agent_helpers  # noqa: E402


HTML = (
    "<html><head><title>Example</title></head><body>"
    "<nav>menu</nav><article><h1>Hello</h1><p>Some useful text here.</p></article>"
    "<script>window.bad()</script></body></html>"
)


def test_html_to_text_strips_markup_and_script():
    text = agent_helpers._html_to_text("<p>a</p><script>x()</script> b")
    assert "a" in text
    assert "b" in text
    assert "x()" not in text


def test_fallback_parse_extracts_title_and_domain():
    out = agent_helpers._fallback_parse(HTML, "https://example.com/a")
    assert out["title"] == "Example"
    assert out["domain"] == "example.com"
    assert out["word_count"] > 0
    assert "Hello" in agent_helpers._html_to_text(out["content_html"])


def test_defuddle_html_falls_back_when_engines_missing(monkeypatch):
    monkeypatch.setattr(agent_helpers, "_pydefuddle_parse", lambda html, url="": None)
    monkeypatch.setattr(agent_helpers, "_npx_defuddle_parse", lambda html: None)
    out = agent_helpers._defuddle_html(HTML, "https://example.com/a")
    assert out["engine"] == "bs4-fallback"
    assert out["title"] == "Example"
    assert out["text"]
