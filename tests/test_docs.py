"""Executable documentation guards (architecture invariant #11).

The build fails when the docs drift from the code — no habit required. Each
guard pins one claim that has actually drifted before (detector counts,
schema version, license, bilingual docs).
"""

from __future__ import annotations

import re
from pathlib import Path

from love_risk_engine.core.profiles import PROFILES
from love_risk_engine.core.rulespec import RULE_SPECS
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


def test_scientific_foundations_rule_table_matches_registry():
    """docs/SCIENTIFIC_FOUNDATIONS.md Table 2 is the projection of
    core/rulespec.py::RULE_SPECS. Both directions of drift fail the build:
    a registered rule missing from the doc, or a doc row with no registry
    entry."""
    doc = _read_text("docs/SCIENTIFIC_FOUNDATIONS.md")
    rows = re.findall(r"^\| `([a-z_]+)` \|", doc, flags=re.MULTILINE)
    assert len(rows) == len(RULE_SPECS), (
        f"doc rule table has {len(rows)} rows, registry has {len(RULE_SPECS)}"
    )
    assert set(rows) == set(RULE_SPECS), (
        f"doc/registry mismatch: doc={sorted(rows)} registry={sorted(RULE_SPECS)}"
    )


def test_readme_links_scientific_foundations_and_disclaims_validation():
    readme = _read_text("README.md")
    assert "docs/SCIENTIFIC_FOUNDATIONS.md" in readme
    # Normalize whitespace so line-wrapping in the README cannot break the
    # contract.
    flat = " ".join(readme.split())
    assert "have not been clinically or empirically validated" in flat


# --- ADR (Architecture Decision Records) guards ------------------------------
#
# ADRs are the sediment layer: they record *why* a load-bearing decision
# stuck. The guards below keep the catalog honest — an ADR that drifts from
# the template, an orphan ADR the index never lists, or a stale index link
# to a file that no longer exists all fail the build.
#
# See docs/adr/README.md for the template and conventions.

_ADR_DIR = ROOT / "docs" / "adr"
_ADR_REQUIRED_SECTIONS = (
    "## Context",
    "## Decision",
    "## Consequences",
    "## Enforcement",
)
_ADR_REQUIRED_META = (
    "**Status:**",
    "**Date:**",
    "**Decides:**",
)
_ADR_INDEX_LINK = re.compile(r"^- \[(\d{4}) —", re.MULTILINE)


def _adr_files() -> list[Path]:
    return sorted(p for p in _ADR_DIR.glob("*.md") if p.name != "README.md")


def test_adr_index_lists_every_adr_file_and_no_orphans():
    """The README index and the files on disk must agree in both directions:
    every ADR file is linked, and every link resolves to a file. An ADR that
    nobody indexed is invisible to future-you; a link to a deleted ADR is a
    lie."""
    index = _read_text("docs/adr/README.md")
    linked_numbers = {match.group(1) for match in _ADR_INDEX_LINK.finditer(index)}
    file_numbers = {p.stem[:4] for p in _adr_files()}
    missing_from_index = file_numbers - linked_numbers
    stale_in_index = linked_numbers - file_numbers
    assert not missing_from_index, (
        f"ADR files not listed in docs/adr/README.md: {sorted(missing_from_index)}"
    )
    assert not stale_in_index, (
        f"index lists ADRs with no file: {sorted(stale_in_index)}"
    )


def test_adr_numbers_are_sequential_from_0001():
    """A skipped number implies a deleted ADR — and we do not rewrite
    history. A superseded ADR stays on disk pointing at its successor; it
    is never renumbered or removed."""
    numbers = sorted(int(p.stem[:4]) for p in _adr_files())
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"ADR numbers must be sequential from 0001, got {numbers}"
    )


def test_each_adr_has_required_sections_and_meta():
    """An ADR missing Context/Decision/Consequences/Enforcement is a
    half-recorded decision — the whole point is that future-you can tell
    *why* the decision stuck and *what gate enforces it*. A template drift
    here means the next ADR will inherit the gap."""
    for path in _adr_files():
        text = path.read_text(encoding="utf-8")
        for section in _ADR_REQUIRED_SECTIONS:
            assert section in text, f"{path.name} missing required section {section!r}"
        for meta in _ADR_REQUIRED_META:
            assert meta in text, f"{path.name} missing required meta field {meta!r}"


def test_contributing_links_testing_philosophy():
    """CONTRIBUTING.md's Tests section must link docs/TESTING.md. The
    philosophy doc is the single point of truth for *why* the suite is
    shaped the way it is; if the link rots, future-you re-derives the
    testing rules from scattered memory notes — which is how the rules
    drift in the first place."""
    contributing = _read_text("CONTRIBUTING.md")
    assert "docs/TESTING.md" in contributing, (
        "CONTRIBUTING.md must link docs/TESTING.md from its Tests section"
    )
    assert (ROOT / "docs" / "TESTING.md").exists(), "docs/TESTING.md must exist"
