"""The packaged skill must be real content and stay in sync with the repo."""

from pathlib import Path

import browser_harness

_PKG = Path(browser_harness.__file__).parent
_PKG_SKILL = _PKG / "SKILL.md"
_REPO = _PKG_SKILL.resolve().parents[2]


def test_packaged_skill_is_real_content():
    text = _PKG_SKILL.read_text(encoding="utf-8")
    assert text.startswith("---"), "packaged SKILL.md lost its frontmatter"
    assert "name: browser-harness" in text
    assert "../../SKILL.md" not in text, (
        "packaged SKILL.md is the pointer stub — `browser-harness skill` would print garbage"
    )


def test_packaged_skill_matches_repo_root():
    repo = _REPO / "SKILL.md"
    if not repo.is_file():
        return  # installed (non-repo) environment: nothing to sync against
    assert _PKG_SKILL.read_text(encoding="utf-8") == repo.read_text(encoding="utf-8"), (
        "src/browser_harness/SKILL.md drifted from the repo root SKILL.md — copy the root file over it"
    )


def test_plugin_skill_copy_matches_repo_root():
    plugin = _REPO / "skills" / "browser-harness" / "SKILL.md"
    root = _REPO / "SKILL.md"
    if not (plugin.is_file() and root.is_file()):
        return  # installed (non-repo) environment
    assert plugin.read_text(encoding="utf-8") == root.read_text(encoding="utf-8"), (
        "skills/browser-harness/SKILL.md drifted from the repo root SKILL.md"
    )


def test_packaged_references_match_interaction_skills():
    src = _REPO / "interaction-skills"
    dst = _PKG / "references" / "interaction"
    if not src.is_dir():
        return  # installed (non-repo) environment
    src_files = {p.name: p.read_text(encoding="utf-8") for p in src.glob("*.md")}
    dst_files = {p.name: p.read_text(encoding="utf-8") for p in dst.glob("*.md")}
    assert dst_files == src_files, (
        "src/browser_harness/references/interaction/ drifted from interaction-skills/ — recopy it"
    )
