"""X capture worker (standalone). Run inside a rmux pane by x_supervisor.py.

Each round: attach to the X tab, scroll to read tweets, click the
"new posts" pill, and upsert everything into SQLite. A heartbeat file is
refreshed every successful round so the supervisor can detect a stall.

Env: X_DB, X_HEARTBEAT, X_INTERVAL.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
import datetime
import platform

from browser_harness.admin import ensure_daemon
from browser_harness import helpers


def _clean(s):
    return re.sub(r"[\ud800-\udfff]", "?", str(s or ""))


_HERE = os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    """Repo agent-workspace (dev) else per-user workspace dir (global install)."""
    repo = os.path.normpath(os.path.join(_HERE, "..", "..", "agent-workspace"))
    if os.path.isdir(repo):
        return repo
    from browser_harness.paths import workspace_dir

    return str(workspace_dir())


DB = os.environ.get("X_DB") or os.path.join(_data_dir(), "x_tweets.db")
HEARTBEAT = os.environ.get("X_HEARTBEAT") or os.path.join(_data_dir(), "x_worker.heartbeat")
INTERVAL = float(os.environ.get("X_INTERVAL") or "45")
DOCK_W = int(os.environ.get("X_DOCK_W") or "520")
DOCK_H = int(os.environ.get("X_DOCK_H") or "200")
FOREGROUND = (os.environ.get("X_FOREGROUND") or "1").strip().lower() in ("1", "true", "yes", "on")
IDLE_THRESHOLD = float(os.environ.get("X_IDLE_THRESHOLD") or "10")


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
    con.commit()


def _store(con, tweets):
    now = datetime.datetime.now().isoformat(timespec="seconds")
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
        con.execute(
            "INSERT OR IGNORE INTO tweets(author,handle,text,posted_at,url,dedup_key,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?)",
            (name, handle, text, posted, url, key, now, now),
        )
        con.execute("UPDATE tweets SET last_seen_at=? WHERE dedup_key=?", (now, key))
    con.commit()


def _tick():
    with open(HEARTBEAT, "w", encoding="utf-8") as f:
        f.write(str(time.time()))


def _tid(target):
    if isinstance(target, dict):
        return target.get("targetId") or target.get("target_id")
    return target


def _idle_seconds():
    """Seconds since the user's last keyboard/mouse input (0 = idle/unknown)."""
    if platform.system() != "Windows":
        return 0.0
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    try:
        lii = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        gtc = ctypes.windll.kernel32.GetTickCount
        gtc.restype = ctypes.c_uint32
        diff = (gtc() - lii.dwTime) & 0xFFFFFFFF
        return diff / 1000.0
    except Exception:
        return 0.0


def _foreground(target):
    """Bring the X tab to a tiny taskbar-docked window so throttled JS resumes."""
    tid = _tid(target)
    if not tid:
        return
    try:
        r = helpers.cdp("Browser.getWindowForTarget", targetId=tid)
        wid = r.get("windowId")
        if wid is not None:
            # Chrome applies windowState and bounds as separate steps.
            helpers.cdp("Browser.setWindowBounds", windowId=wid, bounds={"windowState": "normal"})
            docked = _dock_bounds()
            if docked:
                x, y, w, h = docked
                helpers.cdp("Browser.setWindowBounds", windowId=wid, bounds={
                    "left": x, "top": y, "width": w, "height": h,
                })
        helpers.cdp("Target.activateTarget", targetId=tid)
    except Exception:
        pass


def _dock_bounds():
    """Tiny window bounds docked next to the taskbar, off the desktop center."""
    try:
        import json

        raw = helpers.js(
            "JSON.stringify({w: screen.availWidth, h: screen.availHeight, "
            "l: screen.availLeft, t: screen.availTop})"
        )
        s = json.loads(raw or "{}")
        aw = int(s.get("w") or 0)
        ah = int(s.get("h") or 0)
        al = int(s.get("l") or 0)
        at = int(s.get("t") or 0)
        if not aw or not ah:
            return None
        w = min(DOCK_W, aw)
        h = min(DOCK_H, ah)
        x = al + aw - w
        y = at + ah - h
        if at > 0:
            y = at  # taskbar on top
        elif al > 0:
            x = al  # taskbar on left
        return max(0, x), max(0, y), w, h
    except Exception:
        return None


def _restore_window(target, state):
    """Restore the window to ``state`` (e.g. 'minimized') after a round."""
    if state != "minimized":
        return
    tid = _tid(target)
    if not tid:
        return
    try:
        r = helpers.cdp("Browser.getWindowForTarget", targetId=tid)
        wid = r.get("windowId")
        if wid is not None:
            helpers.cdp("Browser.setWindowBounds", windowId=wid, bounds={"windowState": state})
    except Exception:
        pass


def _round(con):
    ensure_daemon()
    tabs = helpers.list_tabs(include_chrome=False)
    x = next((t for t in tabs if "x.com" in t.get("url", "")), None)
    if x:
        helpers.switch_tab(x, activate=False)
    else:
        x = helpers.new_tab("https://x.com/home")
    helpers.wait_for_load(timeout=20)
    hidden = helpers.js("document.visibilityState") == "hidden"
    # 定时切一次前台刷新（不因键鼠活跃而跳过，否则 X 隐藏时一直抓不到新帖）。
    # 窗口会缩成小窗贴任务栏、刷完即最小化，把抢焦点影响压到最低。
    do_foreground = FOREGROUND and hidden
    if do_foreground:
        _foreground(x)
        time.sleep(1.5)
    prev = None
    for _ in range(6):
        _store(con, helpers.js(EXTRACT) or [])
        helpers.js("window.scrollTo(0, Math.max(document.documentElement.scrollHeight, document.body.scrollHeight))")
        time.sleep(1.0)
        h = helpers.js("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)")
        if h == prev:
            break
        prev = h
    helpers.js("window.scrollTo(0,0)")
    time.sleep(1.0)
    pill = None
    for _ in range(2):
        r = helpers.js(FIND)
        if r:
            pill = r
            break
        time.sleep(3.0)
    if pill:
        helpers.js(CLICK)
        time.sleep(2.5)
        _store(con, helpers.js(EXTRACT) or [])
    if do_foreground:
        _restore_window(x, "minimized")
    _tick()
    return con.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]


def main():
    con = _conn()
    _init(con)
    _tick()  # startup heartbeat so the supervisor sees us immediately
    print("[worker] started", flush=True)
    while True:
        try:
            total = _round(con)
            print(f"[worker] ok total={total}", flush=True)
        except Exception as e:
            print(f"[worker] error {_clean(repr(e))}", flush=True)
            time.sleep(5.0)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
