"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""

import gzip
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request


def _extract_links(limit, exclude):
    """Grab up to ``limit`` external http(s) links (title + url) from the page."""
    from browser_harness.helpers import js

    return js(
        """(function(limit, exclude){
            var out = [], seen = {};
            var links = document.links;
            for (var i = 0; i < links.length; i++) {
                var a = links[i];
                var href = a.href || "";
                var title = (a.innerText || "").trim();
                if (!/^https?:/.test(href)) continue;
                if (href.indexOf(exclude) !== -1) continue;
                if (!title || title.length < 4) continue;
                if (seen[href]) continue;
                seen[href] = 1;
                out.push({title: title, url: href});
                if (out.length >= limit) break;
            }
            return out;
        })(%d, %s)"""
        % (int(limit), json.dumps(exclude))
    )


def ensure_app_tab(key, url):
    """Attach to an existing tab whose URL contains ``key``, else open a new tab."""
    from browser_harness.helpers import list_tabs, switch_tab, new_tab

    for t in list_tabs(include_chrome=False):
        if key in (t.get("url") or ""):
            switch_tab(t, activate=False)
            return t.get("targetId") or t.get("target_id")
    return new_tab(url)


def setup_browser_apps():
    """Ensure X, Google, Bing each have their own tab. Returns ``{name: target_id}``."""
    return {
        "x": ensure_app_tab("x.com", "https://x.com/home"),
        "google": ensure_app_tab("google.com", "https://www.google.com"),
        "bing": ensure_app_tab("bing.com", "https://www.bing.com"),
    }


def google_search(query, limit=10):
    """Search Google in its own tab (reused) and return ``[{title, url}, ...]``."""
    from browser_harness.helpers import goto_url, wait_for_load, wait_for_element

    ensure_app_tab("google.com", "https://www.google.com")
    goto_url("https://www.google.com/search?q=" + urllib.parse.quote(query))
    wait_for_load(timeout=20)
    try:
        wait_for_element('a[href^="http"]', timeout=10)
    except Exception:
        pass
    return _extract_links(limit, "google.")


def bing_search(query, limit=10):
    """Search Bing in its own tab (reused) and return ``[{title, url}, ...]``."""
    from browser_harness.helpers import goto_url, wait_for_load, wait_for_element

    ensure_app_tab("bing.com", "https://www.bing.com")
    goto_url("https://www.bing.com/search?q=" + urllib.parse.quote(query))
    wait_for_load(timeout=20)
    try:
        wait_for_element('a[href^="http"]', timeout=10)
    except Exception:
        pass
    return _extract_links(limit, "bing.")


def detect_page_blocks():
    """Return anti-bot/block signals on the current page: ``[{type, reason}, ...]``.

    Detects Cloudflare challenge pages, captcha iframes (Turnstile / hCaptcha /
    reCAPTCHA), and common "verify you are human" / "access denied" text.
    """
    from browser_harness.helpers import js, page_info

    info = page_info()
    url = (info.get("url") or "").lower()
    title = (info.get("title") or "").lower()
    signals = []

    if "challenges.cloudflare.com" in url or "cf_chl" in url:
        signals.append({"type": "cloudflare", "reason": "challenge URL"})
    for phrase in (
        "just a moment",
        "attention required",
        "verify you are human",
        "access denied",
        "checking your browser",
        "enable javascript and cookies",
    ):
        if phrase in title:
            signals.append({"type": "block", "reason": "title: " + phrase})

    try:
        iframes = js("Array.from(document.querySelectorAll('iframe')).map(f => f.src || '').filter(Boolean)")
        for src in iframes:
            s = src.lower()
            if any(k in s for k in ("captcha", "hcaptcha", "recaptcha", "turnstile", "challenges.cloudflare")):
                signals.append({"type": "captcha", "reason": src[:90]})
                break
    except Exception:
        pass

    try:
        body = (js("(document.body && document.body.innerText || '').slice(0, 600)") or "").lower()
        for phrase in ("checking your browser", "verify you are human", "access denied"):
            if phrase in body:
                signals.append({"type": "block", "reason": phrase})
                break
    except Exception:
        pass

    seen = set()
    out = []
    for s in signals:
        key = (s["type"], s["reason"])
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def scan_tabs_for_blocks():
    """Check every tab for anti-bot blocks; return ``{url: [signals]}``."""
    from browser_harness.helpers import list_tabs, switch_tab

    out = {}
    for t in list_tabs(include_chrome=False):
        url = t.get("url") or ""
        try:
            switch_tab(t, activate=False)
            signals = detect_page_blocks()
        except Exception:
            signals = []
        if signals:
            out[url] = signals
    return out


def _html_to_text(html):
    """Best-effort plain text from an HTML fragment (prefers bs4 when present)."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        pass
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z#0-9]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pydefuddle_parse(html, url=""):
    """Parse HTML with the pydefuddle Python port, or return ``None``."""
    try:
        from pydefuddle import defuddle as _df
    except Exception:
        return None
    r = _df(html, url=url, markdown=True)
    return {
        "title": getattr(r, "title", "") or "",
        "url": url or "",
        "domain": getattr(r, "domain", "") or "",
        "author": getattr(r, "author", "") or "",
        "published": getattr(r, "published", "") or "",
        "description": getattr(r, "description", "") or "",
        "image": getattr(r, "image", "") or "",
        "favicon": getattr(r, "favicon", "") or "",
        "language": getattr(r, "language", "") or "",
        "site": getattr(r, "site_title", "") or "",
        "word_count": int(getattr(r, "word_count", 0) or 0),
        "content_html": getattr(r, "content", "") or "",
        "markdown": getattr(r, "markdown", "") or "",
        "engine": "pydefuddle",
    }


def _npx_defuddle_parse(html):
    """Parse HTML with ``npx defuddle parse - --json``, or return ``None``."""
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return None
    try:
        proc = subprocess.run(
            [npx, "-y", "defuddle", "parse", "-", "--json"],
            input=html.encode("utf-8"),
            capture_output=True,
            timeout=90,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout.decode("utf-8", "replace"))
    except Exception:
        return None
    return {
        "title": data.get("title") or "",
        "url": "",
        "domain": data.get("domain") or "",
        "author": data.get("author") or "",
        "published": data.get("published") or "",
        "description": data.get("description") or "",
        "image": data.get("image") or "",
        "favicon": data.get("favicon") or "",
        "language": data.get("language") or "",
        "site": data.get("site") or "",
        "word_count": int(data.get("wordCount") or 0),
        "content_html": data.get("content") or "",
        "markdown": data.get("contentMarkdown") or "",
        "engine": "defuddle-cli",
    }


def _fallback_parse(html, url=""):
    """Minimal extraction when neither pydefuddle nor npx defuddle is available."""
    title = ""
    content_html = html or ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.get_text(" ", strip=True) if soup.title else "").strip()
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        content_el = soup.find("main") or soup.find("article") or soup.body or soup
        content_html = str(content_el)
    except Exception:
        pass
    if not title:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
        if m:
            title = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", m.group(1))).strip()
    return {
        "title": title,
        "url": url or "",
        "domain": urllib.parse.urlparse(url).netloc if url else "",
        "author": "",
        "published": "",
        "description": "",
        "image": "",
        "favicon": "",
        "language": "",
        "site": "",
        "word_count": len(_html_to_text(content_html).split()),
        "content_html": content_html,
        "markdown": "",
        "engine": "bs4-fallback",
    }


def _defuddle_html(html, url=""):
    """Normalize page extraction across pydefuddle -> npx defuddle -> fallback."""
    out = _pydefuddle_parse(html, url)
    if out is None:
        out = _npx_defuddle_parse(html)
    if out is None:
        out = _fallback_parse(html, url)
    if not out.get("url") and url:
        out["url"] = url
    if not out.get("domain") and url:
        out["domain"] = urllib.parse.urlparse(url).netloc
    out["text"] = _html_to_text(out.get("content_html") or "")
    if not out.get("word_count") and out.get("text"):
        out["word_count"] = len(out["text"].split())
    return out


def extract_page_content(markdown=True):
    """Extract clean text/markdown + metadata from the current browser page."""
    from browser_harness.helpers import js, page_info

    info = page_info() or {}
    url = info.get("url") or ""
    html = ""
    try:
        html = js("document.documentElement.outerHTML") or ""
    except Exception:
        pass
    result = _defuddle_html(html, url)
    if not markdown:
        result["markdown"] = ""
    return result


def _http_get(url, timeout=30):
    """Plain HTTP GET returning decoded HTML (gzip-aware, redirect-following)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; browser-harness/0.1)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        ctype = (resp.headers.get("Content-Type") or "").lower()
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    charset = "utf-8"
    for part in ctype.split(";"):
        if "charset=" in part.lower():
            candidate = part.split("=", 1)[1].strip().strip('"').strip("'")
            if candidate:
                charset = candidate
            break
    return raw.decode(charset, "replace")


def extract_url_content(url, markdown=True, use_browser=True):
    """Fetch ``url`` and extract clean text/markdown + metadata.

    ``use_browser=True`` navigates the attached (logged-in) browser, so cookies
    and JS-rendered pages work. ``use_browser=False`` does a plain HTTP GET with
    no browser and no JavaScript.
    """
    if use_browser:
        from browser_harness.helpers import goto_url, wait_for_load

        goto_url(url)
        wait_for_load(timeout=30)
        return extract_page_content(markdown=markdown)
    result = _defuddle_html(_http_get(url), url)
    if not markdown:
        result["markdown"] = ""
    return result
