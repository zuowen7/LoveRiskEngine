"""i18n tests (localization phase, docs/proposals/PLAN_i18n_rich_docs.md).

Written test-first: these fail until core/i18n.py exists, then pin language
resolution, catalog completeness, placeholder substitution, fail-open
behavior, and display-time finding localization.
"""

from __future__ import annotations

from love_risk_engine.core.bias_detector import BiasFinding
from love_risk_engine.core.i18n import (
    CATALOG,
    Language,
    current_language,
    localize_finding,
    t,
)


def test_current_language_defaults_to_en(monkeypatch):
    monkeypatch.delenv("LRE_LANG", raising=False)
    assert current_language() is Language.EN


def test_current_language_reads_zh(monkeypatch):
    monkeypatch.setenv("LRE_LANG", "zh")
    assert current_language() is Language.ZH


def test_current_language_unknown_env_falls_back_to_en(monkeypatch):
    monkeypatch.setenv("LRE_LANG", "klingon")
    assert current_language() is Language.EN


def test_t_placeholder_substitution(monkeypatch):
    monkeypatch.setenv("LRE_LANG", "zh")
    assert t("verified_facts", v=1, t=2) == "已验证事实：1 / 2"


def test_t_falls_back_to_msgid_for_unknown_key():
    assert t("no_such_key_xyz") == "no_such_key_xyz"  # never crashes


def test_catalog_has_both_languages_for_every_key():
    for msgid, entry in CATALOG.items():
        assert Language.EN in entry, f"{msgid} missing English"
        assert Language.ZH in entry, f"{msgid} missing Chinese"


def test_localize_finding_uses_key(monkeypatch):
    monkeypatch.setenv("LRE_LANG", "zh")
    f = BiasFinding(
        "unresolved_inconsistencies",
        "3 unresolved inconsistencies.",
        severity=3,
        proposed_decision="CONTINUE_OBSERVING",
        msg_key="unresolved_inconsistencies",
        msg_params={"count": "3"},
    )
    assert localize_finding(f) == "3 个未解决的矛盾。"


def test_localize_finding_falls_back_to_message():
    f = BiasFinding("legacy_rule", "legacy english text", severity=2)
    assert localize_finding(f) == "legacy english text"
