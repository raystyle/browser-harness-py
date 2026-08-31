from importlib import resources

import pytest


def _packaged_skill_is_stub() -> bool:
    """True when the packaged SKILL.md is a symlink stub (git core.symlinks=false)."""
    try:
        text = resources.files("browser_harness").joinpath("SKILL.md").read_text()
    except Exception:
        return True
    return not text.startswith("---\n")


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    assert end != -1
    return text[4:end]


@pytest.mark.skipif(
    _packaged_skill_is_stub(),
    reason="packaged SKILL.md is a symlink stub (git core.symlinks=false)",
)
def test_packaged_skill_frontmatter_is_valid_simple_yaml():
    text = resources.files("browser_harness").joinpath("SKILL.md").read_text()
    metadata = {}

    for line in _frontmatter(text).splitlines():
        key, separator, value = line.partition(":")
        assert separator == ":", line
        assert key in {"name", "description"}
        assert key.strip() == key
        value = value.strip()
        assert value, key

        if value[0] in {"'", '"'}:
            assert value[-1] == value[0], line
            parsed = value[1:-1]
        else:
            parsed = value
            assert ": " not in parsed, line

        metadata[key] = parsed

    assert metadata == {
        "name": "browser-harness",
        "description": "Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.",
    }
