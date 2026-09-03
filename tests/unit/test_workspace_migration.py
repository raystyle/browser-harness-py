"""BH_BROWSER_WORKSPACE env chain + pre-v0.6.8 agent-workspace auto-migration."""

from browser_harness import paths


def _make_legacy_tree(root):
    """A realistic pre-v0.6.8 <BH_HOME>/agent-workspace: provisioned apps,
    app data, and a user-added file that must survive the rename."""
    ws = root / "agent-workspace"
    (ws / "apps").mkdir(parents=True)
    (ws / "apps" / "x-search.py").write_text("# app", encoding="utf-8")
    (ws / "domain-skills").mkdir()
    (ws / "x_tweets.db").write_bytes(b"sqlite-ish")
    (ws / "my_notes.md").write_text("user content", encoding="utf-8")
    return ws


def test_env_precedence_new_name_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_BROWSER_WORKSPACE", str(tmp_path / "new"))
    monkeypatch.setenv("BH_AGENT_WORKSPACE", str(tmp_path / "old"))
    assert paths.workspace_dir() == (tmp_path / "new").resolve()


def test_env_legacy_name_still_honored(monkeypatch, tmp_path):
    monkeypatch.delenv("BH_BROWSER_WORKSPACE", raising=False)
    monkeypatch.setenv("BH_AGENT_WORKSPACE", str(tmp_path / "old"))
    assert paths.workspace_dir() == (tmp_path / "old").resolve()


def test_default_dir_migrates_wholesale(monkeypatch, tmp_path):
    """First default-path resolution renames agent-workspace -> browser-workspace,
    moving every file (user-added included) instead of orphaning the old dir."""
    monkeypatch.delenv("BH_BROWSER_WORKSPACE", raising=False)
    monkeypatch.delenv("BH_AGENT_WORKSPACE", raising=False)
    monkeypatch.setattr(paths, "home_dir", lambda: tmp_path)
    legacy = _make_legacy_tree(tmp_path)

    result = paths.workspace_dir()

    assert result == tmp_path / "browser-workspace"
    assert not legacy.exists()                                   # old dir is gone
    assert (result / "x_tweets.db").read_bytes() == b"sqlite-ish"  # data moved
    assert (result / "my_notes.md").read_text(encoding="utf-8") == "user content"
    assert (result / "apps" / "x-search.py").exists()


def test_migration_falls_back_to_old_dir_when_rename_fails(monkeypatch, tmp_path):
    """A locked tree (Windows handles held by a running daemon/Chrome) must not
    break resolution: fall back to the old dir, warn once, survive."""
    monkeypatch.delenv("BH_BROWSER_WORKSPACE", raising=False)
    monkeypatch.delenv("BH_AGENT_WORKSPACE", raising=False)
    monkeypatch.setattr(paths, "home_dir", lambda: tmp_path)
    paths._MIGRATION_WARNED = False
    legacy = _make_legacy_tree(tmp_path)

    def locked_rename(old, new):
        raise OSError("Access is denied")

    monkeypatch.setattr(paths.os, "rename", locked_rename)
    try:
        result = paths.workspace_dir()
    finally:
        paths._MIGRATION_WARNED = False

    assert result == legacy
    assert legacy.exists() and (legacy / "my_notes.md").exists()


def test_fresh_install_skips_migration(monkeypatch, tmp_path):
    """No legacy dir -> the new default is simply created, no error."""
    monkeypatch.delenv("BH_BROWSER_WORKSPACE", raising=False)
    monkeypatch.delenv("BH_AGENT_WORKSPACE", raising=False)
    monkeypatch.setattr(paths, "home_dir", lambda: tmp_path)
    assert paths.workspace_dir() == tmp_path / "browser-workspace"
    assert (tmp_path / "browser-workspace").is_dir()
