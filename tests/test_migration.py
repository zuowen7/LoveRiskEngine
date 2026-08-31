"""Schema-versioning tests.

`_migrate()` used to run on every `init()` — i.e. on every CLI invocation —
re-scanning `PRAGMA table_info` and firing speculative `ALTER TABLE`s to
rediscover that nothing needed doing. It is now gated on `PRAGMA user_version`.
These tests pin both halves of that contract: an up-to-date database must skip
the work entirely, and a genuinely old database must still be upgraded.
"""

import sqlite3

from love_risk_engine.storage.database import Database
from love_risk_engine.storage.schema import SCHEMA_VERSION

# The v0.1 shape as originally shipped: no signal_type on observations, and
# inconsistencies without kind/attribute/value_a/value_b/obs_a/obs_b/resolution.
LEGACY_SCHEMA = """
CREATE TABLE relationships (
    id TEXT PRIMARY KEY, alias TEXT NOT NULL,
    status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE observations (
    id TEXT PRIMARY KEY, relationship_id TEXT NOT NULL, timestamp TEXT NOT NULL,
    category TEXT NOT NULL, observation TEXT NOT NULL,
    interpretation TEXT NOT NULL DEFAULT '',
    alternative_explanation TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'self', confidence REAL NOT NULL DEFAULT 5.0,
    rationalization INTEGER NOT NULL DEFAULT 0,
    inconsistency_flag INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE inconsistencies (
    id TEXT PRIMARY KEY, relationship_id TEXT NOT NULL,
    description TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def _columns(path, table):
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    finally:
        conn.close()


def _version(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def test_fresh_database_is_stamped_with_current_version(tmp_path):
    path = str(tmp_path / "fresh.db")
    db = Database(path)
    try:
        db.init()
    finally:
        db.close()
    assert _version(path) == SCHEMA_VERSION


def test_legacy_database_gains_new_columns(tmp_path):
    """A pre-versioning database must be upgraded in place, data intact."""
    path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO relationships VALUES "
        "('R001','Alex','ACTIVE','2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO inconsistencies VALUES ('I001','R001','old row',0,"
        "'2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()
    assert _version(path) == 0
    assert "signal_type" not in _columns(path, "observations")

    db = Database(path)
    try:
        db.init()
        # pre-existing data survives and reads back through the domain mapper
        rel = db.get_relationship("R001")
        assert rel is not None
        assert rel.alias == "Alex"
        items = db.list_inconsistencies("R001", resolved=False)
        assert [i.id for i in items] == ["I001"]
        assert items[0].kind == "manual"  # column default back-filled
        assert items[0].resolution is None
    finally:
        db.close()

    assert _version(path) == SCHEMA_VERSION
    assert "signal_type" in _columns(path, "observations")
    assert {"kind", "attribute", "resolution", "resolution_note"} <= _columns(
        path, "inconsistencies"
    )
    assert "observation_claims" in {
        r[0]
        for r in sqlite3.connect(path)
        .execute("SELECT name FROM sqlite_master WHERE type='table'")
        .fetchall()
    }


def test_up_to_date_database_skips_migration(tmp_path, monkeypatch):
    """The hot path must not re-run the back-fill on an already-current DB."""
    path = str(tmp_path / "current.db")
    db = Database(path)
    try:
        db.init()
        calls = []
        monkeypatch.setattr(Database, "_migrate_v0_to_v1", lambda self: calls.append(1))
        db.init()
        db.init()
        assert calls == []
    finally:
        db.close()


def test_migration_runs_once_on_legacy_open(tmp_path):
    """Second open of an upgraded database is a no-op, not a repeat migration."""
    path = str(tmp_path / "once.db")
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.commit()
    conn.close()

    calls = []
    original = Database._migrate_v0_to_v1

    def counting(self):
        calls.append(1)
        return original(self)

    Database._migrate_v0_to_v1 = counting
    try:
        for _ in range(3):
            db = Database(path)
            try:
                db.init()
            finally:
                db.close()
    finally:
        Database._migrate_v0_to_v1 = original
    assert calls == [1]
