---
name: browser-install
description: Install browser-harness and connect it to a browser fast.
---

# browser-harness install

Use once. For browser work, read `SKILL.md`.

## Fast Path

This fork installs from GitHub, not PyPI:

```powershell
uv tool install --python 3.12 --upgrade --force git+https://github.com/raystyle/browser-harness@dev/work
```

Register the Codex skill:

```powershell
$skillDir = "$env:USERPROFILE\.codex\skills\browser-harness"
New-Item -ItemType Directory -Force $skillDir | Out-Null
browser-harness skill | Set-Content -LiteralPath "$skillDir\SKILL.md" -Encoding utf8
```

Quick browser check:

```powershell
@'
print(page_info())
'@ | browser-harness
```

If `page_info()` prints, configure recording consent below, then stop.

`--python 3.12` prevents uv from selecting old releases that support older Python versions. `--upgrade --force` replaces any previous `browser-harness` tool install with the latest `dev/work` build.

For Claude Code or other agents: install `browser-harness`, register a skill named `browser-harness`, use `browser-harness skill` as the body, and use this trigger:

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

If an old user-installed `browser` or `browser-use` skill is being picked instead, remove that stale skill directory manually. Do not edit bundled/vendor plugin caches.

## Recording Consent

Run `browser-harness recordings`. If it reports `(default)`, ask the user once:

> Enable local browser recordings? This saves screenshots and action traces on
> this machine, which may include sensitive page content, so you can later ask
> "show me what you did" or request a video. Videos are never generated
> automatically. [y/N]

Default to no. Run `browser-harness recordings enable` only after yes; otherwise
run `browser-harness recordings disable`. Preserve an existing `(config)` or
`(BH_RECORD)` preference during upgrades instead of asking again.

## If Chrome Blocks It

In Chrome:

1. Open `chrome://inspect/#remote-debugging`.
2. Tick "Allow remote debugging for this browser instance".
3. Retry `page_info()`.

If that reports `permission-blocked` on macOS, handle the per-connection Allow
sheet without bringing Chrome to the foreground:

```bash
browser-harness mac-approve
```

Continue browser work when the helper returns `ready`; otherwise follow its
printed instruction. The first checkbox is intentionally a one-time manual
Chrome setup step; it is not exposed to the harness until CDP is available.

The helper requires Accessibility permission for the app launching the CLI
(for example Terminal, iTerm, Codex, or an IDE) in System Settings.

## Isolated Agent Chrome

X monitoring does not use your normal Chrome. Start it with:

```powershell
browser-harness x-monitor
```

This launches an isolated `agent-chrome-profile` on port `9223` with
anti-throttle flags and pins the worker to it via `BU_CDP_URL`.

## If Still Broken

```powershell
browser-harness --doctor
```

Use the output:

- `chrome running` FAIL: ask the user to open Chrome, or start the isolated
  agent Chrome via `browser-harness x-monitor`.
- `daemon alive` FAIL: Chrome remote debugging permission is missing, Chrome is
  closed, or the CDP endpoint is not reachable.
- `rmux` FAIL: install rmux under `%LOCALAPPDATA%\rmux` or make `rmux` available
  on PATH; see README.

For a machine-readable health check, an orchestrator can set `BU_NAME` to an
already-provisioned daemon and run:

```powershell
browser-harness doctor --json --require-existing-daemon
```

This prints a versioned JSON report and exits nonzero unless that exact daemon
has a live browser connection. It never starts or discovers another browser.

If this still fails, inspect `src/browser_harness/admin.py`, `src/browser_harness/daemon.py`, and `src/browser_harness/_ipc.py`.

Useful:

```powershell
browser-harness --update -y
```

State lives under `C:\Users\<user>\.config\browser-harness` by default on Windows: agent workspace, agent Chrome profile, runtime sockets, logs, screenshots, and temp files. Override with `BH_HOME` or `BROWSER_HARNESS_HOME`.
