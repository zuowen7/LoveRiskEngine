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


def _insert_relationship(
    conn: sqlite3.Connection, relationship_id: str, alias: str
) -> None:
    conn.execute(
        "INSERT INTO relationships(id, alias, status, created_at) VALUES (?,?,?,?)",
        (relationship_id, alias, "ACTIVE", "2026-01-01T00:00:00+00:00"),
    )


def test_nested_success_cannot_commit_before_outer_failure(db):
    """Regression: an inner success used to commit the whole connection."""
    with pytest.raises(RuntimeError, match="outer failed"), db.transaction() as outer:
        _insert_relationship(outer, "R901", "Outer")
        with db.transaction() as inner:
            _insert_relationship(inner, "R902", "Inner")
        raise RuntimeError("outer failed")

    assert db.list_relationships() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_nested_success_commits_with_outer_success(db):
    with db.transaction() as outer:
        _insert_relationship(outer, "R901", "Outer")
        with db.transaction() as inner:
            _insert_relationship(inner, "R902", "Inner")

    assert [item.id for item in db.list_relationships()] == ["R901", "R902"]
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_propagated_inner_failure_rolls_back_complete_outer_unit(db):
    with pytest.raises(RuntimeError, match="inner failed"), db.transaction() as outer:
        _insert_relationship(outer, "R901", "Outer")
        with db.transaction() as inner:
            _insert_relationship(inner, "R902", "Inner")
            raise RuntimeError("inner failed")

    assert db.list_relationships() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_caught_inner_failure_rolls_back_only_its_savepoint(db):
    with db.transaction() as outer:
        _insert_relationship(outer, "R901", "Outer before")
        with (
            pytest.raises(RuntimeError, match="inner failed"),
            db.transaction() as inner,
        ):
            _insert_relationship(inner, "R902", "Inner")
            raise RuntimeError("inner failed")
        _insert_relationship(outer, "R903", "Outer after")

    assert [item.id for item in db.list_relationships()] == ["R901", "R903"]
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_sibling_nested_scope_can_succeed_after_caught_inner_failure(db):
    with db.transaction() as outer:
        _insert_relationship(outer, "R901", "Outer")
        with (
            pytest.raises(RuntimeError, match="first inner failed"),
            db.transaction() as failed_inner,
        ):
            _insert_relationship(failed_inner, "R902", "Failed inner")
            raise RuntimeError("first inner failed")
        with db.transaction() as successful_inner:
            _insert_relationship(successful_inner, "R903", "Successful inner")

    assert [item.id for item in db.list_relationships()] == ["R901", "R903"]
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_three_level_failure_isolated_to_its_savepoint(db):
    with db.transaction() as outer:
        _insert_relationship(outer, "R901", "Outer before")
        with (
            pytest.raises(RuntimeError, match="middle failed"),
            db.transaction() as middle,
        ):
            _insert_relationship(middle, "R902", "Middle")
            with db.transaction() as inner:
                _insert_relationship(inner, "R903", "Inner")
            raise RuntimeError("middle failed")
        _insert_relationship(outer, "R904", "Outer after")

    assert [item.id for item in db.list_relationships()] == ["R901", "R904"]
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_base_exception_rolls_back_and_restores_transaction_state(db):
    class AbortTransaction(BaseException):
        pass

    with pytest.raises(AbortTransaction), db.transaction() as conn:
        _insert_relationship(conn, "R901", "Interrupted")
        raise AbortTransaction

    assert db.list_relationships() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_commit_failure_rolls_back_and_restores_transaction_state(db):
    db._db.executescript(
        """
        CREATE TABLE tx_parent (id INTEGER PRIMARY KEY);
        CREATE TABLE tx_child (
            parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES tx_parent(id)
                DEFERRABLE INITIALLY DEFERRED
        );
        """
    )

    with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
        conn.execute("INSERT INTO tx_child(parent_id) VALUES (?)", (999,))

    assert db._db.execute("SELECT * FROM tx_child").fetchall() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_commit_failure_after_nested_success_rolls_back_every_scope(db):
    db._db.executescript(
        """
        CREATE TABLE nested_tx_parent (id INTEGER PRIMARY KEY);
        CREATE TABLE nested_tx_child (
            parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES nested_tx_parent(id)
                DEFERRABLE INITIALLY DEFERRED
        );
        """
    )

    with (
        pytest.raises(sqlite3.IntegrityError),
        db.transaction(),
        db.transaction() as inner,
    ):
        inner.execute("INSERT INTO nested_tx_child(parent_id) VALUES (?)", (999,))

    assert db._db.execute("SELECT * FROM nested_tx_child").fetchall() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_transaction_rejects_an_unmanaged_existing_transaction(db):
    db._db.execute("BEGIN")
    _insert_relationship(db._db, "R901", "Unmanaged")

    with (
        pytest.raises(RuntimeError, match="already has an active transaction"),
        db.transaction(),
    ):
        pass

    assert db._tx_depth == 0
    assert db._db.in_transaction
    assert [item.id for item in db.list_relationships()] == ["R901"]

    db._db.rollback()
    assert db.list_relationships() == []


def test_broken_nested_boundary_poisoning_fails_closed(db):
    """Even forbidden raw rollback cannot let later nested work commit."""
    with (
        pytest.raises(RuntimeError, match="Managed transaction boundary was lost"),
        db.transaction() as outer,
    ):
        _insert_relationship(outer, "R901", "Outer before")

        with (
            pytest.raises(sqlite3.OperationalError, match="no such savepoint"),
            db.transaction() as inner,
        ):
            _insert_relationship(inner, "R902", "Inner")
            inner.rollback()

        with pytest.raises(RuntimeError, match="no longer usable"), db.transaction():
            pass

        _insert_relationship(outer, "R903", "Outer after")

    assert db.list_relationships() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_savepoint_creation_failure_poisons_outer_scope(db):
    def deny_savepoints(
        action: int,
        _arg1: str | None,
        _arg2: str | None,
        _database: str | None,
        _trigger: str | None,
    ) -> int:
        return (
            sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_SAVEPOINT
            else sqlite3.SQLITE_OK
        )

    with (
        pytest.raises(RuntimeError, match="Managed transaction boundary was lost"),
        db.transaction() as outer,
    ):
        _insert_relationship(outer, "R901", "Outer")
        outer.set_authorizer(deny_savepoints)
        try:
            with (
                pytest.raises(sqlite3.DatabaseError, match="not authorized"),
                db.transaction(),
            ):
                pass
        finally:
            outer.set_authorizer(None)

    assert db.list_relationships() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_savepoint_cleanup_failure_poisons_outer_scope(db):
    with (
        pytest.raises(RuntimeError, match="Managed transaction boundary was lost"),
        db.transaction() as outer,
    ):
        _insert_relationship(outer, "R901", "Outer before")

        with (
            pytest.raises(sqlite3.OperationalError, match="no such savepoint"),
            db.transaction() as inner,
        ):
            _insert_relationship(inner, "R902", "Inner")
            inner.rollback()
            raise RuntimeError("body failed after raw rollback")

        _insert_relationship(outer, "R903", "Outer after")

    assert db.list_relationships() == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


def test_nested_storage_method_cannot_commit_callers_outer_transaction(db):
    rid = db.add_relationship("Alex")

    with pytest.raises(RuntimeError, match="outer failed"), db.transaction():
        db.import_observations(rid, _observations(rid, 2))
        raise RuntimeError("outer failed")

    assert db.get_observations(rid) == []
    assert db._tx_depth == 0
    assert not db._db.in_transaction


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
