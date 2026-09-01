"""The packaged SKILL.md must be real content, not the repo-root pointer stub."""

from pathlib import Path

import browser_harness

_PKG_SKILL = Path(browser_harness.__file__).parent / "SKILL.md"


def test_packaged_skill_is_real_content():
    text = _PKG_SKILL.read_text(encoding="utf-8")
    assert text.startswith("---"), "packaged SKILL.md lost its frontmatter"
    assert "name: browser-harness" in text
    assert "../../SKILL.md" not in text, (
        "packaged SKILL.md is the pointer stub — `browser-harness skill` would print garbage"
    )


def test_packaged_skill_matches_repo_root():
    repo = _PKG_SKILL.resolve().parents[2] / "SKILL.md"
    if not repo.is_file():
        return  # installed (non-repo) environment: nothing to sync against
    assert _PKG_SKILL.read_text(encoding="utf-8") == repo.read_text(encoding="utf-8"), (
        "src/browser_harness/SKILL.md drifted from the repo root SKILL.md — copy the root file over it"
    )
