import os

from love_risk_engine.core.cooldown import (
    Cooldown,
    cooldown_hours_for,
    format_remaining,
    is_active,
    is_blocking,
)
from love_risk_engine.core.decision import Decision
from love_risk_engine.storage.database import Database


def test_is_blocking_only_for_pause_decrease_exit():
    assert is_blocking(Decision.PAUSE)
    assert is_blocking(Decision.DECREASE_EXPOSURE)
    assert is_blocking(Decision.EXIT)
    assert not is_blocking(Decision.CONTINUE_OBSERVING)
    assert not is_blocking(Decision.WAIT)


def test_default_hours_per_decision():
    assert cooldown_hours_for(Decision.PAUSE) == 24
    assert cooldown_hours_for(Decision.DECREASE_EXPOSURE) == 48
    assert cooldown_hours_for(Decision.EXIT) == 72


def test_env_override_applies_uniformly(monkeypatch):
    monkeypatch.setenv("LRE_COOLDOWN_HOURS", "6")
    assert cooldown_hours_for(Decision.PAUSE) == 6
    assert cooldown_hours_for(Decision.EXIT) == 6


def test_env_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("LRE_COOLDOWN_HOURS", "not-a-number")
    assert cooldown_hours_for(Decision.PAUSE) == 24


def test_is_active_logic():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    future = (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat(timespec="seconds")
    past = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(timespec="seconds")
    assert is_active(Cooldown("C1", "R001", "PAUSE", "", now, future, True), now=now)
    assert not is_active(Cooldown("C2", "R001", "PAUSE", "", now, past, True), now=now)
    assert not is_active(Cooldown("C3", "R001", "PAUSE", "", now, future, False), now=now)


def test_review_creates_cooldown_on_blocking_decision(tmp_path):
    from love_risk_engine.core.exposure import Exposure
    from love_risk_engine.core.state import EmotionalState, RelationshipState
    from love_risk_engine.services.review import run_review
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.upsert_state(RelationshipState(
        rid, emotional_state=EmotionalState.OVERWHELMED))
    db.upsert_exposure(Exposure(rid, life_decision=5))
    review = run_review(db, rid)
    assert review.recommendation == Decision.PAUSE.value
    assert review.cooldown_id.startswith("C")
    cds = db.list_cooldowns(rid, active_only=True)
    assert len(cds) == 1
    assert cds[0]["decision"] == "PAUSE"
    db.close()


def test_no_cooldown_on_continue_observing(tmp_path):
    from love_risk_engine.core.exposure import Exposure
    from love_risk_engine.core.state import RelationshipState
    from love_risk_engine.services.review import run_review
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.upsert_state(RelationshipState(rid, attraction=3, trust=3, uncertainty=4))
    db.upsert_exposure(Exposure(rid, time=1))
    review = run_review(db, rid)
    assert review.recommendation == Decision.CONTINUE_OBSERVING.value
    assert review.cooldown_id == ""
    assert db.list_cooldowns(rid, active_only=True) == []
    db.close()


def test_clear_cooldowns(tmp_path):
    from love_risk_engine.core.exposure import Exposure
    from love_risk_engine.core.state import EmotionalState, RelationshipState
    from love_risk_engine.services.review import run_review
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.upsert_state(RelationshipState(rid, emotional_state=EmotionalState.OVERWHELMED))
    db.upsert_exposure(Exposure(rid, life_decision=5))
    run_review(db, rid)
    assert len(db.list_cooldowns(rid, active_only=True)) == 1
    n = db.clear_cooldowns(rid)
    assert n == 1
    assert db.list_cooldowns(rid, active_only=True) == []
    db.close()


def test_override_log_recorded(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    cid = db.add_cooldown(rid, "PAUSE", "test", "2026-01-01T00:00:00+00:00",
                          "2026-01-02T00:00:00+00:00")
    oid = db.log_override(rid, cid, "deliberate", "2026-01-01T12:00:00+00:00")
    assert oid.startswith("OV")
    ovs = db.list_overrides(rid)
    assert len(ovs) == 1
    assert ovs[0]["reason"] == "deliberate"
    db.close()
