"""browser-harness filesystem layout."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def home_dir() -> Path:
    raw = os.environ.get("BH_HOME") or os.environ.get("BROWSER_HARNESS_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return (Path(base).expanduser() / "browser-harness").resolve()
    return (Path.home() / ".config" / "browser-harness").resolve()


def ensure_private_dir(path: Path) -> Path:
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if not existed and sys.platform != "win32":
        os.chmod(path, 0o700)
    return path


def config_dir() -> Path:
    raw = os.environ.get("BH_CONFIG_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir())


def inspect_marker() -> Path:
    """Marker recording that the harness opened a chrome://inspect tab"""
    return config_dir() / "inspect-opened"


def runtime_dir() -> Path:
    raw = os.environ.get("BH_RUNTIME_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "runtime")


def tmp_dir() -> Path:
    raw = os.environ.get("BH_TMP_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "tmp")


def workspace_dir() -> Path:
    raw = os.environ.get("BH_BROWSER_WORKSPACE") or os.environ.get("BH_AGENT_WORKSPACE")
    if raw:
        return ensure_private_dir(Path(raw).expanduser().resolve())
    return _migrate_legacy_dir(home_dir() / "agent-workspace", home_dir() / "browser-workspace")


_MIGRATION_WARNED = False


def _migrate_legacy_dir(old: Path, new: Path) -> Path:
    """Rename a pre-v0.6.8 default layout dir to its browser-* name.

    Runs on the first default-path resolution, before anything mkdirs the new
    name — the rename moves the whole tree (user-added files, x_tweets.db,
    recordings) instead of orphaning it. Explicit BH_* env vars pin the
    location and are honored as-is, no migration. A failure (typically
    Windows handles held by a running daemon) re-checks whether a concurrent
    racer already did the rename, else falls back to the old dir with a
    one-time warning; --update stops the stack, so its next run retries
    naturally.
    """
    global _MIGRATION_WARNED
    if new.exists() or not old.exists():
        return ensure_private_dir(new)
    try:
        os.rename(old, new)
        return ensure_private_dir(new)
    except OSError:
        if new.exists():  # a concurrent first-caller already moved it
            return ensure_private_dir(new)
        if not _MIGRATION_WARNED:
            _MIGRATION_WARNED = True
            print(
                f"browser-harness: could not rename {old} to {new} (files in"
                " use?); staying on the old location for now —"
                " browser-harness --update after the stack stops will retry",
                file=sys.stderr,
            )
        return ensure_private_dir(old)
