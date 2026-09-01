"""`browser-harness skills sync` mirrors the packaged skill into agent CLI dirs."""

from pathlib import Path

from browser_harness import skills


def test_sync_creates_and_updates(tmp_path, monkeypatch):
    fake = {
        "claude": tmp_path / "claude" / "skills" / "browser-harness",
        "codex": tmp_path / "codex" / "skills" / "browser-harness",
    }
    monkeypatch.setattr(skills, "_SKILL_DIRS", fake)
    monkeypatch.setattr(skills, "_provision_dst", lambda name: tmp_path / "workspace" / name)

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

    # Workspace payload dirs (domain-skills, apps) provision additively.
    for name in skills._PROVISION_DIRS:
        total, missing, _ = skills._provision_diff(name)
        if total:
            assert missing == 0
            assert skills._provision_dst(name).is_dir()

            # Locally added content survives a resync.
            keep = skills._provision_dst(name) / "mine-custom" / "keep.md"
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_text("# mine", encoding="utf-8")
            assert skills.run_cli(["sync"]) == 0
            assert keep.is_file()

    # A second sync is a no-op that still reports success.
    assert skills.run_cli(["sync"]) == 0


def test_bad_subcommand_usage():
    assert skills.run_cli(["bogus"]) == 2


def test_sync_prunes_retired_relics_but_keeps_user_files(tmp_path, monkeypatch, capsys):
    fake = {
        "claude": tmp_path / "claude" / "skills" / "browser-harness",
        "codex": tmp_path / "codex" / "skills" / "browser-harness",
    }
    monkeypatch.setattr(skills, "_SKILL_DIRS", fake)
    monkeypatch.setattr(skills, "_provision_dst", lambda name: tmp_path / "workspace" / name)
    ws = tmp_path / "workspace"
    ws.mkdir()
    # pre-v0.4.0 relics on a machine that lived through old layouts...
    (ws / "x_worker.py").write_text("old", encoding="utf-8")
    (ws / "page_text.py").write_text("old", encoding="utf-8")
    (ws / "start-x-monitor.ps1").write_text("old", encoding="utf-8")
    # ...plus files that must never be touched.
    (ws / "agent_helpers.py").write_text("overrides", encoding="utf-8")
    (ws / "my-custom-app.py").write_text("mine", encoding="utf-8")

    import browser_harness.paths as paths_mod
    monkeypatch.setattr(paths_mod, "workspace_dir", lambda: ws)

    assert skills.run_cli(["sync"]) == 0
    assert not (ws / "x_worker.py").exists()
    assert not (ws / "page_text.py").exists()
    assert not (ws / "start-x-monitor.ps1").exists()
    assert (ws / "agent_helpers.py").read_text(encoding="utf-8") == "overrides"
    assert (ws / "my-custom-app.py").read_text(encoding="utf-8") == "mine"
    assert "pruned" in capsys.readouterr().out
