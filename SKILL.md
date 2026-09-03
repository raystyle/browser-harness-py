---
name: browser-harness
description: "Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work."
---

# browser-harness

Direct browser control via CDP. For task-specific edits, use `browser-workspace/browser_helpers.py`. For setup, install, or connection problems, read https://github.com/raystyle/browser-harness/blob/main/install.md.

## When Not to Use

A basic fetch of public information needs no browser. If a plain HTTP request can read it — a public page, an API, docs — use `curl` or your fetch tool, and leave the browser alone. Use browser-harness when the task needs interaction (click, type, navigate), the user's logged-in session, JS rendering, or a bot-protected page. If a direct fetch fails or returns a shell page, then escalate to the browser.

Domain skills are off by default. Set `BH_DOMAIN_SKILLS=1` to enable them; see the bottom section.

**If `BH_DOMAIN_SKILLS=1` and the task is site-specific, read every file in the matching `$BH_BROWSER_WORKSPACE/domain-skills/<site>/` directory before inventing an approach.**

## Usage

```powershell
@'
print(page_info())
'@ | browser-harness
```

- Invoke as `browser-harness`. On Windows PowerShell use a here-string piped to
  the command (`@'... '@ | browser-harness`); on macOS/Linux a heredoc works.
- Helpers are pre-imported. `run.py` calls `ensure_daemon()` before `exec`.
- First navigation for a task is `new_tab(url)`, not `goto_url(url)`. The daemon
  preserves the attached tab across separate CLI invocations, so do not call
  `new_tab()` again in every script.
- Keep one working tab per task/site. Before opening another, inspect
  `current_tab()` and `list_tabs()` and use `switch_tab()` to reuse a matching
  tab. Do not leave duplicate tabs on the same URL or close tabs you did not
  create.
- `new_tab()` and `switch_tab()` attach and move the horse marker without
  changing Chrome's visible tab. Screenshots and normal CDP input work in the
  background; call `activate_tab(target)` only when the user explicitly asks
  or a page demonstrably pauses rendering while hidden.
- A timed-out `scroll(x, y, dx, dy)` on an attached background tab is evidence
  that the page needs to be visible. Call `activate_tab(current_tab())`, retry
  the same scroll once, then re-read the scroll position. This visibly switches
  tabs, so do not use it when the user has forbidden foreground changes. Do not
  invent a `Runtime.evaluate` scroll replacement or a cross-frame JS walker.
- The x-monitor worker drives the browser through its own daemon
  (`BU_NAME=x-monitor`), so capture rounds never race ad-hoc CLI scripts for
  the default daemon's tab attachment. Both daemons may attach to the same
  agent Chrome concurrently.
- The default daemon is pinned to the isolated agent Chrome via
  `BU_CDP_URL=http://127.0.0.1:9223` in `<BH_HOME>/.env` — it never attaches
  to the user's own Chrome, even one with the chrome://inspect remote-debugging
  toggle enabled (that toggle's DevToolsActivePort would otherwise be
  discovered first). If the agent Chrome is down, `ensure_daemon` launches it.
  The port comes from `BH_AGENT_CDP_PORT` (default 9223); a WSL2 host on
  mirrored networking shares loopback with Windows, so its stack pins its own
  port (e.g. 9224) to not collide with the Windows stack's agent Chrome.
  `BH_CHROME_HEADLESS=1` launches the agent Chrome headless (default on
  display-less Linux).
- To drive a different browser for a task, set `BU_CDP_URL`/`BU_CDP_WS` (per
  call or in `<BH_HOME>/.env`); see the X section below.
- Pipe code and command dispatch share one capability surface (dual-mode
  compatibility): any subcommand is callable from pipe scripts via
  `run_app(name, *args, json_output=False)` — it runs exactly
  `browser-harness <name> <args>` and returns its stdout. `web_fetch(url)` is
  the direct pre-imported alias for `browser-harness web-fetch <url>` (plain
  HTTP first, browser upgrade on bot walls; current page:
  `extract_page_content()`). Long-running supervisors (x-monitor) stay in rmux.

## Browser Workspace

`browser-workspace/` is an **agent-owned runtime directory**, not package source.
Only add task-specific helpers and data here; do not edit the installed package.

- Always under the app data dir (`BH_HOME`, default `~/.config/browser-harness`;
  Windows: `C:\Users\<user>\.config\browser-harness`) — in every install mode,
  including a git checkout. The repo's `browser-workspace/` holds tracked
  reference content only.
- Override the location with `BH_BROWSER_WORKSPACE` (legacy `BH_AGENT_WORKSPACE`
  still honored; a pre-v0.6.8 default `agent-workspace/` is auto-renamed on
  first run).
- **Add an app = helper functions + plugin script**: reusable functions go in
  `browser_helpers.py`, standalone scripts in `apps/<name>.py` — invoked as
  `browser-harness <name> [args...]` (positional args land in `APP_ARGS`).
  Long-running plugins get a rmux session (`browser-harness rmux ensure ...`).
- `browser_helpers.py` loading is a **merge**: packaged helpers fill the defaults,
  the workspace copy overrides per function — create it only to customize; an
  absent file always uses the newest packaged helpers.
- To add a helper, create `browser_helpers.py` in the active workspace. Its public
  functions are imported automatically by the next `browser-harness` script:

```python
def summarize_current_page():
    info = page_info() or {}
    body = js("(document.body && document.body.innerText || '').slice(0, 3000)")
    return {"url": info.get("url"), "title": info.get("title"), "body": body}
```

Then invoke without importing:

```powershell
@'
print(summarize_current_page())
'@ | browser-harness
```

- Keep app data there too: `x_tweets.db`, heartbeats, supervisor logs.
- Domain skills live in `browser-workspace/domain-skills/<host>/`. When
  `BH_DOMAIN_SKILLS=1`, read every matching file before inventing an approach.

## Apps routing

The package is a thin core (daemon, helpers, rmux, diagnostics); applications are **workspace plugins** in `browser-workspace/apps/`, provisioned by `browser-harness --update` (or `skills sync`). Route by intent:

| User intent | App / command |
| --- | --- |
| X 持续抓推 / 监控新推（自愈） | `browser-harness x-monitor`（插件） |
| X 已存推的查询 / 搜索 / 统计 | `browser-harness x-search ...`（插件） |
| Google 搜索 | `browser-harness google-search <query>`（插件） |
| Bing 搜索 | `browser-harness bing-search <query>`（插件） |
| 网页正文提取 | `browser-harness web-fetch <url>`（插件） |
| 登录态跨设备迁移 | `browser-harness cookies export\|import`（插件，S007） |
| 无头/有头切换（登录录入走有头） | `browser-harness chrome-mode status\|headed\|headless`（核心，S008） |
| rmux 会话管理 | `browser-harness rmux list\|status\|ensure\|capture\|kill\|kill-server`（核心） |

Plugin development & testing spec: `docs/references/R003-插件开发与测试规范.md`.

## Local Chrome

If the daemon cannot connect, run diagnostics:

```powershell
browser-harness --doctor
```

If Chrome is not running at all, the harness launches it automatically and retries.

If Chrome is running but remote debugging is not enabled, the harness opens:

```text
chrome://inspect/#remote-debugging
```

On macOS, when Chrome asks for remote-debugging permission, run:

```text
browser-harness mac-approve
```

Continue browser work when it returns `ready`; otherwise follow its printed
instruction.

Chrome 144+ shows a per-connection "Allow remote debugging?" prompt. Keep these
steps non-blocking and wizard-style: announce → user authorizes → confirm →
continue. When command output contains a blocking signal, stop and tell the user
exactly what to click — never retry in a loop or leave them staring at a dialog:

| Signal in output | Tell the user to... |
| --- | --- |
| `Chrome is asking "Allow remote debugging?"` | click the Chrome popup's Allow button |
| `permission-blocked: ... not been accepted` | the previous attempt timed out; the popup is asking again — click Allow now, then retry once |
| `handshake-wait: ... popup, click Allow` | click Allow in the Chrome popup |
| `remote debugging is turned off ... chrome://inspect/#remote-debugging` | open chrome://inspect/#remote-debugging and tick "Allow remote debugging" |
| macOS `mac-approve` / popup | run `browser-harness mac-approve` or click Allow |

Approval is per-connection: each new daemon handshake can show the popup again.
After the user clicks Allow, verify with `browser-harness --doctor` that
`active browser connections` is `1` before continuing.

## Page Workflow

- Prefer to find elements with the accessibility tree, not screenshots: `cdp("Accessibility.getFullAXTree")["nodes"]` has every element's role, name, and `backendDOMNodeId` — filter in Python before printing (it is thousands of nodes). Node `role` is a property object, not a plain string, and its nesting varies by Chrome version — normalize it:
  `v = n.get("role") or {}; role = v if isinstance(v, str) else (v.get("value") if isinstance(v.get("value"), str) else (v.get("value") or {}).get("value", ""))`.
  Coordinates: `q = cdp("DOM.getBoxModel", backendNodeId=n)["model"]["content"]; x, y = sum(q[0::2])/4, sum(q[1::2])/4` (viewport px, ready for `click_at_xy`; negative/oversized means scroll first).
- Clicking: AX node -> box center -> `click_at_xy(x, y)` -> verify with a targeted `js(...)`/`page_info()` check. A click that dispatches without effect on a hidden tab needs the same `activate_tab` treatment as a timed-out scroll.
- Fall back to raw HTML via `js(...)` only when the AX tree lacks the element (canvas, exotic widgets); screenshot when layout or imagery matters — `capture_screenshot()` returns a PNG file path, not base64.
- After navigation, call `wait_for_load()`.
- If the current tab is stale or internal, call `ensure_real_tab()`.
- Use `js(...)` for DOM inspection or extraction when coordinates are the wrong tool.
- Login walls: stop and ask. Exception: use available SSO automatically when Chrome is already signed in; still stop for passwords, MFA, consent, or ambiguous account choice.
- Raw CDP is available with `cdp("Domain.method", ...)`.

## X (Twitter) Monitoring via rmux

Two pieces: the `x-supervisor` workspace app (self-healing loop) plus the
`x-worker` app it spawns into a rmux pane. Agent-operated, no autostart;
`browser-harness --update` (or `skills sync`) installs them.

Run as rmux background sessions (reuse one shell; poll on demand — no blocking
command). The worker runs against an **isolated agent Chrome** — never the
user's own Chrome — via `BU_CDP_URL`.

- Start (non-blocking; launches the isolated Chrome if needed and the supervisor
  in a rmux pane, then returns):
  `browser-harness x-monitor`
  -> isolated Chrome on `<BH_HOME>/agent-chrome-profile` + port
     `BH_AGENT_CDP_PORT` (default `9223`); rmux
     sessions `x-supervisor` (supervisor) and `x-monitor` (worker).
  Windows first; WSL2 works headless (S006) once the agent profile is
  logged in to X on that host.
- Poll status/data anytime:
  `browser-harness rmux status`              # are both sessions alive?
  heartbeat freshness at `browser-workspace/x_worker.heartbeat`
  `browser-harness rmux capture x-monitor`   # worker stdout
  `browser-harness x-search --stats`         # how many tweets are stored
- Recover / stop: `browser-harness rmux kill x-monitor` (the supervisor respawns
  on anomaly); stop the supervisor with `browser-harness rmux kill x-supervisor`.

Worker env vars:

- `X_INTERVAL` (default 600) seconds between refresh rounds.
- `X_IDLE_THRESHOLD` (default 10) seconds of no keyboard/mouse required before a
  foreground refresh is allowed.
- `X_IDLE_WAIT` (default 60) max seconds to wait for idle while you are active;
  if you stay active, that round is skipped (no focus steal).
- `X_FOREGROUND=0` disables foreground refresh entirely (pure background).
- `X_DOCK_W` / `X_DOCK_H` (default 520x200) the small taskbar-docked window size.

When the X page is hidden (minimized / background tab) and the user is idle, the
worker shrinks the window to that docked pane, activates the tab to defeat
Chrome's intensive throttling, captures, then minimizes it again.

Tweets are stored in `<BH_HOME>/browser-workspace/x_tweets.db` (deduped, WAL,
searchable). Tweet `author` holds the display name only; `handle` is separate.
When the user asks to analyze:

- "新推 / 最新推 / 刚抓到的 / 最近 1 小时" → report recent captures without the browser:
  `browser-harness x-search --recent --limit N` or `--since 1h`
  or read the live timeline through the browser when "right now" matters.
- "存的推 / 搜推 / 关键词 / 谁发的" → query the store without the browser:
  `browser-harness x-search <keyword>` (`--author X` matches display name or
  @handle, `--limit N`, `--group-by day|hour`, `--csv [--csv-out path.csv]`).
  A primary mode is required: `<keyword>`, `--recent`, `--since`, or `--stats`.
- "存了多少 / 统计 / 谁发得多" → `browser-harness x-search --stats`
  (totals, distinct authors, posted/seen range, top authors)

## Search (Google / Bing)

Workspace helpers `google_search(query, limit)` and `bing_search(query, limit)` each
reuse their own tab, extract `[{title, url}, ...]`, and return them. Use them when
the user asks to search Google or Bing (runs in the real, logged-in browser):

```python
google_search("rust web framework", limit=5)
bing_search("rust web framework", limit=5)
```

## Page content extraction (defuddle)

To read the clean text of a web page (article / docs / any URL), use defuddle.
It strips nav, ads, and boilerplate and returns the main content as Markdown +
metadata. Prefer a plain fetch for public pages; use the browser only for
logged-in or JS-only pages.

In a browser script:

```python
extract_url_content("https://example.com/article", markdown=True)             # plain HTTP
extract_url_content("https://x.com/home", markdown=True, use_browser=True)    # reuse session
extract_page_content(markdown=True)                                           # current tab
```

Returns `{title, url, domain, author, published, description, image, favicon,
language, site, word_count, markdown, text, content_html, engine}`.

Or from the shell (no browser needed for public pages):

```powershell
browser-harness web-fetch "https://example.com/article"          # markdown
browser-harness web-fetch "https://example.com/article" --text   # plain text
browser-harness web-fetch "https://example.com/article" --json    # full metadata
browser-harness web-fetch "https://x.com/home" --browser          # reuse session
browser-harness web-fetch --current                                # current tab
```

Engine order: `pydefuddle` (Python, bundled as a core dependency), then a
stdlib/bs4 fallback. The `engine` field says which one was used. No Node/npx
dependency.

## Browser availability

To know whether there is an operable browser (Chrome running + remote debugging
enabled + daemon connected), poll:

```powershell
browser-harness doctor --json   # parse daemon.browser_ready / chrome_running
```

or run the setup wizard — a guided, step-by-step flow that auto-opens Chrome,
reminds for remote-debugging / Allow, and creates one tab per app (X, Google,
Bing). These scripts live in a git checkout's `browser-workspace/` and are not
part of the installed package:

```powershell
uv run python browser-workspace/browser_wizard.py   # repo checkout only
```

or watch it continuously — this also auto-opens Chrome when none is running,
then reports when the daemon becomes connected:

```powershell
uv run python browser-workspace/browser_watch.py     # repo checkout only
```

In a browser script, `setup_browser_apps()` ensures X / Google / Bing each have
their own tab and returns the target ids.

## Browser instances and tab binding

Use the resource views to check the attached browser before operating:

```powershell
browser-harness browsers   # Chrome instances, tabs, app-tab binding, rmux state
browser-harness current    # currently attached target + CDP attach state
```

- `browsers` marks each instance as `agent` or `user` by profile path.
- X monitoring always uses `agent-chrome-profile` on `BH_AGENT_CDP_PORT`
  (default `9223`); it never touches the user's normal profile.
- `setup_browser_apps()` is idempotent and mutex-like: X, Google, and Bing each
  reuse their own tab rather than opening duplicates.

## Recordings and Videos

Fresh installs do not record. Users can enable local background traces:

```powershell
browser-harness recordings enable
browser-harness recordings disable
browser-harness recordings
```

`BH_RECORD=1` or `BH_RECORD=0` overrides the preference for one process. Any
natural nudge to “record,” “show,” “demo,” or “make a video” opts in that task;
significant work alone does not.

Before browser work, call `start_recording(name, title=...)`, retain its exact
returned directory, and call `stop_recording()` after verifying the result.
Never replace that path with `recordings --latest`. For a request made after
the task, use:

```powershell
browser-harness recordings --latest
```

Use it only if timestamps and pages match; otherwise say the work was not
captured. Never reenact a completed task. For a video, follow
[make-video.md](https://github.com/raystyle/browser-harness/blob/main/interaction-skills/make-video.md).
If sub-agents are available, they may handle post-production from the exact
recording path while the main agent returns the task result.

## Interaction Skills

If you get stuck on a browser mechanic, check the interaction skills — when this
skill is installed they sit right next to this file under `references/interaction/`;
upstream they live at https://github.com/raystyle/browser-harness/tree/main/interaction-skills.

- connection.md
- cookies.md
- cross-origin-iframes.md
- dialogs.md
- downloads.md
- drag-and-drop.md
- dropdowns.md
- iframes.md
- make-video.md
- network-requests.md
- print-as-pdf.md
- screenshots.md
- scrolling.md
- shadow-dom.md
- tabs.md
- uploads.md
- viewport.md

## Design Constraints

- Coordinate clicks default. CDP mouse events pass through iframes/shadow/cross-origin at the compositor level.
- Keep the connection model simple: use the default daemon, `BU_CDP_URL`, or
  `BU_CDP_WS`.
- Trusted orchestrators that already provisioned an exact named daemon can set
  `BH_REQUIRE_EXISTING_DAEMON=1`. Each CLI call then health-checks and reuses
  that daemon or fails closed; it never auto-starts or discovers another Chrome.
- Core helpers stay short. Put task-specific helper additions in `$BH_BROWSER_WORKSPACE/browser_helpers.py`.

## Gotchas

- `chrome://inspect/#remote-debugging` must be enabled for local Chrome control.
- On macOS, if Chrome shows an "Allow remote debugging?" popup, run `browser-harness mac-approve`. Do not poll in a loop — the daemon holds one connection.
- Omnibox popups are not real work tabs.
- CDP target order is not Chrome's visible tab-strip order.
- `BU_CDP_URL` is an HTTP DevTools endpoint; the daemon resolves it to WebSocket.
- The daemon is single-instance per BU_NAME (kernel lock in the runtime dir).
  Concurrent starts defer to the live one, out-wait a starting one, or take
  over if it dies — never spawn a second copy. Always launch via the
  `browser-harness` CLI, never a bare `python -m browser_harness.daemon`
  (interpreter-base mixing, M109).
- A user Chrome with the chrome://inspect remote-debugging toggle listens on a
  DevToolsActivePort (e.g. 9222) that command-line parsing cannot see; check
  the `[inspect-toggle]` section of `browser-harness browsers`. Keep the
  default daemon pinned via `BU_CDP_URL` so it can never ride the user's
  browser.

## Domain Skills

Only applies when `BH_DOMAIN_SKILLS=1`. Otherwise ignore domain skills.

When enabled, look up `$BH_BROWSER_WORKSPACE/domain-skills/<dir>/` before
inventing an approach. **Directory name = the hostname's first label after
stripping a leading `www.`**: `github.com` → `github/`, `www.bing.com` →
`bing/`. Subdomains are their own site — `maps.google.com` → `maps/` (not
`google/`); that is why `gmail` is a directory of its own.

`goto_url(...)` returns up to 10 `.md` filenames for the navigated host (set
`BH_DOMAIN_SKILLS=1` in the same process for the hint). Bundled helper
scripts (e.g. `claude-ai/extract-share-transcript.py`) are not listed — list
the directory itself to find them. `browser-harness skills sync` (also run by `--update`) provisions
the packaged site skills into the workspace (additively — locally added site
skills are never deleted; only this project's own retired pre-v0.4.0 filenames
are pruned on sync).
