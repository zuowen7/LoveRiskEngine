"""Calibration / evaluation tests (measurement phase, v1).

Written test-first per docs/proposals/PLAN_license_docs_calibration.md: these
fail until schema v5 + `core/calibration.py` exist, then pin the labeling
lifecycle and the honest per-rule statistics.
"""

from __future__ import annotations

import pytest
from love_risk_engine.core.calibration import (
    VALID_OUTCOMES,
    compute_calibration,
)
from love_risk_engine.core.review import Review
from love_risk_engine.storage.database import Database


def _review(rid: str, hooks: list[str]) -> Review:
    return Review(
        id=rid,
        relationship_id="R001",
        timestamp="2026-09-01T00:00:00+00:00",
        triggered_hooks=hooks,
        unresolved_inconsistencies=0,
        recommendation="CONTINUE_OBSERVING",
        notes="",
    )


def test_label_creates_outcome_row(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rel = db.add_relationship("Alex")
    db.save_review(_review("RV001", ["attraction_exceeds_trust"]))
    assert db.label_review_outcome("RV001", "bad", "it got worse") is True
    outcomes = db.list_review_outcomes(rel)
    assert len(outcomes) == 1
    assert outcomes[0].review_id == "RV001"
    assert outcomes[0].outcome == "bad"
    assert outcomes[0].note == "it got worse"
    db.close()


def test_relabel_overwrites(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rel = db.add_relationship("Alex")
    db.save_review(_review("RV001", ["attraction_exceeds_trust"]))
    db.label_review_outcome("RV001", "bad", "")
    assert db.label_review_outcome("RV001", "good", "corrected") is True
    outcomes = db.list_review_outcomes(rel)
    assert len(outcomes) == 1  # labels are judgments, not evidence: overwrite
    assert outcomes[0].outcome == "good"
    assert outcomes[0].note == "corrected"
    db.close()


def test_invalid_outcome_rejected(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    db.add_relationship("Alex")
    db.save_review(_review("RV001", []))
    with pytest.raises(ValueError):
        db.label_review_outcome("RV001", "awesome", "")
    db.close()


def test_compute_calibration_per_rule_stats():
    reviews = [
        _review("RV001", ["attraction_exceeds_trust", "promise_expiry"]),
        _review("RV002", ["attraction_exceeds_trust"]),
        _review("RV003", []),
        _review("RV004", ["attraction_exceeds_trust"]),  # fired, never labeled
    ]
    outcomes = {
        "RV001": type("O", (), {"review_id": "RV001", "outcome": "bad"})(),
        "RV002": type("O", (), {"review_id": "RV002", "outcome": "good"})(),
    }
    report = compute_calibration(reviews, list(outcomes.values()))
    assert report.total_reviews == 4
    assert report.reviews_labeled == 2
    stats = {s.rule_id: s for s in report.rules}
    assert stats["attraction_exceeds_trust"].fired == 3
    assert stats["attraction_exceeds_trust"].labeled == 2
    assert stats["attraction_exceeds_trust"].bad == 1
    assert stats["promise_expiry"].fired == 1
    assert stats["promise_expiry"].bad == 1  # labeled bad on RV001
    assert isinstance(VALID_OUTCOMES, tuple) and "neutral" in VALID_OUTCOMES


def test_compute_calibration_empty():
    report = compute_calibration([], [])
    assert report.rules == []
    assert report.total_reviews == 0
    assert report.reviews_labeled == 0
