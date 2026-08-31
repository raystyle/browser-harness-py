"""Search tweets stored by x_monitor.py.

No browser required; reads the SQLite database directly.

Usage:
    uv run python agent-workspace/x_search.py <keyword> [--limit N] [--author X] [--recent]
"""

import os
import sqlite3
import sys


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


DB = os.environ.get("X_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "x_tweets.db")


def _parse(argv):
    kw = None
    limit = 20
    author = None
    recent = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--limit":
            limit = int(argv[i + 1])
            i += 2
            continue
        if a == "--author":
            author = argv[i + 1]
            i += 2
            continue
        if a == "--recent":
            recent = True
            i += 1
            continue
        if not a.startswith("--"):
            kw = a
        i += 1
    return kw, limit, author, recent


def main():
    kw, limit, author, recent = _parse(sys.argv[1:])
    if not kw and not recent:
        print("usage: uv run python agent-workspace/x_search.py <keyword> [--limit N] [--author X] [--recent]")
        sys.exit(2)
    con = sqlite3.connect(DB)
    q = "SELECT author, handle, text, posted_at, url, first_seen_at FROM tweets"
    where, params = [], []
    if kw:
        like = "%" + kw + "%"
        where.append("(text LIKE ? OR author LIKE ? OR handle LIKE ?)")
        params += [like, like, like]
    if author:
        where.append("author LIKE ?")
        params.append("%" + author + "%")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY first_seen_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = con.execute(q, params).fetchall()
    con.close()

    print("matched:", len(rows))
    for author, handle, text, posted, url, first_seen in rows:
        print("-" * 64)
        print("author:", author, "| @" + (handle or "?"), "| posted:", posted, "| seen:", first_seen)
        print("text:", text[:320])
        if url:
            print("url:", url if url.startswith("http") else "https://x.com" + url)


main()
