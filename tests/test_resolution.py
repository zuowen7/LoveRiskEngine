from love_risk_engine.storage.database import Database


def _setup(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    # three detected-style inconsistencies to resolve differently
    i1 = db.add_inconsistency(rid, "job barista vs engineer")
    i2 = db.add_inconsistency(rid, "relationship_status single vs married")
    i3 = db.add_inconsistency(rid, "city Berlin vs Paris")
    return db, rid, [i1, i2, i3]


def test_resolve_default_is_sequential_change(tmp_path):
    db, rid, ids = _setup(tmp_path)
    assert db.resolve_inconsistency(ids[0])
    items = db.list_inconsistencies(rid, resolved=True)
    assert len(items) == 1
    assert items[0]["resolution"] == "sequential_change"
    assert items[0]["resolved"] == 1
    db.close()


def test_resolve_with_note_and_type(tmp_path):
    db, rid, ids = _setup(tmp_path)
    db.resolve_inconsistency(ids[1], resolution="genuine_inconsistency", note="red flag")
    items = db.list_inconsistencies(rid, resolved=True)
    assert items[0]["resolution"] == "genuine_inconsistency"
    assert items[0]["resolution_note"] == "red flag"
    db.close()


def test_resolved_removed_from_open_count(tmp_path):
    db, rid, ids = _setup(tmp_path)
    db.resolve_inconsistency(ids[0], "sequential_change")
    open_items = db.list_inconsistencies(rid, resolved=False)
    assert len(open_items) == 2  # two still open
    db.close()


def test_acknowledged_lists_all_resolved(tmp_path):
    db, rid, ids = _setup(tmp_path)
    db.resolve_inconsistency(ids[0], "sequential_change")
    db.resolve_inconsistency(ids[1], "genuine_inconsistency", "noted")
    db.resolve_inconsistency(ids[2], "dismissed")
    ack = db.acknowledged_inconsistencies(rid)
    assert len(ack) == 3
    resolutions = {row["resolution"] for row in ack}
    assert resolutions == {"sequential_change", "genuine_inconsistency", "dismissed"}
    db.close()


def test_resolve_unknown_id_returns_false(tmp_path):
    db, rid, ids = _setup(tmp_path)
    assert db.resolve_inconsistency("I999") is False
    db.close()
