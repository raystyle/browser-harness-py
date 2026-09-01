"""Workspace agent_helpers merge semantics + workspace app routing."""

import importlib
from pathlib import Path

from browser_harness import helpers, run


def test_agent_helpers_merges_instead_of_replacing(tmp_path, monkeypatch):
    """A workspace agent_helpers.py overrides per function; packaged helpers stay."""
    (tmp_path / "agent_helpers.py").write_text(
        "def my_custom_helper():\n    return 'ws'\n\n\ndef google_search(query, limit=5):\n"
        "    return [{'title': 'overridden', 'url': 'x'}]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", tmp_path)
    try:
        helpers._load_agent_helpers()
        assert helpers.my_custom_helper() == "ws"               # workspace addition
        assert helpers.google_search("q", limit=1)[0]["title"] == "overridden"  # override
        assert callable(helpers.detect_page_blocks)             # packaged survivor
        assert callable(helpers.extract_url_content)            # packaged survivor
    finally:
        monkeypatch.undo()
        importlib.reload(helpers)  # restore the real merge state


def test_workspace_app_lookup(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "hello.py").write_text("print('hi')", encoding="utf-8")
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", tmp_path)
    assert run.workspace_app("hello") == apps / "hello.py"
    assert run.workspace_app("missing") is None
    assert run.workspace_app("../evil") is None
    assert run.workspace_app("-h") is None
    assert run.workspace_app("") is None
