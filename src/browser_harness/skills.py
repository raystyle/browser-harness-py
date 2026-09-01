"""Sync the packaged skill (SKILL.md + references/) into agent CLI skill dirs
and provision workspace payload dirs (domain-skills/, apps/) additively."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

# Agent CLIs that follow the Agent Skills layout (<root>/skills/<name>/).
_SKILL_DIRS = {
    "claude": Path.home() / ".claude" / "skills" / "browser-harness",
    "codex": Path.home() / ".codex" / "skills" / "browser-harness",
}

# Workspace payload dirs provisioned from packaged references/ (same name).
# Additive sync only — the workspace is agent-owned and may hold content the
# user or agent added locally; provisioning never deletes.
_PROVISION_DIRS = ("domain-skills", "apps")

# Files this project itself shipped into the workspace root before the v0.4.0
# apps/ layout and later retired. Sync removes exactly these names so upgraded
# machines drop pre-v0.4.0 relics; anything else in the workspace (user/agent
# additions, agent_helpers.py overrides) is never touched.
_RETIRED_WORKSPACE_FILES = (
    "browser_watch.py",
    "browser_wizard.py",
    "page_text.py",
    "start-x-monitor.ps1",
    "x_monitor.py",
    "x_search.py",
    "x_supervisor.py",
    "x_worker.py",
)


def _prune_retired_files(dst_root: Path) -> int:
    removed = 0
    for name in _RETIRED_WORKSPACE_FILES:
        p = dst_root / name
        if p.is_file():
            p.unlink()
            removed += 1
    return removed


def _packaged_skill_dir() -> Path:
    return Path(__file__).parent


def _skill_text() -> str:
    """The packaged SKILL.md — must be real content, not the pointer stub."""
    text = (_packaged_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    if text.startswith("..") or "name: browser-harness" not in text:
        raise RuntimeError("packaged SKILL.md is the pointer stub — reinstall browser-harness first")
    return text


def _skill_files(root: Path) -> list[Path]:
    """The skill bundle: SKILL.md + references/install.md + references/interaction/.

    domain-skills are deliberately NOT part of the CLI skill bundle — they are
    workspace-only (goto_url and agents read them from the agent workspace)."""
    files: list[Path] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return files
    files.append(skill)
    refs = root / "references"
    for name in ("install.md", "interaction"):
        p = refs / name
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(q for q in p.rglob("*") if q.is_file()))
    return files


_TEXT_SUFFIXES = (".md", ".py")


def _norm_bytes(p: Path) -> bytes:
    """File bytes with CRLF folded to LF for text payloads (M107).

    A CRLF checkout (Windows autocrlf) must hash/compare equal to the LF
    copy we sync out, else every status run reports OUTDATED forever."""
    data = p.read_bytes()
    if p.suffix in _TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return data


def _skill_hash(root: Path) -> str | None:
    files = _skill_files(root)
    if not files:
        return None
    h = hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(root)).replace("\\", "/").encode())
        h.update(_norm_bytes(p))
    return h.hexdigest()[:16]


def _sync_tree(dst: Path) -> None:
    """Mirror the skill bundle (SKILL.md + install.md + interaction/) into dst."""
    src = _packaged_skill_dir()
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "SKILL.md").write_text(_skill_text(), encoding="utf-8", newline="\n")
    src_refs, dst_refs = src / "references", dst / "references"
    dst_refs.mkdir(parents=True, exist_ok=True)
    for name in ("install.md", "interaction"):
        s = src_refs / name
        if not s.exists():
            continue
        d = dst_refs / name
        if d.is_dir():
            shutil.rmtree(d)
        elif d.exists():
            d.unlink()
        if s.is_dir():
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)


# --- workspace provisioning (domain-skills / apps) ---

def _provision_src(name: str) -> Path:
    return _packaged_skill_dir() / "references" / name


def _provision_dst(name: str) -> Path:
    from .paths import workspace_dir

    return workspace_dir() / name


def _provision_files(root: Path) -> list[Path]:
    """Payload files: markdown plus bundled helper scripts (no .gitkeep)."""
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".py"))


def _provision_diff(name: str) -> tuple[int, int, int]:
    """(packaged total, missing at destination, differing)."""
    src, dst = _provision_src(name), _provision_dst(name)
    missing = differing = total = 0
    for p in _provision_files(src):
        total += 1
        t = dst / p.relative_to(src)
        if not t.is_file():
            missing += 1
        elif _norm_bytes(t) != _norm_bytes(p):
            differing += 1
    return total, missing, differing


def _provision_sync(name: str) -> int:
    src, dst = _provision_src(name), _provision_dst(name)
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for p in _provision_files(src):
        t = dst / p.relative_to(src)
        if not t.is_file() or _norm_bytes(t) != _norm_bytes(p):
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(p.read_bytes())
            copied += 1
    return copied


def run_cli(args: list[str]) -> int:
    do_sync = bool(args) and args[0] == "sync"
    if args and not do_sync:
        print("usage: browser-harness skills [sync]", file=sys.stderr)
        return 2
    try:
        _skill_text()  # fail fast on the pointer stub
    except (OSError, RuntimeError) as e:
        print(f"skills: {e}", file=sys.stderr)
        return 1
    src = _packaged_skill_dir()
    want = _skill_hash(src)
    for tool, d in _SKILL_DIRS.items():
        root = d.parent.parent  # ~/.claude or ~/.codex
        cur = _skill_hash(d)
        if cur == want:
            print(f"  {tool:8s} up to date    {d}")
            continue
        if not do_sync:
            if cur is None and not root.is_dir():
                print(f"  {tool:8s} not installed  {root} not present")
            else:
                print(f"  {tool:8s} OUTDATED      {d}  (run: browser-harness skills sync)")
            continue
        _sync_tree(d)
        print(f"  {tool:8s} synced         {d}  [{len(_skill_files(d))} files]")
    for name in _PROVISION_DIRS:
        total, missing, differing = _provision_diff(name)
        if total == 0:
            continue
        dst = _provision_dst(name)
        if not missing and not differing:
            print(f"  workspace up to date    {dst}  [{total} {name}]")
        elif do_sync:
            copied = _provision_sync(name)
            print(f"  workspace synced        {dst}  [{copied}/{total} {name} copied]")
        else:
            print(f"  workspace OUTDATED      {dst}  ({missing} missing, {differing} differ — run: browser-harness skills sync)")
    if do_sync:
        from .paths import workspace_dir

        pruned = _prune_retired_files(workspace_dir())
        if pruned:
            print(f"  workspace pruned        {pruned} retired pre-v0.4.0 file(s) removed")
    return 0
