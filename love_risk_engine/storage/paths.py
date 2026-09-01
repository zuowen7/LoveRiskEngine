"""Data-home path resolution (architecture phase 1, D2).

One database per user, discoverable: the default lives in the platform data
directory instead of wherever `lre` happens to be invoked. `LRE_DB_PATH`
overrides, and a legacy `./love_risk.db` in the working directory still wins
over the data dir — existing data is never orphaned by an upgrade.
"""

from __future__ import annotations

import os
import posixpath
import sys
from pathlib import Path


def _home() -> str:
    """User home directory (isolated for testability)."""
    return str(Path("~").expanduser())


def default_db_path() -> str:
    """Platform data dir / LoveRiskEngine / love_risk.db.

    The POSIX branches use `posixpath` explicitly — identical to `os.path` on
    those platforms, but deterministic when tested from any host.
    """
    if sys.platform == "win32":
        base = (
            os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE") or _home()
        )
        data_dir = str(Path(base) / "LoveRiskEngine")
        return str(Path(data_dir) / "love_risk.db")
    if sys.platform == "darwin":
        data_dir = posixpath.join(
            _home(), "Library", "Application Support", "LoveRiskEngine"
        )
    else:
        base = os.environ.get("XDG_DATA_HOME") or posixpath.join(
            _home(), ".local", "share"
        )
        data_dir = posixpath.join(base, "LoveRiskEngine")
    return posixpath.join(data_dir, "love_risk.db")


def resolve_db_path(explicit: str | None = None) -> str:
    """Resolution order: explicit path, legacy CWD file, platform data dir."""
    if explicit:
        return explicit
    if Path("love_risk.db").exists():
        return "love_risk.db"  # legacy data: keep using it, never orphan it
    return default_db_path()
