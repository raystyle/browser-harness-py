<!-- LOCAL-FORK-WORKFLOW:START -->

## Local project definition

This working copy is a personal fork of `browser-use/browser-harness` for local development and testing. Upstream is read-only here; personal work is pushed to the fork `raystyle/browser-harness`.

## Context: remotes and branches

- `origin`: `https://github.com/browser-use/browser-harness.git` (upstream; fetch/pull only)
- `mine`: `https://github.com/raystyle/browser-harness.git` (personal fork; push target)
- `main`: mirrors `origin/main`; never edited directly
- `dev/work`: active local development branch

## Rules

1. Never push to `origin`; pull upstream only with `git pull --ff-only origin main`.
2. Develop on `dev/work`, not `main`; keep `main` a clean fast-forward mirror.
3. Push personal branches to `mine` with `git push -u mine dev/work`.
4. Before merging upstream, commit or stash `dev/work` changes, then run `git switch main && git pull --ff-only origin main && git switch dev/work && git merge main`.
5. Reinstall dependencies only when `pyproject.toml` changed after a merge (uv resolves from it).
6. Local verify loop: `./browser-harness --doctor`; `uv run --with pytest python -m pytest tests/unit -q` for unit tests.

<!-- LOCAL-FORK-WORKFLOW:END -->

<!-- PROJECT-STRUCTURE:START -->

## Project structure

Planning and docs follow the `ohmyagents` conventions (Chinese content):

- Root planning docs: `GOAL.md` (goal), `PLAN.md` (how), `TODO.md` (status), `INDEX.md` (unique index), plus `ROADMAP.md` (phases) and `CHANGELOG.md` (milestones).
- `docs/` is split into `proven/` (P), `diary/`, `research/` (S), `references/` (R), `guide/` (G, with `template.md`), `mistakes/` (M).
- Source stays in `src/browser_harness/`; tests in `tests/`; skills in `skills/`, `interaction-skills/`, and `agent-workspace/`.
- `INDEX.md` is the canonical map. Do not move `src/`, `tests/`, `install.md`, `SKILL.md`, or skill directories without updating every reference.

<!-- PROJECT-STRUCTURE:END -->

browser-harness is a thin layer that connects agents to browsers via an editable CDP harness.

# Code priorities
- Clarity
- Precision
- Low verbosity
- Versatility

# Overview
Core code lives in `src/browser_harness/`:
- `admin.py` — daemon lifecycle, diagnostics, updates, profile management
- `daemon.py` — the long-lived middleman process between the browser and the agent
- `helpers.py` — CDP wrapper and core browser primitives auto-imported into the scripts the CLI reads from stdin
- `run.py` — the `browser-harness` CLI

`SKILL.md` tells agents how to use the harness and CLI.
`install.md` tells agents how to install it, attach a browser, and troubleshoot.

An agent operating the harness only edits inside `agent-workspace/`:
- `agent_helpers.py` — task-specific browser helpers the agent adds
- `domain-skills/` — skills the agent writes and reads

Package/CLI name = `browser-harness`. Skill identity (`name` + trigger) = `browser-use` (do not rename).

# Commands

From a **git checkout** (no global install required for local testing):

```bash
# doctor — install/daemon/browser state
./browser-harness --doctor

# smoke — CDP attach + page_info (Chrome remote debugging must be allowed)
./browser-harness <<'PY'
print(page_info())
PY

# unit tests (no live browser)
uv run --with pytest python -m pytest tests/unit -q

# after core/src edits: reload daemon so next call picks up code
./browser-harness --reload
```

Notes:
- `./browser-harness` = local tree launcher. Agents/docs outside this repo use the installed `browser-harness` command.
- Integration tests under `tests/integration/` may need a live browser/CDP — prefer unit + doctor for routine PR gates.
- First-time install / blocked Chrome: follow `install.md` (`chrome://inspect/#remote-debugging`).

# Security
- Do not commit secrets, Browser Use Cloud tokens, or session cookies.
- Prefer the smallest change that fixes the bug; do not expand CDP surface without need.

# Contributing
Consider what is really needed. Prefer the smallest diff that fixes the bug.
Domain skills under `agent-workspace/domain-skills/` are agent-generated when possible — hand-author only when necessary.
