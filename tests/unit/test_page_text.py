from browser_harness import browser_helpers


HTML = (
    "<html><head><title>Example</title></head><body>"
    "<nav>menu</nav><article><h1>Hello</h1><p>Some useful text here.</p></article>"
    "<script>window.bad()</script></body></html>"
)


def test_html_to_text_strips_markup_and_script():
    text = browser_helpers._html_to_text("<p>a</p><script>x()</script> b")
    assert "a" in text
    assert "b" in text
    assert "x()" not in text


def test_fallback_parse_extracts_title_and_domain():
    out = browser_helpers._fallback_parse(HTML, "https://example.com/a")
    assert out["title"] == "Example"
    assert out["domain"] == "example.com"
    assert out["word_count"] > 0
    assert "Hello" in browser_helpers._html_to_text(out["content_html"])


def test_defuddle_html_falls_back_when_engines_missing(monkeypatch):
    monkeypatch.setattr(browser_helpers, "_pydefuddle_parse", lambda html, url="": None)
    out = browser_helpers._defuddle_html(HTML, "https://example.com/a")
    assert out["engine"] == "bs4-fallback"
    assert out["title"] == "Example"
    assert out["text"]
