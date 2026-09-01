"""State/exposure change-history tests (roadmap item #1).

Written test-first per PLAN_state_exposure_history.md: these fail until the
history tables + core/history.py exist, then pin snapshot-on-change recording,
no-op skipping, clamping, ordering and the exact delta strings.
"""

from __future__ import annotations

from love_risk_engine.core.exposure import Exposure
from love_risk_engine.core.history import (
    ExposureChange,
    StateChange,
    describe_exposure_change,
    describe_state_change,
)
from love_risk_engine.core.state import EmotionalState, RelationshipState
from love_risk_engine.storage.database import Database


def _db(tmp_path) -> tuple[Database, str]:
    db = Database(str(tmp_path / "t.db"))
    db.init()
    return db, db.add_relationship("Alex")


def test_upsert_state_records_baseline_on_first_write(tmp_path):
    db, rid = _db(tmp_path)
    db.upsert_state(
        RelationshipState(
            rid,
            attraction=7.5,
            trust=4.0,
            uncertainty=2.0,
            emotional_state=EmotionalState.CALM,
        )
    )
    rows = db.list_state_history(rid)
    assert len(rows) == 1
    assert rows[0].id == "SH001"
    assert rows[0].attraction == 7.5
    assert rows[0].emotional_state == "CALM"
    db.close()


def test_upsert_state_records_changed_values(tmp_path):
    db, rid = _db(tmp_path)
    db.upsert_state(RelationshipState(rid, attraction=7.5))
    db.upsert_state(RelationshipState(rid, attraction=8.5))
    rows = db.list_state_history(rid)
    assert [r.attraction for r in rows] == [7.5, 8.5]
    db.close()


def test_upsert_state_skips_unchanged_write(tmp_path):
    db, rid = _db(tmp_path)
    db.upsert_state(RelationshipState(rid, attraction=7.5))
    db.upsert_state(RelationshipState(rid, attraction=7.5))
    assert len(db.list_state_history(rid)) == 1
    db.close()


def test_upsert_state_history_holds_clamped_values(tmp_path):
    db, rid = _db(tmp_path)
    db.upsert_state(RelationshipState(rid, attraction=99, trust=-5))
    rows = db.list_state_history(rid)
    assert rows[0].attraction == 10.0
    assert rows[0].trust == 0.0
    db.close()


def test_upsert_exposure_records_baseline_and_change(tmp_path):
    db, rid = _db(tmp_path)
    db.upsert_exposure(Exposure(rid, time=1, emotional=2))
    db.upsert_exposure(Exposure(rid, time=3, emotional=2))
    rows = db.list_exposure_history(rid)
    assert [r.time for r in rows] == [1.0, 3.0]
    db.close()


def test_upsert_exposure_skips_unchanged_write(tmp_path):
    db, rid = _db(tmp_path)
    db.upsert_exposure(Exposure(rid, time=1, emotional=2))
    db.upsert_exposure(Exposure(rid, time=1, emotional=2))
    assert len(db.list_exposure_history(rid)) == 1
    db.close()


def test_list_state_history_returns_ordered_domain_objects(tmp_path):
    db, rid = _db(tmp_path)
    for attraction in (7.5, 8.0, 8.5):
        db.upsert_state(RelationshipState(rid, attraction=attraction))
    rows = db.list_state_history(rid)
    assert [r.id for r in rows] == ["SH001", "SH002", "SH003"]
    assert all(isinstance(r, StateChange) for r in rows)
    db.close()


def test_list_exposure_history_returns_ordered_domain_objects(tmp_path):
    db, rid = _db(tmp_path)
    for time in (1.0, 2.0):
        db.upsert_exposure(Exposure(rid, time=time))
    rows = db.list_exposure_history(rid)
    assert [r.id for r in rows] == ["EH001", "EH002"]
    assert all(isinstance(r, ExposureChange) for r in rows)
    db.close()


def test_history_ids_are_sequential():
    # Prefixes are independent sequences, both starting at 001.
    assert StateChange("SH001", "R001", "t", 0.0, 0.0, 0.0, "NEUTRAL").id == "SH001"
    assert ExposureChange("EH001", "R001", "t", 0.0, 0.0, 0.0, 0.0, 0.0).id == "EH001"


def test_describe_state_change_baseline_and_delta():
    baseline = describe_state_change(
        None,
        StateChange("SH001", "R001", "t", 7.5, 4.0, 2.0, "ANXIOUS"),
    )
    assert (
        baseline
        == "baseline: attraction 7.5, trust 4.0, uncertainty 2.0, emotional ANXIOUS"
    )

    prev = StateChange("SH001", "R001", "t", 7.5, 4.0, 2.0, "CALM")
    curr = StateChange("SH002", "R001", "t2", 8.5, 5.0, 2.0, "CALM")
    expected = "attraction 7.5 -> 8.5, trust 4.0 -> 5.0"
    assert describe_state_change(prev, curr) == expected

    # emotional-only change
    tense = StateChange("SH003", "R001", "t3", 8.5, 5.0, 2.0, "TENSE")
    assert describe_state_change(curr, tense) == "emotional CALM -> TENSE"

    # nothing changed -> empty description (defensive; storage never records it)
    same = StateChange("SH004", "R001", "t4", 8.5, 5.0, 2.0, "CALM")
    assert describe_state_change(curr, same) == ""


def test_describe_exposure_change_baseline_and_delta():
    baseline = describe_exposure_change(
        None,
        ExposureChange("EH001", "R001", "t", 1.0, 2.0, 0.0, 0.0, 0.0),
    )
    assert baseline == (
        "baseline: total 3.0 (time 1.0, emotional 2.0, privacy 0.0, "
        "financial 0.0, life_decision 0.0)"
    )

    prev = ExposureChange("EH001", "R001", "t", 1.0, 2.0, 0.0, 0.0, 0.0)
    curr = ExposureChange("EH002", "R001", "t2", 3.0, 2.0, 0.0, 0.0, 0.0)
    assert describe_exposure_change(prev, curr) == "total 3.0 -> 5.0 (time 1.0 -> 3.0)"

    same = ExposureChange("EH003", "R001", "t3", 3.0, 2.0, 0.0, 0.0, 0.0)
    assert describe_exposure_change(curr, same) == ""
