"""`browser-harness skills sync` mirrors the packaged skill into agent CLI dirs."""

from pathlib import Path

from browser_harness import skills


def test_sync_creates_and_updates(tmp_path, monkeypatch):
    fake = {
        "claude": tmp_path / "claude" / "skills" / "browser-harness",
        "codex": tmp_path / "codex" / "skills" / "browser-harness",
    }
    monkeypatch.setattr(skills, "_SKILL_DIRS", fake)
    monkeypatch.setattr(skills, "_domain_dst", lambda: tmp_path / "workspace" / "domain-skills")

    assert skills.run_cli([]) == 0  # status run: nothing crashes, nothing created
    assert not fake["claude"].exists()

    assert skills.run_cli(["sync"]) == 0
    want = skills._skill_hash(skills._packaged_skill_dir())
    assert skills._skill_hash(fake["claude"]) == want
    assert skills._skill_hash(fake["codex"]) == want
    assert (fake["claude"] / "SKILL.md").is_file()
    assert (fake["codex"] / "references" / "interaction" / "tabs.md").is_file()
    # Domain skills are workspace-only; they never land in CLI skill dirs.
    assert not (fake["codex"] / "references" / "domain-skills").exists()

    # Domain skills land in the workspace, additively.
    total, missing, _ = skills._domain_diff()
    if total:
        assert missing == 0
        assert skills._domain_dst().is_dir()

    # Locally added site skills survive a resync.
    keep = skills._domain_dst() / "mysite" / "custom.md"
    if total:
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text("# mine", encoding="utf-8")
        assert skills.run_cli(["sync"]) == 0
        assert keep.is_file()

    # A second sync is a no-op that still reports success.
    assert skills.run_cli(["sync"]) == 0


def test_bad_subcommand_usage():
    assert skills.run_cli(["bogus"]) == 2
