from love_risk_engine.core.exposure import Exposure
from love_risk_engine.core.state import EmotionalState, RelationshipState
from love_risk_engine.storage.database import Database


def test_init_creates_tables(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    db.add_relationship("Alex")
    assert db.list_relationships()[0].alias == "Alex"
    db.close()


def test_sequential_relationship_ids(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    r1 = db.add_relationship("Alex")
    r2 = db.add_relationship("Sam")
    assert r1 == "R001"
    assert r2 == "R002"
    db.close()


def test_get_relationship_by_id_and_alias(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    assert db.get_relationship("R001").id == rid
    assert db.get_relationship("Alex").id == rid
    assert db.get_relationship("nope") is None
    db.close()


def test_observation_roundtrip(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    oid = db.add_observation(
        rid,
        "honesty",
        "cancelled plans",
        "losing interest",
        "work deadline",
        "self",
        4.0,
        rationalization=True,
        inconsistency_flag=True,
    )
    obs = db.get_observations(rid)
    assert len(obs) == 1
    assert obs[0].id == oid
    assert obs[0].rationalization is True
    assert obs[0].inconsistency_flag is True
    db.close()


def test_state_clamp_and_upsert(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.upsert_state(
        RelationshipState(
            rid,
            attraction=99,
            trust=-5,
            uncertainty=3,
            emotional_state=EmotionalState.ANXIOUS,
        )
    )
    st = db.get_state(rid)
    assert st.attraction == 10.0
    assert st.trust == 0.0
    assert st.emotional_state == EmotionalState.ANXIOUS
    db.close()


def test_exposure_default_and_upsert(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    assert db.get_exposure(rid) is None
    db.upsert_exposure(Exposure(rid, time=3, emotional=4, privacy=1))
    exp = db.get_exposure(rid)
    assert exp.total == 8.0
    db.close()


def test_inconsistency_resolve(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    iid = db.add_inconsistency(rid, "story mismatch")
    assert len(db.list_inconsistencies(rid)) == 1
    assert db.resolve_inconsistency(iid) is True
    assert len(db.list_inconsistencies(rid)) == 0
    db.close()


def test_boundary_hit_requires_evidence(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    bid = db.add_boundary("no disrespect", severity="HARD")
    hid = db.add_boundary_hit(bid, rid, "they mocked my boundary on call")
    hits = db.list_boundary_hits(rid, only_hard=True)
    assert len(hits) == 1
    assert hits[0].id == hid
    assert hits[0].evidence == "they mocked my boundary on call"
    db.close()
