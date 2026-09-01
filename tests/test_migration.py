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
        assert rel.kind == "LOVER"  # column default back-filled
        items = db.list_inconsistencies("R001", resolved=False)
        assert [i.id for i in items] == ["I001"]
        assert items[0].kind == "manual"  # column default back-filled
        assert items[0].resolution is None
    finally:
        db.close()

    assert _version(path) == SCHEMA_VERSION
    assert "signal_type" in _columns(path, "observations")
    assert "kind" in _columns(path, "relationships")
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


def test_v1_database_gains_relationship_kind(tmp_path):
    """A database stamped v1 (no relationships.kind) upgrades to v2.

    The v1→v2 step must not depend on the v0→v1 back-fill: a database stamped
    v1 skips the v0 work entirely, so this test pins the v1→v2 path on its own.
    """
    path = str(tmp_path / "v1.db")
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute("PRAGMA user_version = 1")
    conn.execute(
        "INSERT INTO relationships VALUES ('R001','Sam','ACTIVE','2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()
    assert "kind" not in _columns(path, "relationships")

    db = Database(path)
    try:
        db.init()
        rel = db.get_relationship("R001")
        assert rel is not None
        assert rel.kind == "LOVER"
    finally:
        db.close()

    assert _version(path) == SCHEMA_VERSION
    assert "kind" in _columns(path, "relationships")


def test_v2_database_gains_history_tables(tmp_path):
    """A database stamped v2 (no history tables) upgrades to v3.

    The v2→v3 step only creates the history tables — it must not depend on
    earlier back-fills, so this test stamps v2 and pins the v2→v3 path alone.
    """
    path = str(tmp_path / "v2.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE relationships ("
        "id TEXT PRIMARY KEY, alias TEXT NOT NULL, status TEXT NOT NULL, "
        "created_at TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'LOVER');"
    )
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        db.init()
    finally:
        db.close()

    assert _version(path) == SCHEMA_VERSION
    tables = {
        r[0]
        for r in sqlite3.connect(path)
        .execute("SELECT name FROM sqlite_master WHERE type='table'")
        .fetchall()
    }
    assert {"state_history", "exposure_history"} <= tables


def test_v3_database_gains_verification_items(tmp_path):
    """A database stamped v3 (no verification_items) upgrades to v4."""
    path = str(tmp_path / "v3.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE relationships ("
        "id TEXT PRIMARY KEY, alias TEXT NOT NULL, status TEXT NOT NULL, "
        "created_at TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'LOVER');"
    )
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        db.init()
    finally:
        db.close()

    assert _version(path) == SCHEMA_VERSION
    tables = {
        r[0]
        for r in sqlite3.connect(path)
        .execute("SELECT name FROM sqlite_master WHERE type='table'")
        .fetchall()
    }
    assert "verification_items" in tables


def test_v4_database_gains_review_outcomes(tmp_path):
    """A database stamped v4 (no review_outcomes) upgrades to v5."""
    path = str(tmp_path / "v4.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE relationships ("
        "id TEXT PRIMARY KEY, alias TEXT NOT NULL, status TEXT NOT NULL, "
        "created_at TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'LOVER');"
    )
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        db.init()
    finally:
        db.close()

    assert _version(path) == SCHEMA_VERSION
    tables = {
        r[0]
        for r in sqlite3.connect(path)
        .execute("SELECT name FROM sqlite_master WHERE type='table'")
        .fetchall()
    }
    assert "review_outcomes" in tables


def test_v5_database_gains_structured_judgment_columns_with_data_preserved(
    tmp_path,
):
    """A v5 observation survives the v5→v6 column migration unchanged."""
    path = str(tmp_path / "v5.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE relationships (
            id TEXT PRIMARY KEY, alias TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'LOVER'
        );
        CREATE TABLE observations (
            id TEXT PRIMARY KEY, relationship_id TEXT NOT NULL,
            timestamp TEXT NOT NULL, category TEXT NOT NULL,
            observation TEXT NOT NULL, interpretation TEXT NOT NULL DEFAULT '',
            alternative_explanation TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'self',
            confidence REAL NOT NULL DEFAULT 5.0,
            rationalization INTEGER NOT NULL DEFAULT 0,
            inconsistency_flag INTEGER NOT NULL DEFAULT 0,
            signal_type TEXT NOT NULL DEFAULT 'UNSPECIFIED'
        );
        """
    )
    conn.execute("PRAGMA user_version = 5")
    conn.execute(
        "INSERT INTO relationships VALUES "
        "('R001','Alex','ACTIVE','2026-01-01T00:00:00+00:00','LOVER')"
    )
    conn.execute(
        "INSERT INTO observations VALUES "
        "('O001','R001','2026-01-02T00:00:00+00:00','general','fact',"
        "'reading','alternative','self',4.0,0,0,'CHEAP')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        db.init()
        observation = db.get_observations("R001")[0]
        assert observation.observation == "fact"
        assert observation.interpretation == "reading"
        assert observation.criterion_key == ""
        assert observation.judgment_direction.value == "UNSPECIFIED"
    finally:
        db.close()

    assert _version(path) == SCHEMA_VERSION
    assert {"criterion_key", "judgment_direction"} <= _columns(path, "observations")


def test_fresh_and_v5_schema_paths_both_define_structured_judgment_columns(
    tmp_path,
):
    """Meta-guard: canonical DDL and v5 migration are independently required."""
    fresh_path = str(tmp_path / "fresh-contract.db")
    fresh = Database(fresh_path)
    try:
        fresh.init()
    finally:
        fresh.close()

    assert {"criterion_key", "judgment_direction"} <= _columns(
        fresh_path, "observations"
    )
    # The dedicated v5 test above exercises the independent upgrade path. This
    # assertion pins the current version so deleting that migration cannot be
    # hidden by leaving the fresh DDL intact.
    assert SCHEMA_VERSION == 6
