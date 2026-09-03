"""Google search in the logged-in browser (workspace app).

Run:   browser-harness google-search <query> [--page N]
"""

import base64
import re
import sys


def _decode_bing_target(url):
    m = re.search(r"[?&]u=([^&]+)", url)
    if not m:
        return None
    try:
        s = m.group(1)
        s += "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s).decode("utf-8", "replace")
    except Exception:
        return None


def run(engine: str, rest: list[str]) -> int:
    page = 1
    qparts: list[str] = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--page":
            try:
                page = max(1, int(rest[i + 1]))
                i += 2
            except (IndexError, ValueError):
                print("usage: --page <int>", file=sys.stderr)
                return 2
        else:
            qparts.append(a)
        i += 1
    query = " ".join(qparts).strip()
    if not query:
        print(f"usage: browser-harness {engine}-search <query> [--page <int>]", file=sys.stderr)
        return 2
    from browser_harness.admin import ensure_daemon
    from browser_harness.browser_helpers import bing_search, extract_url_content, google_search

    ensure_daemon()
    rows = google_search(query, limit=5, page=page) if engine == "google" else bing_search(query, limit=5, page=page)
    for i, r in enumerate(rows, 1):
        url = r.get("url", "")
        title = r.get("title", "")
        print(f"[{i}] {title}")
        print(f"    {url}")
        desc = (r.get("description") or "").strip().replace("\n", " ")
        target = _decode_bing_target(url) if "bing.com/ck" in url else url
        if target and target.startswith("http") and i <= 3:
            try:
                content = extract_url_content(target, markdown=False, use_browser=False)
                text = (content.get("text") or "").strip().replace("\n", " ")
                if text:
                    print(f"    {text[:600]}")
                elif desc:
                    print(f"    {desc[:600]}")
            except Exception:
                if desc:
                    print(f"    {desc[:600]}")
    return 0


raise SystemExit(run("google", list(globals().get("APP_ARGS", []))))
