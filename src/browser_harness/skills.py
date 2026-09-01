"""Sync the packaged skill (SKILL.md + references/) into agent CLI skill dirs."""

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


def _packaged_skill_dir() -> Path:
    return Path(__file__).parent


def _skill_text() -> str:
    """The packaged SKILL.md — must be real content, not the pointer stub."""
    text = (_packaged_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    if text.startswith("..") or "name: browser-harness" not in text:
        raise RuntimeError("packaged SKILL.md is the pointer stub — reinstall browser-harness first")
    return text


def _skill_files(root: Path) -> list[Path]:
    """SKILL.md plus every file under references/, or [] when not installed."""
    files: list[Path] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return files
    files.append(skill)
    refs = root / "references"
    if refs.is_dir():
        files.extend(sorted(p for p in refs.rglob("*") if p.is_file()))
    return files


def _skill_hash(root: Path) -> str | None:
    files = _skill_files(root)
    if not files:
        return None
    h = hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(root)).replace("\\", "/").encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _sync_tree(dst: Path) -> None:
    """Mirror packaged SKILL.md + references/ into dst (agent CLI skill dirs are pure mirrors)."""
    src = _packaged_skill_dir()
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "SKILL.md").write_text(_skill_text(), encoding="utf-8", newline="\n")
    src_refs, dst_refs = src / "references", dst / "references"
    if src_refs.is_dir():
        if dst_refs.exists():
            shutil.rmtree(dst_refs)
        shutil.copytree(src_refs, dst_refs)


def _domain_src() -> Path:
    return _packaged_skill_dir() / "references" / "domain-skills"


def _domain_dst() -> Path:
    from .paths import workspace_dir

    return workspace_dir() / "domain-skills"


def _domain_diff() -> tuple[int, int, int]:
    """(packaged total, missing at destination, differing) for domain-skills."""
    src, dst = _domain_src(), _domain_dst()
    missing = differing = total = 0
    for p in sorted(src.rglob("*.md")):
        total += 1
        t = dst / p.relative_to(src)
        if not t.is_file():
            missing += 1
        elif t.read_bytes() != p.read_bytes():
            differing += 1
    return total, missing, differing


def _sync_domain() -> int:
    """Provision packaged domain-skills into the agent workspace.

    Additive only: overwrite packaged files, never delete — the workspace is
    agent-owned and may hold site skills the user added locally."""
    src, dst = _domain_src(), _domain_dst()
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for p in sorted(src.rglob("*.md")):
        t = dst / p.relative_to(src)
        if not t.is_file() or t.read_bytes() != p.read_bytes():
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
    total, missing, differing = _domain_diff()
    if total == 0:
        return 0
    if not missing and not differing:
        print(f"  workspace up to date    {_domain_dst()}  [{total} domain skills]")
    elif do_sync:
        copied = _sync_domain()
        print(f"  workspace synced        {_domain_dst()}  [{copied} domain skills copied, {total} packaged]")
    else:
        print(f"  workspace OUTDATED      {_domain_dst()}  ({missing} missing, {differing} differ — run: browser-harness skills sync)")
    return 0
