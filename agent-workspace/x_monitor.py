"""X (Twitter) home timeline -> SQLite continuous monitor.

Self-healing: re-opens the tab, reloads broken pages, dedups, and keeps
running across transient CDP / permission errors.

Run from the repo root via the browser-harness CLI:
    uv run python -m browser_harness.run < agent-workspace/x_monitor.py

Env:
    X_DB        sqlite path (default agent-workspace/x_tweets.db)
    X_ROUNDS    max rounds then exit (default 0 = run forever)
    X_INTERVAL  seconds between rounds (default 8)
"""

import os
import re
import sqlite3
import time
import datetime


DB = os.environ.get("X_DB") or os.path.join(os.getcwd(), "agent-workspace", "x_tweets.db")
MAX_ROUNDS = int(os.environ.get("X_ROUNDS") or "0")
INTERVAL = float(os.environ.get("X_INTERVAL") or "8")


def _clean(s):
    return re.sub(r"[\ud800-\udfff]", "?", str(s or ""))


# article[data-testid=tweet]; \u65b0\u63a8\u6587 = new posts (zh), \u65b0\u5e16\u5b50 = new posts (zh alt)
EXTRACT = r"""Array.from(document.querySelectorAll('article[data-testid="tweet"]')).map(t => ({name:(t.querySelector('[data-testid="User-Name"]')?.innerText||'').trim(), text:(t.querySelector('[data-testid="tweetText"]')?.innerText||'').trim(), time:(t.querySelector('time')?.getAttribute('datetime')||''), link:(t.querySelector('a[href*="/status/"]')?.getAttribute('href')||'')}))"""

FIND = r"""(function(){var els=Array.from(document.querySelectorAll('a,[role="button"],div,span'));for(var i=0;i<els.length;i++){var el=els[i];var t=(el.innerText||'').trim();if(t&&t.length<40&&/\u65b0\u63a8\u6587|\u65b0\u5e16\u5b50|new posts|new Tweets/i.test(t)&&el.querySelectorAll('*').length<=3){return t;}}return null;})()"""

CLICK = FIND.replace("return t;", "el.click(); return t;")


def _conn():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _init(con):
    con.execute(
        """CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL DEFAULT '',
            handle TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL DEFAULT '',
            posted_at TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            dedup_key TEXT NOT NULL UNIQUE,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )"""
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_tweets_posted_at ON tweets(posted_at)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tweets_first_seen ON tweets(first_seen_at)")
    con.commit()


def _store(con, tweets):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    inserted = 0
    for t in tweets:
        name = _clean(t.get("name"))
        text = _clean(t.get("text"))
        if not text and not name:
            continue
        url = _clean(t.get("link"))
        posted = _clean(t.get("time"))
        handle = ""
        m = re.search(r"@([A-Za-z0-9_]+)", name)
        if m:
            handle = m.group(1)
        key = url if url else (name + "|" + text)
        cur = con.execute(
            "INSERT OR IGNORE INTO tweets(author,handle,text,posted_at,url,dedup_key,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?)",
            (name, handle, text, posted, url, key, now, now),
        )
        if cur.rowcount > 0:
            inserted += 1
        else:
            con.execute("UPDATE tweets SET last_seen_at=? WHERE dedup_key=?", (now, key))
    con.commit()
    return inserted


def _collect():
    return js(EXTRACT) or []


def _ensure_page():
    tabs = list_tabs(include_chrome=False)
    x = next((t for t in tabs if "x.com" in t.get("url", "")), None)
    if x:
        switch_tab(x, activate=False)
    else:
        new_tab("https://x.com/home")
    wait_for_load(timeout=20)
    time.sleep(2.5)


def _reload_if_broken():
    try:
        if str(js("location.href")).startswith("https://x.com"):
            count = js("document.querySelectorAll('article[data-testid=\"tweet\"]').length")
            if count == 0 and js("!!document.body && document.body.innerText.length > 0"):
                js("location.reload()")
                time.sleep(5)
    except Exception:
        pass


def main():
    con = _conn()
    _init(con)
    round_no = 0
    while True:
        round_no += 1
        if MAX_ROUNDS and round_no > MAX_ROUNDS:
            break
        try:
            _ensure_page()
            _reload_if_broken()
            prev = None
            for _ in range(6):
                _store(con, _collect())
                js("window.scrollTo(0, Math.max(document.documentElement.scrollHeight, document.body.scrollHeight))")
                time.sleep(1.0)
                h = js("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)")
                if h == prev:
                    break
                prev = h
            js("window.scrollTo(0,0)")
            time.sleep(1.0)
            pill = None
            for _ in range(2):
                r = js(FIND)
                if r:
                    pill = r
                    break
                time.sleep(3)
            if pill:
                js(CLICK)
                time.sleep(2.5)
                _store(con, _collect())
            total = con.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
            print("[x-monitor] round=%d db_total=%d pill=%s" % (round_no, total, _clean(pill) if pill else "none"), flush=True)
        except Exception as e:
            print("[x-monitor] round=%d error: %s" % (round_no, _clean(repr(e))), flush=True)
            time.sleep(min(30, 2 * min(round_no, 8)))
        time.sleep(INTERVAL)


main()
