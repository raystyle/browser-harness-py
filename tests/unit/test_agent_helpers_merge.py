"""Workspace browser_helpers merge semantics + workspace app routing."""

import importlib
from pathlib import Path

import pytest

from browser_harness import helpers, run


def test_agent_helpers_merges_instead_of_replacing(tmp_path, monkeypatch):
    """A workspace browser_helpers.py overrides per function; packaged helpers stay."""
    (tmp_path / "browser_helpers.py").write_text(
        "def my_custom_helper():\n    return 'ws'\n\n\ndef google_search(query, limit=5):\n"
        "    return [{'title': 'overridden', 'url': 'x'}]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(helpers, "BROWSER_WORKSPACE", tmp_path)
    try:
        helpers._load_browser_helpers()
        assert helpers.my_custom_helper() == "ws"               # workspace addition
        assert helpers.google_search("q", limit=1)[0]["title"] == "overridden"  # override
        assert callable(helpers.detect_page_blocks)             # packaged survivor
        assert callable(helpers.extract_url_content)            # packaged survivor
    finally:
        monkeypatch.undo()
        importlib.reload(helpers)  # restore the real merge state


def test_legacy_workspace_helper_filename_still_merges(tmp_path, monkeypatch):
    """Pre-v0.6.8 workspaces have agent_helpers.py; the loader must keep
    reading that name (new browser_helpers.py wins when both exist)."""
    (tmp_path / "agent_helpers.py").write_text(
        "def legacy_named_helper():\n    return 'legacy'\n", encoding="utf-8"
    )
    monkeypatch.setattr(helpers, "BROWSER_WORKSPACE", tmp_path)
    try:
        helpers._load_browser_helpers()
        assert helpers.legacy_named_helper() == "legacy"
    finally:
        monkeypatch.undo()
        importlib.reload(helpers)


def test_workspace_app_lookup(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "hello.py").write_text("print('hi')", encoding="utf-8")
    monkeypatch.setattr(helpers, "BROWSER_WORKSPACE", tmp_path)
    assert run.workspace_app("hello") == apps / "hello.py"
    assert run.workspace_app("missing") is None
    assert run.workspace_app("../evil") is None
    assert run.workspace_app("-h") is None
    assert run.workspace_app("") is None


# --- stdin/command mode dual compatibility (Issue #2) ---

def test_pipe_namespace_import_chain_exposes_app_entrypoints():
    """run.py pre-imports the exec namespace via `from .helpers import *`.
    Replicate that exact chain and require the app entry points to survive it
    — Issue #2's NameError was a break in precisely this chain (app cores
    without names matching their CLI subcommands)."""
    ns = {}
    exec("from browser_harness.helpers import *", ns)
    assert callable(ns["web_fetch"])
    assert callable(ns["run_app"])
    assert callable(ns["google_search"])  # the one that already worked


def test_web_fetch_alias_defaults_match_the_cli_app(monkeypatch):
    """CLI semantics: plain HTTP first (--browser is opt-in), markdown by
    default. The alias must keep those defaults so both modes mean the same
    call."""
    from browser_harness import browser_helpers

    seen = {}

    def fake_extract(url, markdown=True, use_browser=True):
        seen.update(url=url, markdown=markdown, use_browser=use_browser)
        return {"markdown": "ok"}

    monkeypatch.setattr(browser_helpers, "extract_url_content", fake_extract)
    assert browser_helpers.web_fetch("https://example.com") == {"markdown": "ok"}
    assert seen == {"url": "https://example.com", "markdown": True, "use_browser": False}
    browser_helpers.web_fetch("https://example.com/x", use_browser=True, markdown=False)
    assert seen == {"url": "https://example.com/x", "markdown": False, "use_browser": True}


def test_legacy_agent_helpers_module_is_a_reexport_shim():
    """v0.6.8 renamed agent_helpers -> browser_helpers; the old import path
    must stay usable for one release (workspace copies, external code)."""
    from browser_harness import agent_helpers, browser_helpers

    assert agent_helpers.web_fetch is browser_helpers.web_fetch
    assert agent_helpers.google_search is browser_helpers.google_search


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_app_runs_the_cli_subcommand_verbatim(monkeypatch):
    """run_app must spawn exactly `python -m browser_harness.run <name> <args>`
    so pipe code and command dispatch stay one code path."""
    import sys

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _FakeProc(stdout="42\n")

    monkeypatch.setattr("subprocess.run", fake_run)
    assert helpers.run_app("x-search", "--stats") == "42\n"
    assert captured["cmd"] == [
        sys.executable, "-m", "browser_harness.run", "x-search", "--stats",
    ]
    assert captured["kwargs"]["encoding"] == "utf-8"


def test_run_app_parses_json_output(monkeypatch):
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _FakeProc(stdout='{"a": 1}\n'))
    assert helpers.run_app("browsers", json_output=True) == {"a": 1}


def test_run_app_raises_with_stderr_tail_on_failure(monkeypatch):
    monkeypatch.setattr(
        "subprocess.run", lambda cmd, **kw: _FakeProc(returncode=2, stderr="usage: boom")
    )
    with pytest.raises(RuntimeError, match="exited 2.*boom"):
        helpers.run_app("missing-app")


# --- search block reporting (Issue #3 semantics: blocked ≠ no results) ---


def _patch_search_env(monkeypatch, blocks, links):
    from browser_harness import browser_helpers

    monkeypatch.setattr(browser_helpers, "ensure_app_tab", lambda key, url: "t-goog")
    monkeypatch.setattr(helpers, "goto_url", lambda u: {})
    monkeypatch.setattr(helpers, "wait_for_load", lambda timeout=20: True)
    monkeypatch.setattr(helpers, "wait_for_element", lambda sel, timeout=10: True)
    monkeypatch.setattr(helpers, "switch_tab", lambda t, activate=False: None)
    monkeypatch.setattr(browser_helpers, "detect_page_blocks", lambda: blocks)
    monkeypatch.setattr(browser_helpers, "_extract_links", lambda limit, exclude: links)
    return browser_helpers


def test_google_search_reports_block_instead_of_silent_empty(capsys, monkeypatch):
    bh = _patch_search_env(
        monkeypatch,
        blocks=[{"type": "block", "reason": "sorry page"}],
        links=[{"title": "never-returned", "url": "https://x"}],
    )
    assert bh.google_search("q") == []
    assert "blocked" in capsys.readouterr().err


def test_google_search_clean_path_returns_links(capsys, monkeypatch):
    bh = _patch_search_env(monkeypatch, blocks=[], links=[{"title": "t", "url": "https://x"}])
    assert bh.google_search("q")[0]["title"] == "t"
    assert capsys.readouterr().err == ""


def test_bing_search_reports_block_instead_of_silent_empty(capsys, monkeypatch):
    bh = _patch_search_env(
        monkeypatch,
        blocks=[{"type": "cloudflare", "reason": "challenge URL"}],
        links=[],
    )
    monkeypatch.setattr(helpers, "js", lambda expr: [])
    assert bh.bing_search("q") == []
    assert "blocked" in capsys.readouterr().err
