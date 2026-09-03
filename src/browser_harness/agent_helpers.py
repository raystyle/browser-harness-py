"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""

import gzip
import json
import re
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
    """Attach to the app's own tab (exact domain match), else open one.

    Idempotent + mutex: one app owns one tab. Repeated calls reuse the existing
    tab instead of opening duplicates, so apps never race into extra tabs.
    """
    from browser_harness.helpers import list_tabs, switch_tab, new_tab

    for t in list_tabs(include_chrome=False):
        host = ""
        try:
            host = urllib.parse.urlparse(t.get("url") or "").hostname or ""
        except Exception:
            host = ""
        if host == key or host.endswith("." + key):
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


def google_search(query, limit=10, page=1):
    """Search Google in its own tab (reused) and return ``[{title, url}, ...]``."""
    from browser_harness.helpers import goto_url, wait_for_load, wait_for_element, switch_tab

    tid = ensure_app_tab("google.com", "https://www.google.com")
    switch_tab(tid, activate=False)  # re-attach in case the X worker moved it
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    if page > 1:
        url += f"&start={(page - 1) * 10}"
    goto_url(url)
    wait_for_load(timeout=20)
    try:
        wait_for_element('a[href^="http"]', timeout=10)
    except Exception:
        pass
    switch_tab(tid, activate=False)  # re-attach before extracting
    return _extract_links(limit, "google.")


def bing_search(query, limit=10, page=1):
    """Search Bing in its own tab (reused) and return ``[{title, url, description}, ...]``."""
    from browser_harness.helpers import goto_url, wait_for_load, wait_for_element, switch_tab, js

    tid = ensure_app_tab("bing.com", "https://www.bing.com")
    switch_tab(tid, activate=False)  # re-attach in case the X worker moved it
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(query)
    if page > 1:
        url += f"&first={(page - 1) * 10 + 1}"
    goto_url(url)
    wait_for_load(timeout=20)
    try:
        wait_for_element("li.b_algo h2 a", timeout=10)
    except Exception:
        pass
    switch_tab(tid, activate=False)  # re-attach before extracting
    # Bing wraps result links in a JS-only redirect (bing.com/ck/a), so extract
    # the native b_algo cards (title + link + snippet) instead of generic links.
    return js(
        """(function(limit){
            var out=[], seen={};
            var items=document.querySelectorAll('li.b_algo');
            for(var i=0;i<items.length;i++){
                var li=items[i];
                var a=li.querySelector('h2 a');
                var p=li.querySelector('p');
                var href=a?(a.href||''):'';
                var title=a?((a.innerText||a.textContent||'')||'').trim():'';
                var desc=p?((p.innerText||p.textContent||'')||'').trim():'';
                if(!href||!title)continue;
                if(seen[href])continue;
                seen[href]=1;
                out.push({title:title,url:href,description:desc});
                if(out.length>=limit)break;
            }
            return out;
        })(%d)""" % int(limit)
    )


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


_SITE_SELECTORS = {
    "github.com": "article.markdown-body",
    "stackoverflow.com": "#answers, .s-prose, .question .s-prose",
    "wikipedia.org": "#mw-content-text",
    "medium.com": "article",
    "news.ycombinator.com": ".commtext",
    "reddit.com": ".usertext-body, [data-testid='comment']",
    "docs.python.org": "div.body",
}


def _site_selector(url=""):
    """Return a site-specific content selector for ``url``, or ``None``."""
    try:
        host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    except Exception:
        host = ""
    for domain, selector in _SITE_SELECTORS.items():
        if host == domain or host.endswith("." + domain):
            return selector
    return None


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
    kwargs = {"markdown": True}
    selector = _site_selector(url)
    if selector:
        kwargs["content_selector"] = selector
    r = _df(html, url=url, **kwargs)
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


def _fallback_parse(html, url=""):
    """Minimal extraction when pydefuddle is not available."""
    title = ""
    content_html = html or ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.get_text(" ", strip=True) if soup.title else "").strip()
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        selector = _site_selector(url)
        content_el = None
        if selector:
            content_el = soup.select_one(selector.split(",")[0].strip())
        content_el = content_el or soup.find("main") or soup.find("article") or soup.body or soup
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
    """Normalize page extraction across pydefuddle -> fallback."""
    out = _pydefuddle_parse(html, url)
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


def _looks_blocked(html):
    """True when the fetched HTML looks like a bot wall (Cloudflare / captcha)."""
    if not html:
        return True
    low = html.lower()
    return any(
        phrase in low
        for phrase in (
            "just a moment",
            "challenges.cloudflare.com",
            "cf-chl",
            "verify you are human",
            "access denied",
            "enable javascript and cookies",
            "captcha",
        )
    )


def _fetch_in_browser(url, markdown=True):
    """Open ``url`` in a fresh tab, extract, then close it (no tab pollution)."""
    from browser_harness.helpers import close_tab, new_tab, switch_tab, wait_for_load

    tid = new_tab(url)
    wait_for_load(timeout=30)
    try:
        switch_tab(tid, activate=False)  # re-attach in case the X worker moved it
        return extract_page_content(markdown=markdown)
    finally:
        try:
            close_tab(tid)
        except Exception:
            pass


def web_fetch(url, markdown=True, use_browser=False):
    """``browser-harness web-fetch <url>`` as a pre-imported callable.

    App-name alias closing the stdin/command mode gap (Issue #2): search apps
    exposed their cores as google_search/bing_search, but web-fetch's had no
    matching name. Same defaults as the CLI app — plain HTTP first, upgrading
    to the attached browser only when the response looks bot-walled or thin.
    For the current page use extract_page_content().
    """
    return extract_url_content(url, markdown=markdown, use_browser=use_browser)


def extract_url_content(url, markdown=True, use_browser=True):
    """Fetch ``url`` and extract clean text/markdown + metadata.

    ``use_browser=True`` navigates the attached (logged-in) browser, so cookies
    and JS-rendered pages work. ``use_browser=False`` does a plain HTTP GET with
    no browser and no JavaScript, then auto-upgrades to the browser when the
    response looks like a bot wall or the extracted text is suspiciously short.
    """
    if use_browser:
        return _fetch_in_browser(url, markdown)
    try:
        html = _http_get(url)
    except Exception:
        html = ""
    result = _defuddle_html(html, url)
    if (not html or _looks_blocked(html) or (result.get("word_count") or 0) < 20):
        try:
            result = _fetch_in_browser(url, True)
            result["engine"] = result.get("engine", "") + "+browser-retry"
        except Exception:
            pass
    if not markdown:
        result["markdown"] = ""
    return result
