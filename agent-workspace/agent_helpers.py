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


def google_search(query, limit=10):
    """Search Google and return ``[{title, url}, ...]`` (opens a background tab)."""
    from browser_harness.helpers import new_tab, wait_for_load, wait_for_element

    new_tab("https://www.google.com/search?q=" + urllib.parse.quote(query))
    wait_for_load(timeout=20)
    try:
        wait_for_element('a[href^="http"]', timeout=10)
    except Exception:
        pass
    return _extract_links(limit, "google.")


def bing_search(query, limit=10):
    """Search Bing and return ``[{title, url}, ...]`` (opens a background tab)."""
    from browser_harness.helpers import new_tab, wait_for_load, wait_for_element

    new_tab("https://www.bing.com/search?q=" + urllib.parse.quote(query))
    wait_for_load(timeout=20)
    try:
        wait_for_element('a[href^="http"]', timeout=10)
    except Exception:
        pass
    return _extract_links(limit, "bing.")
