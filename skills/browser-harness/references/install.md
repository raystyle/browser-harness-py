# browser-harness CLI — one-time install prerequisite

This is a **one-time prerequisite**, not part of the regular AI workflow. Do it once; after `browser-harness` prints page info, never repeat install/connection steps during normal browser work.

## Install the command

```powershell
uv tool install --python 3.12 --force git+https://github.com/raystyle/browser-harness
browser-harness --version   # should print the version
```

`--python 3.12` prevents uv from selecting old releases that support older Python versions. `--upgrade --force` replaces any previous `browser-harness` tool install with the latest `main` build. It does not uninstall unrelated commands such as `browser-use-Browser` or `browser-use-Terminal`.

For browser-harness development, clone the repo into a durable path and run `uv tool install -e .` from the checkout.

## Register the skill

Install/register a skill named `browser-harness` using this command for the body:

```powershell
browser-harness skill
```

For Codex:

```powershell
$skillDir = "$env:USERPROFILE\.codex\skills\browser-harness"
New-Item -ItemType Directory -Force $skillDir | Out-Null
browser-harness skill | Set-Content -LiteralPath "$skillDir\SKILL.md" -Encoding utf8
```

If an old user-installed `browser` or `browser-use` skill is being picked instead, remove that stale skill directory manually. Never edit bundled/vendor plugin caches.

## Connect to a browser

`browser-harness` attaches to a local Chrome you already have running. Quick check:

```powershell
@'
print(page_info())
'@ | browser-harness
```

If that prints page info, you're done. If not, run `browser-harness --doctor` and follow the connection cases. The two local connection methods:

- **Way 1 (real browser):** open Chrome normally, then open `chrome://inspect/#remote-debugging` and tick "Allow remote debugging for this browser instance". On Chrome 144+, click Allow on the first-attach popup. Inherits your logins/extensions — best when the agent acts in your everyday browser.
- **Way 2 (isolated agent Chrome):** `browser-harness x-monitor` launches a separate Chrome profile on port `9223` with anti-throttle flags and `BU_CDP_URL` set. Use this for X monitoring and unattended automation; it never touches your normal Chrome profile.

If the quick path fails after `--doctor`, inspect `src/browser_harness/admin.py`, `src/browser_harness/daemon.py`, and `src/browser_harness/_ipc.py`.

## Keeping current

This fork installs from the `main` branch. Upgrade with:

```powershell
browser-harness --update -y
```

One command: it stops the running stack (rmux sessions + daemons, which otherwise
lock the venv on Windows), reinstalls from `main`, re-provisions skills and
workspace apps (additively — local additions are never deleted), and brings back
the x-monitor stack if it was running. The manual
`uv tool install --force git+https://github.com/raystyle/browser-harness`
also works but requires stopping the stack first (M102 in the repo docs).

State lives under `C:\Users\<user>\.config\browser-harness` by default on Windows: agent workspace, agent Chrome profile, runtime sockets, logs, screenshots, and temp files. Override with `BH_HOME` or `BROWSER_HARNESS_HOME`.
