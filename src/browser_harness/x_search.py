"""Search tweets stored by x_worker.py / x_monitor.py.

No browser required; reads the SQLite database directly.

Usage:
    uv run python agent-workspace/x_search.py <keyword> [--limit N] [--author X]
    uv run python agent-workspace/x_search.py --recent [--limit N]
    uv run python agent-workspace/x_search.py --since 1h [--limit N]
    uv run python agent-workspace/x_search.py --since 2d --group-by day
    uv run python agent-workspace/x_search.py --stats
    uv run python agent-workspace/x_search.py <keyword> --csv [--csv-out path.csv]

Options:
    --limit N            max rows (default 20)
    --author X           filter by author text
    --recent             newest first (no keyword required)
    --since 30s|10m|1h|2d|1w   only tweets captured in the last duration
    --group-by day|hour  group output by capture time
    --stats              print store totals / ranges / top authors
    --csv                print CSV to stdout
    --csv-out path       write CSV to a file
"""

import csv
import datetime
import os
import re
import sqlite3
import sys


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_HERE = os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    """Repo agent-workspace (dev) else per-user workspace dir (global install)."""
    repo = os.path.normpath(os.path.join(_HERE, "..", "..", "agent-workspace"))
    if os.path.isdir(repo):
        return repo
    from browser_harness.paths import workspace_dir

    return str(workspace_dir())


DB = os.environ.get("X_DB") or os.path.join(_data_dir(), "x_tweets.db")


def _parse_duration(s):
    m = re.fullmatch(r"(\d+)\s*(s|sec|m|min|h|hr|d|w)?", s.strip().lower())
    if not m:
        raise ValueError(f"invalid duration {s!r}; use e.g. 30s, 10m, 1h, 2d, 1w")
    n = int(m.group(1))
    unit = (m.group(2) or "m").lower()
    mult = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hr": 3600, "d": 86400, "w": 604800}
    return n * mult[unit]


def _parse(argv):
    kw = None
    limit = 20
    author = None
    recent = False
    since = None
    group_by = None
    csv_mode = False
    csv_path = None
    stats = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--limit":
            limit = int(argv[i + 1]); i += 2; continue
        if a == "--author":
            author = argv[i + 1]; i += 2; continue
        if a == "--recent":
            recent = True; i += 1; continue
        if a == "--since":
            since = _parse_duration(argv[i + 1]); i += 2; continue
        if a == "--group-by":
            group_by = argv[i + 1]; i += 2; continue
        if a == "--csv":
            csv_mode = True; i += 1; continue
        if a == "--csv-out":
            csv_path = argv[i + 1]; csv_mode = True; i += 2; continue
        if a == "--stats":
            stats = True; i += 1; continue
        if not a.startswith("--"):
            kw = a
        i += 1
    return kw, limit, author, recent, since, group_by, csv_mode, csv_path, stats


def _has_table(con):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tweets'"
    ).fetchone() is not None


def _query(kw, limit, author, since):
    con = sqlite3.connect(DB)
    if not _has_table(con):
        con.close()
        return []
    q = "SELECT author, handle, text, posted_at, url, first_seen_at FROM tweets"
    where, params = [], []
    if kw:
        like = "%" + kw + "%"
        where.append("(text LIKE ? OR author LIKE ? OR handle LIKE ?)")
        params += [like, like, like]
    if author:
        where.append("author LIKE ?")
        params.append("%" + author + "%")
    if since is not None:
        cutoff = (datetime.datetime.now() - datetime.timedelta(seconds=since)).isoformat(timespec="seconds")
        where.append("first_seen_at >= ?")
        params.append(cutoff)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY first_seen_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = con.execute(q, params).fetchall()
    con.close()
    return rows


def _fmt_url(url):
    if not url:
        return ""
    return url if url.startswith("http") else "https://x.com" + url


def _print_flat(rows):
    for author, handle, text, posted, url, first_seen in rows:
        print("-" * 64)
        print("author:", author, "| @" + (handle or "?"), "| posted:", posted, "| seen:", first_seen)
        print("text:", text[:320])
        if url:
            print("url:", _fmt_url(url))


def _print_grouped(rows, by):
    buckets = {}
    for r in rows:
        ts = r[5]
        key = ts[:10] if by == "day" else (ts[:13] if len(ts) >= 13 else ts)
        buckets.setdefault(key, []).append(r)
    for key in sorted(buckets, reverse=True):
        group = buckets[key]
        print(f"\n== {key}  ({len(group)} tweets) ==")
        for author, handle, text, posted, url, first_seen in group:
            hhmmss = first_seen[11:19] if len(first_seen) >= 19 else first_seen
            print(f"  [{hhmmss}] {author} (@{handle or '?'}): {text[:110].replace(chr(10), ' ')}")


def _write_csv(rows, path):
    out = open(path, "w", newline="", encoding="utf-8") if path else sys.stdout
    w = csv.writer(out)
    w.writerow(["author", "handle", "text", "posted_at", "url", "first_seen_at"])
    for r in rows:
        w.writerow(list(r))
    if path:
        out.close()
        print(f"wrote {len(rows)} rows to {path}", file=sys.stderr)


def _stats():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    if not _has_table(con):
        con.close()
        print("total_tweets: 0")
        print("distinct_authors: 0")
        print("posted_range: - -> -")
        print("seen_range: - -> -")
        return
    total = con.execute("SELECT COUNT(*) n FROM tweets").fetchone()["n"]
    handles = con.execute("SELECT COUNT(DISTINCT handle) n FROM tweets WHERE handle != ''").fetchone()["n"]
    posted = con.execute(
        "SELECT MIN(posted_at) mn, MAX(posted_at) mx FROM tweets WHERE posted_at != ''"
    ).fetchone()
    seen = con.execute("SELECT MIN(first_seen_at) mn, MAX(first_seen_at) mx FROM tweets").fetchone()
    top = con.execute(
        "SELECT handle, COUNT(*) n FROM tweets WHERE handle != '' "
        "GROUP BY handle ORDER BY n DESC, MAX(first_seen_at) DESC LIMIT 10"
    ).fetchall()
    con.close()
    print("total_tweets:", total)
    print("distinct_authors:", handles)
    print("posted_range:", (posted["mn"] or "-"), "->", (posted["mx"] or "-"))
    print("seen_range:", (seen["mn"] or "-"), "->", (seen["mx"] or "-"))
    if top:
        print("top_authors:")
        for r in top:
            print(f"  @{r['handle']}: {r['n']}")


def main(argv=None):
    kw, limit, author, recent, since, group_by, csv_mode, csv_path, stats = _parse(argv if argv is not None else sys.argv[1:])
    if stats:
        _stats()
        return
    if not kw and not recent and since is None:
        print("usage: uv run python agent-workspace/x_search.py <keyword>|--recent|--since <dur>|--stats [options]")
        sys.exit(2)
    rows = _query(kw, limit, author, since)
    if csv_mode:
        _write_csv(rows, csv_path)
        return
    print("matched:", len(rows))
    if group_by in ("day", "hour"):
        _print_grouped(rows, group_by)
    else:
        _print_flat(rows)


if __name__ == "__main__":
    main()
