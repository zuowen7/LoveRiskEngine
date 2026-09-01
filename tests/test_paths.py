"""Data-home path resolution tests (architecture phase 1, D2).

Written test-first per docs/proposals/PLAN_phase1_data_safety.md: these fail
until `storage/paths.py` exists, then pin platform resolution and the legacy
CWD fallback that must never orphan existing data.
"""

from __future__ import annotations

from pathlib import Path

from love_risk_engine.storage.paths import _home, default_db_path, resolve_db_path


def test_home_matches_expanduser():
    assert _home() == str(Path("~").expanduser())


def _patch_home(monkeypatch, home: str) -> None:
    import love_risk_engine.storage.paths as paths

    monkeypatch.setattr(paths, "_home", lambda: home)


def test_default_db_path_windows_uses_localappdata(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\x\AppData\Local")
    assert default_db_path() == r"C:\Users\x\AppData\Local\LoveRiskEngine\love_risk.db"


def test_default_db_path_windows_falls_back_to_userprofile(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("USERPROFILE", r"C:\Users\x")
    assert default_db_path() == r"C:\Users\x\LoveRiskEngine\love_risk.db"


def test_default_db_path_macos(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    _patch_home(monkeypatch, "/Users/x")
    assert (
        default_db_path()
        == "/Users/x/Library/Application Support/LoveRiskEngine/love_risk.db"
    )


def test_default_db_path_linux_uses_xdg(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/home/x/.data")
    assert default_db_path() == "/home/x/.data/LoveRiskEngine/love_risk.db"


def test_default_db_path_linux_falls_back_to_dot_local_share(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    _patch_home(monkeypatch, "/home/x")
    assert default_db_path() == "/home/x/.local/share/LoveRiskEngine/love_risk.db"


def test_resolve_db_path_explicit_wins(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "linux")
    explicit = str(tmp_path / "custom.db")
    assert resolve_db_path(explicit) == explicit


def test_resolve_db_path_uses_legacy_cwd_db_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "love_risk.db").write_text("", encoding="utf-8")
    monkeypatch.setattr("sys.platform", "linux")
    _patch_home(monkeypatch, "/home/x")
    # Relative, as before the data-home change — resolution happens against CWD.
    assert resolve_db_path() == "love_risk.db"


def test_resolve_db_path_goes_to_data_dir_without_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no love_risk.db here
    monkeypatch.setattr("sys.platform", "linux")
    _patch_home(monkeypatch, "/home/x")
    assert resolve_db_path() == "/home/x/.local/share/LoveRiskEngine/love_risk.db"
