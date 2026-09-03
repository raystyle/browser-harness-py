"""Export / import browser session cookies between agent Chromes.

Move a logged-in session (e.g. X) from one machine's agent Chrome to
another's without re-login: export on the source host, copy the file,
import on the target host. Works agent-Chrome -> agent-Chrome only (the
chrome://inspect permission flow of a default profile is a different,
interactive path — see S004/S007).

Usage:
    browser-harness cookies export [--endpoint URL] [--out FILE]
                                   [--domain x.com] ... [--all]
    browser-harness cookies import --file FILE [--endpoint URL] [--domain x.com] ...

Endpoints are HTTP DevTools URLs (resolved to the browser WebSocket via
/json/version). Defaults:
    export: BH_COOKIE_EXPORT_ENDPOINT, else http://127.0.0.1:9223 (the other
            host's agent Chrome — e.g. the Windows side from WSL)
    import: BU_CDP_URL (this host's pinned agent Chrome), else --endpoint required

The export file contains live session credentials: it is written 0600 and
must never be committed or shared.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

SCHEMA = "browser-harness-cookies/1"

# Fields CDP accepts when setting a cookie; everything else in a getCookies
# record (size, session, sourceSnapshotURL, ...) is output-only.
_SET_FIELDS = (
    "name", "value", "domain", "path", "expires", "httpOnly", "secure",
    "sameSite", "priority", "sameParty", "sourceScheme", "sourcePort",
    "partitionKey",
)
_SAME_SITES = ("Strict", "Lax", "None")


def normalize_endpoint(raw: str) -> str:
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        raise ValueError("empty endpoint")
    return raw if "://" in raw else f"http://{raw}"


def domain_matches(cookie_domain: str, wanted: str) -> bool:
    d = (cookie_domain or "").lstrip(".").lower()
    w = (wanted or "").lstrip(".").lower()
    if not w:
        return False
    return d == w or d.endswith("." + w)


def filter_cookies(cookies: list, domains: list) -> list:
    if not domains:
        return list(cookies)
    return [c for c in cookies if any(domain_matches(c.get("domain", ""), w) for w in domains)]


def sanitize_for_set(cookie: dict) -> dict:
    out = {k: cookie[k] for k in _SET_FIELDS if cookie.get(k) not in (None, "", [])}
    if out.get("sameSite") not in _SAME_SITES:
        out.pop("sameSite", None)
    return out


def _ws_url(endpoint: str, timeout: float = 10.0) -> str:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            return json.loads(urllib.request.urlopen(f"{endpoint}/json/version", timeout=3).read())["webSocketDebuggerUrl"]
        except Exception as e:  # noqa: BLE001 - retry until deadline, report last
            last = e
            time.sleep(0.5)
    raise RuntimeError(f"endpoint {endpoint} unreachable: {last} -- is that agent Chrome running?")


async def _fetch_cookies(endpoint: str) -> list:
    from cdp_use.client import CDPClient

    c = CDPClient(_ws_url(endpoint))
    await c.start()
    try:
        r = await c.send_raw("Storage.getCookies")
        return r.get("cookies", [])
    finally:
        await c.stop()


async def _push_cookies(endpoint: str, cookies: list) -> tuple[int, int]:
    """Set cookies on the endpoint browser. Returns (set_ok, total_wanted).

    Batch Storage.setCookies first; per-cookie Network.setCookie fallback so a
    single rejected record (bad domain/partition key) can't sink the rest."""
    from cdp_use.client import CDPClient

    wanted = {(c.get("name"), (c.get("domain") or "").lstrip(".").lower(), c.get("path"))
              for c in cookies}
    c = CDPClient(_ws_url(endpoint))
    await c.start()
    try:
        try:
            await c.send_raw("Storage.setCookies", {"cookies": cookies})
        except Exception:
            for cookie in cookies:
                try:
                    await c.send_raw("Network.setCookie", cookie)
                except Exception:
                    pass  # counted via the re-read below
        # Verify by re-reading: a rejected cookie just won't be there.
        live = await c.send_raw("Storage.getCookies")
        have = {(k.get("name"), (k.get("domain") or "").lstrip(".").lower(), k.get("path"))
                for k in live.get("cookies", [])}
        return len(wanted & have), len(wanted)
    finally:
        await c.stop()


def _default_out(endpoint: str) -> Path:
    from browser_harness import paths

    host = endpoint.split("://", 1)[-1].split(":")[0].replace(":", "_")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return paths.home_dir() / f"cookies-{host}-{stamp}.json"


def _write_private(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def main(argv=None) -> int:
    if argv is None:
        argv = globals().get("APP_ARGS", sys.argv[1:])
    parser = argparse.ArgumentParser(description="Export/import agent-Chrome session cookies between hosts")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_export = sub.add_parser("export", help="read cookies from one agent Chrome into a file")
    p_export.add_argument("--endpoint", default=os.environ.get("BH_COOKIE_EXPORT_ENDPOINT", "http://127.0.0.1:9223"))
    p_export.add_argument("--out", default=None, help="output file (default <BH_HOME>/cookies-<host>-<ts>.json)")
    p_export.add_argument("--domain", action="append", default=[], metavar="D",
                          help="only cookies for this domain (repeatable; default: none => require --all or --domain)")
    p_export.add_argument("--all", action="store_true", help="export every cookie, not just --domain matches")

    p_import = sub.add_parser("import", help="write cookies from a file into an agent Chrome")
    p_import.add_argument("--file", required=True)
    p_import.add_argument("--endpoint", default=os.environ.get("BU_CDP_URL") or None)
    p_import.add_argument("--domain", action="append", default=[], metavar="D",
                          help="only import cookies for this domain (repeatable; default: all in file)")

    args = parser.parse_args(argv)

    if args.cmd == "export":
        if not args.domain and not args.all:
            print("refusing to dump every site's cookies by default -- pass --domain (repeatable) or --all", file=sys.stderr)
            return 2
        endpoint = normalize_endpoint(args.endpoint)
        cookies = asyncio.run(_fetch_cookies(endpoint))
        picked = filter_cookies(cookies, args.domain)
        if not picked:
            print(f"no cookies matched {args.domain or '(all)'} on {endpoint}", file=sys.stderr)
            return 1
        out = Path(args.out).expanduser() if args.out else _default_out(endpoint)
        _write_private(out, {
            "schema": SCHEMA,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endpoint": endpoint,
            "domains": args.domain or ["(all)"],
            "cookies": picked,
        })
        print(f"exported {len(picked)} cookie(s) from {endpoint} -> {out}")
        print("warning: this file contains live session credentials; do not commit or share it", file=sys.stderr)
        return 0

    # import
    src = Path(args.file).expanduser()
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"cannot read {src}: {e}", file=sys.stderr)
        return 1
    if payload.get("schema") != SCHEMA:
        print(f"unknown cookie file schema: {payload.get('schema')!r} (want {SCHEMA!r})", file=sys.stderr)
        return 1
    cookies = filter_cookies(payload.get("cookies", []), args.domain)
    cookies = [sanitize_for_set(c) for c in cookies]
    if not cookies:
        print("nothing to import (empty file or no --domain matches)", file=sys.stderr)
        return 1
    if not args.endpoint:
        print("import needs --endpoint or BU_CDP_URL (the target agent Chrome)", file=sys.stderr)
        return 2
    endpoint = normalize_endpoint(args.endpoint)
    ok, total = asyncio.run(_push_cookies(endpoint, cookies))
    print(f"imported {ok}/{total} cookie(s) into {endpoint}")
    if ok < total:
        print("hint: rejected cookies are usually partitioned or domain-mismatched; navigate to the site once, then retry", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__" or "APP_ARGS" in globals():
    raise SystemExit(main())
