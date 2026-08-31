from love_risk_engine.core.decision import Decision
from love_risk_engine.core.exposure import Exposure
from love_risk_engine.core.state import EmotionalState, RelationshipState
from love_risk_engine.services.review import run_review
from love_risk_engine.storage.database import Database


def test_review_default_continue_observing(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.upsert_state(RelationshipState(rid, attraction=3, trust=3, uncertainty=4))
    db.upsert_exposure(Exposure(rid, time=1))
    review = run_review(db, rid)
    assert review.recommendation == Decision.CONTINUE_OBSERVING.value
    assert "empty" in review.notes  # safe default: empty evidence base
    db.close()


def test_review_high_emotion_major_decision_pauses(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.upsert_state(
        RelationshipState(
            rid,
            attraction=5,
            trust=5,
            uncertainty=3,
            emotional_state=EmotionalState.ANXIOUS,
        )
    )
    db.upsert_exposure(Exposure(rid, life_decision=5))
    review = run_review(db, rid)
    assert review.recommendation == Decision.PAUSE.value
    db.close()


def test_review_hard_boundary_hit_exits(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.upsert_state(RelationshipState(rid))
    db.upsert_exposure(Exposure(rid))
    bid = db.add_boundary("no manipulation", severity="HARD")
    db.add_boundary_hit(bid, rid, "gaslit me after I set a boundary")
    review = run_review(db, rid)
    assert review.recommendation == Decision.EXIT.value
    db.close()
