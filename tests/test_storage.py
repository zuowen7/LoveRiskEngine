import pytest
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


# ---------------------------------------------------------------------------
# relationship kinds (relationship-kinds proposal, S1)
# ---------------------------------------------------------------------------


def test_relationship_kind_defaults_to_lover(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    db.add_relationship("Alex")
    assert db.get_relationship("Alex").kind == "LOVER"
    db.close()


def test_add_relationship_stores_kind(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    db.add_relationship("Mentor", kind="MENTOR")
    assert db.get_relationship("Mentor").kind == "MENTOR"
    db.close()


def test_add_relationship_rejects_unknown_kind(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    with pytest.raises(ValueError):
        db.add_relationship("Alex", kind="BESTIE")
    db.close()


def test_set_relationship_kind_updates(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    assert db.set_relationship_kind(rid, "BOSS") is True
    assert db.get_relationship(rid).kind == "BOSS"
    db.close()


def test_set_relationship_kind_unknown_relationship(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    assert db.set_relationship_kind("R999", "BOSS") is False
    db.close()


def test_set_relationship_kind_rejects_unknown_kind(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    with pytest.raises(ValueError):
        db.set_relationship_kind(rid, "SIDEKICK")
    db.close()


# ---------------------------------------------------------------------------
# bulk export / restore / integrity primitives (architecture phase 1)
# ---------------------------------------------------------------------------


def test_export_all_tables_covers_every_table(tmp_path):
    from love_risk_engine.storage.schema import TABLE_ORDER

    db = Database(str(tmp_path / "t.db"))
    db.init()
    assert set(db.export_all_tables()) == set(TABLE_ORDER)
    db.close()


def test_restore_all_tables_replaces_contents(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.add_observation(rid, "x", "o", "i", "a", "self", 5.0)
    snapshot = db.export_all_tables()

    db.add_relationship("Later")
    assert len(db.list_relationships()) == 2
    db.restore_all_tables(snapshot)
    assert len(db.list_relationships()) == 1
    assert db.export_all_tables() == snapshot
    db.close()


def test_integrity_check_ok_on_fresh_db(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    ok, detail, violations = db.integrity_check()
    assert ok is True
    assert detail == "ok"
    assert violations == []
    db.close()


def test_integrity_check_reports_foreign_key_violation(tmp_path):
    import sqlite3

    path = str(tmp_path / "t.db")
    db = Database(path)
    db.init()
    db.add_relationship("Alex")
    db.add_observation("R001", "x", "o", "i", "a", "self", 5.0)
    db.close()

    # Plant a violation with FK enforcement off (production always has it on,
    # so this simulates a damaged or hand-edited file).
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO observation_claims(observation_id, attribute, value, idx) "
        "VALUES ('O999', 'k', 'v', 0)"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        db.init()
        ok, detail, violations = db.integrity_check()
        assert ok is False
        assert violations
        assert detail == "ok"  # b-tree fine; the violation is in the FK check
    finally:
        db.close()


# ---------------------------------------------------------------------------
# observation timestamps (architecture phase 3, E2)
# ---------------------------------------------------------------------------


def test_add_observation_preserves_explicit_timestamp(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.add_observation(
        rid,
        "x",
        "o",
        "i",
        "a",
        "self",
        5.0,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    obs = db.get_observations(rid)
    assert obs[0].timestamp == "2026-01-01T00:00:00+00:00"
    db.close()


def test_import_observations_preserves_source_timestamps(tmp_path):
    from love_risk_engine.core.chat_import import ChatMessage, to_observations

    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    messages = [
        ChatMessage("2026-01-01T10:00:00+00:00", "A", "hi"),
        ChatMessage("2026-01-02T10:00:00+00:00", "B", "yo"),
    ]
    db.import_observations(rid, to_observations(messages, [], rid))
    rows = db.get_observations(rid)
    assert [r.timestamp for r in rows] == [
        "2026-01-01T10:00:00+00:00",
        "2026-01-02T10:00:00+00:00",
    ]
    db.close()


def test_import_observations_falls_back_to_now_for_missing_timestamp(tmp_path):
    from love_risk_engine.core.chat_import import ChatMessage, to_observations

    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    db.import_observations(
        rid, to_observations([ChatMessage("", "A", "no timestamp")], [], rid)
    )
    rows = db.get_observations(rid)
    assert rows[0].timestamp  # fallback to insertion time, never empty
    db.close()
