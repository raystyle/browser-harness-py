"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""

import json
import urllib.parse


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
