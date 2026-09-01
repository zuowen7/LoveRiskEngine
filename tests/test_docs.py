"""Executable documentation guards (architecture invariant #11).

The build fails when the docs drift from the code — no habit required. Each
guard pins one claim that has actually drifted before (detector counts,
schema version, license, bilingual docs).
"""

from __future__ import annotations

import re
from pathlib import Path

from love_risk_engine.core.profiles import PROFILES
from love_risk_engine.storage.schema import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parent.parent


def _read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _detector_count() -> int:
    return len({hook for p in PROFILES.values() for hook in p.enabled_hooks})


def test_readme_detector_count_matches_code():
    match = re.search(r"ships (\d+) detectors", _read_text("README.md"))
    assert match, "README.md must state the detector count ('ships N detectors')"
    assert int(match.group(1)) == _detector_count()


def test_readme_zh_detector_count_matches_code():
    match = re.search(r"内置 (\d+) 个检测器", _read_text("README_zh.md"))
    assert match, "README_zh.md must state the detector count ('内置 N 个检测器')"
    assert int(match.group(1)) == _detector_count()


def test_overview_mentions_current_schema_version():
    overview = _read_text("docs/overview.md")
    assert f"schema v{SCHEMA_VERSION}" in overview


def test_license_file_is_apache_2():
    text = _read_text("LICENSE")
    assert "Apache License" in text
    assert "Version 2.0" in text
    pyproject = _read_text("pyproject.toml")
    assert "Apache-2.0" in pyproject


def test_bilingual_docs_exist_and_are_linked():
    for relative in (
        "README_zh.md",
        "docs/getting-started.en.md",
        "docs/getting-started.zh.md",
    ):
        assert (ROOT / relative).exists(), f"missing {relative}"
    readme = _read_text("README.md")
    assert "README_zh.md" in readme
    assert "docs/getting-started.en.md" in readme
    assert "docs/getting-started.zh.md" in readme


def test_cli_usage_mentions_export_restore():
    readme = _read_text("README.md")
    assert "lre export" in readme
    assert "lre restore" in readme
    assert "lre db check" in readme
