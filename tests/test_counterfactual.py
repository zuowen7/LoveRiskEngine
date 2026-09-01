"""Counterfactual review tests (roadmap #2, architecture phase 2).

Written test-first per docs/proposals/PLAN_counterfactual_review.md: these
fail until `core/counterfactual.py` + `services/counterfactual.py` exist, then
pin the freeze semantics, the current-rules-on-past-evidence recompute, and
the MATCHED/DIFFERENT audit output.
"""

from __future__ import annotations

import pytest
from love_risk_engine.core.boundaries import BoundaryHit
from love_risk_engine.core.counterfactual import (
    freeze_boundary_hits,
    freeze_exposure,
    freeze_inconsistency_count,
    freeze_observations,
    freeze_state,
)
from love_risk_engine.core.history import ExposureChange, StateChange
from love_risk_engine.core.inconsistency import Inconsistency
from love_risk_engine.core.observation import Observation
from love_risk_engine.core.state import EmotionalState, RelationshipState
from love_risk_engine.services.counterfactual import run_counterfactual
from love_risk_engine.services.review import run_review
from love_risk_engine.storage.database import Database

T = "2026-08-20T12:00:00+00:00"


def _state_change(oid: str, ts: str, attraction: float) -> StateChange:
    return StateChange(oid, "R001", ts, attraction, 4.0, 2.0, "CALM")


def _exposure_change(oid: str, ts: str, time: float) -> ExposureChange:
    return ExposureChange(oid, "R001", ts, time, 0.0, 0.0, 0.0, 0.0)


def _obs(oid: str, ts: str) -> Observation:
    return Observation(
        id=oid,
        relationship_id="R001",
        timestamp=ts,
        category="x",
        observation="o",
        interpretation="i",
        alternative_explanation="a",
        source="self",
        confidence=5.0,
    )


def test_freeze_state_picks_latest_at_or_before():
    history = [
        _state_change("SH001", "2026-08-10T00:00:00+00:00", 7.0),
        _state_change("SH002", "2026-08-18T00:00:00+00:00", 8.0),
        _state_change("SH003", "2026-08-25T00:00:00+00:00", 9.0),  # after T
    ]
    frozen = freeze_state(history, "R001", T)
    assert frozen.attraction == 8.0
    assert frozen.trust == 4.0
    assert frozen.emotional_state is EmotionalState.CALM


def test_freeze_state_defaults_when_no_history():
    frozen = freeze_state([], "R001", T)
    assert frozen.attraction == 0.0
    assert frozen.emotional_state is EmotionalState.NEUTRAL


def test_freeze_exposure_picks_latest_at_or_before():
    history = [
        _exposure_change("EH001", "2026-08-10T00:00:00+00:00", 1.0),
        _exposure_change("EH002", "2026-08-25T00:00:00+00:00", 5.0),  # after T
    ]
    frozen = freeze_exposure(history, "R001", T)
    assert frozen.time == 1.0
    assert frozen.total == 1.0


def test_freeze_observations_filters_after_as_of():
    observations = [
        _obs("O001", "2026-08-10T00:00:00+00:00"),
        _obs("O002", "2026-08-21T00:00:00+00:00"),  # after T
    ]
    assert [o.id for o in freeze_observations(observations, T)] == ["O001"]


def test_freeze_boundary_hits_filters_after_as_of():
    hits = [
        BoundaryHit("H001", "B001", "R001", "evidence", "2026-08-10T00:00:00+00:00"),
        BoundaryHit("H002", "B001", "R001", "evidence", "2026-08-21T00:00:00+00:00"),
    ]
    assert [h.id for h in freeze_boundary_hits(hits, T)] == ["H001"]


def test_freeze_inconsistency_count_counts_created_before_and_still_open():
    items = [
        Inconsistency(
            "I001", "R001", "before, open", False, "2026-08-10T00:00:00+00:00"
        ),
        Inconsistency(
            "I002", "R001", "before, resolved", True, "2026-08-11T00:00:00+00:00"
        ),
        Inconsistency("I003", "R001", "after", False, "2026-08-21T00:00:00+00:00"),
    ]
    # Approximate by design: resolutions carry no timestamp.
    assert freeze_inconsistency_count(items, T) == 1


def _days_ago_iso(days: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")


def test_freeze_state_fails_open_on_corrupt_emotional_state():
    history = [
        StateChange(
            "SH001", "R001", "2026-08-10T00:00:00+00:00", 7.0, 4.0, 2.0, "NOT_A_STATE"
        )
    ]
    frozen = freeze_state(history, "R001", T)
    assert frozen.attraction == 7.0
    assert frozen.emotional_state is EmotionalState.NEUTRAL


def test_run_counterfactual_recomputes_with_frozen_evidence(tmp_path, monkeypatch):
    import love_risk_engine.storage.database as database
    from love_risk_engine.core.review import Review

    db = Database(str(tmp_path / "t.db"))
    try:
        db.init()
        rid = db.add_relationship("Alex")
        # Deterministic timestamps: state A at -10d, review at -5d, then
        # evidence at -1d that must NOT leak into the frozen context.
        monkeypatch.setattr(database, "_now", lambda: _days_ago_iso(10))
        db.upsert_state(RelationshipState(rid, attraction=7.5))
        db.save_review(
            Review(
                id="RV001",
                relationship_id=rid,
                timestamp=_days_ago_iso(5),
                triggered_hooks=[],
                unresolved_inconsistencies=0,
                recommendation="CONTINUE_OBSERVING",
                notes="",
            )
        )
        monkeypatch.setattr(database, "_now", lambda: _days_ago_iso(1))
        db.upsert_state(RelationshipState(rid, attraction=9.9))
        db.add_observation(rid, "x", "later", "i", "a", "self", 5.0)

        result = run_counterfactual(db, rid, "RV001")
        assert result.evidence.attraction == 7.5
        assert result.evidence.observation_count == 0
        assert result.matched  # same rules, same frozen evidence -> same verdict
    finally:
        db.close()


def test_run_counterfactual_unknown_review_raises(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    try:
        db.init()
        rid = db.add_relationship("Alex")
        with pytest.raises(ValueError, match="not found"):
            run_counterfactual(db, rid, "RV999")
    finally:
        db.close()


def test_run_counterfactual_wrong_relationship_raises(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    try:
        db.init()
        rid = db.add_relationship("Alex")
        rid2 = db.add_relationship("Sam")
        review = run_review(db, rid)
        with pytest.raises(ValueError, match="relationship"):
            run_counterfactual(db, rid2, review.id)
    finally:
        db.close()
