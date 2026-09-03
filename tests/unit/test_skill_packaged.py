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


def test_packaged_references_match_domain_skills():
    src = _REPO / "browser-workspace" / "domain-skills"
    dst = _PKG / "references" / "domain-skills"
    if not src.is_dir():
        return  # installed (non-repo) environment
    src_files = {str(p.relative_to(src)): p.read_bytes() for p in src.rglob("*.md")}
    dst_files = {str(p.relative_to(dst)): p.read_bytes() for p in dst.rglob("*.md")}
    assert dst_files == src_files, (
        "src/browser_harness/references/domain-skills/ drifted from browser-workspace/domain-skills/ — recopy it"
    )


def test_packaged_references_match_workspace_apps():
    src = _REPO / "browser-workspace" / "apps"
    dst = _PKG / "references" / "apps"
    if not src.is_dir():
        return  # installed (non-repo) environment
    src_files = {str(p.relative_to(src)): p.read_bytes() for p in src.glob("*.py")}
    dst_files = {str(p.relative_to(dst)): p.read_bytes() for p in dst.glob("*.py")}
    assert dst_files == src_files, (
        "src/browser_harness/references/apps/ drifted from browser-workspace/apps/ — recopy it"
    )


def test_no_app_modules_left_in_package():
    """X/search/fetch moved to workspace apps; the package must not carry them."""
    for gone in ("xapps.py", "x_worker.py", "x_supervisor.py", "x_search.py", "web_fetch.py"):
        assert not (_PKG / gone).is_file(), f"{gone} should live in browser-workspace/apps/, not the package"
