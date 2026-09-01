"""Extract clean text/markdown from a URL (or the current browser page).

Uses defuddle for main-content extraction:
  - pydefuddle if importable (Python port)
  - else ``npx defuddle parse`` (Node CLI)
  - else a lightweight bs4/stdlib fallback

Usage:
  uv run python agent-workspace/page_text.py <url> [--markdown|--text|--json] [--browser]
  uv run python agent-workspace/page_text.py --current [--markdown|--text|--json]

Default is a plain HTTP fetch (no browser). Pass ``--browser`` to reuse the
attached, logged-in browser (cookies + JS), or ``--current`` to parse the page
the browser is already showing.
"""

import argparse
import json
import sys

from browser_harness.agent_helpers import extract_page_content, extract_url_content


def main(argv=None):
    if argv is None:
        # Invoked as a workspace app: APP_ARGS holds the CLI args after the
        # app name; direct `python web-fetch.py` falls back to sys.argv.
        argv = globals().get("APP_ARGS", sys.argv[1:])
    parser = argparse.ArgumentParser(description="Extract clean text/markdown from a web page")
    parser.add_argument("url", nargs="?", help="URL to fetch (omit with --current)")
    parser.add_argument("--current", action="store_true", help="parse the current browser page")
    parser.add_argument("--browser", action="store_true", help="fetch via the attached browser")
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--markdown", action="store_true", help="print markdown (default)")
    fmt.add_argument("--text", action="store_true", help="print plain text")
    fmt.add_argument("--json", action="store_true", help="print full JSON metadata")
    args = parser.parse_args(argv)

    if args.current:
        result = extract_page_content(markdown=True)
    elif args.url:
        result = extract_url_content(args.url, markdown=True, use_browser=args.browser)
    else:
        parser.error("provide a URL or pass --current")

    if args.text:
        print(result.get("text") or "")
    elif args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("markdown") or result.get("text") or "")
    return 0


# Entry: unguarded. Under app routing the code is exec'd with __name__ set to
# the runner module, so an `if __name__ == "__main__"` guard would silently
# skip execution.
raise SystemExit(main())
