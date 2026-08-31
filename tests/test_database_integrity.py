"""Regression tests for the storage-layer hardening.

Each test here locks in a defect that was found during the quality audit, so
it cannot silently come back.
"""

import sqlite3

import pytest
from love_risk_engine.core.observation import Observation
from love_risk_engine.storage.database import Database, _next_id


@pytest.fixture
def db(tmp_path):
    """One initialised database per test, always closed afterwards."""
    database = Database(str(tmp_path / "t.db"))
    database.init()
    yield database
    database.close()


def _observations(relationship_id: str, count: int) -> list:
    """Build `count` plain observations for the given relationship."""
    return [
        Observation(
            id=f"O{i:03d}",
            relationship_id=relationship_id,
            timestamp="2026-08-30T10:00:00+00:00",
            category="chat",
            observation=f"message {i}",
            interpretation="",
            alternative_explanation="",
            source="chat",
            confidence=5.0,
        )
        for i in range(1, count + 1)
    ]


def test_id_generation_refuses_unknown_tables(db):
    """SQL identifiers cannot be bound, so they are allow-listed."""
    with pytest.raises(ValueError, match="refusing to build an id"):
        _next_id(db, "X", "sqlite_master", "name")


def test_id_generation_allows_known_tables(db):
    rid = db.add_relationship("Alex")
    assert rid == "R001"


def test_using_a_database_before_connect_raises_clearly(tmp_path):
    """Previously this surfaced as an AttributeError on None."""
    database = Database(str(tmp_path / "t.db"))
    with pytest.raises(RuntimeError, match="not connected"):
        database.list_relationships()


def test_transaction_commits_on_success(db):
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO relationships(id, alias, status, created_at) VALUES (?,?,?,?)",
            ("R999", "Committed", "ACTIVE", "2026-01-01T00:00:00+00:00"),
        )
    assert len(db.list_relationships()) == 1


def test_transaction_rolls_back_on_failure(db):
    with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
        conn.execute(
            "INSERT INTO relationships(id, alias, status, created_at) VALUES (?,?,?,?)",
            ("R001", "First", "ACTIVE", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO relationships(id, alias, status, created_at) VALUES (?,?,?,?)",
            ("R001", "Duplicate id", "ACTIVE", "2026-01-01T00:00:00+00:00"),
        )
    assert db.list_relationships() == []


def test_bulk_import_is_all_or_nothing(db, monkeypatch):
    """A failure part-way through must not leave a half-applied import.

    This also guards the subtle part: `add_observation` commits internally, so
    unless the outer transaction suppresses those commits there is nothing
    left for the rollback to undo and the first row survives.
    """
    rid = db.add_relationship("Alex")
    original = db.add_observation
    calls = {"n": 0}

    def fails_on_second(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("import blew up on row 2")
        return original(*args, **kwargs)

    monkeypatch.setattr(db, "add_observation", fails_on_second)

    with pytest.raises(RuntimeError, match="blew up on row 2"):
        db.import_observations(rid, _observations(rid, 3))

    assert db.get_observations(rid) == []


def test_bulk_import_persists_every_row_on_success(db):
    rid = db.add_relationship("Alex")
    assert db.import_observations(rid, _observations(rid, 5)) == 5
    assert len(db.get_observations(rid)) == 5
