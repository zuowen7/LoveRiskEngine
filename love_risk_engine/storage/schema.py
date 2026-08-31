"""SQLite schema for LoveRiskEngine v0.1.

Default local database, no external services. Only the minimal PII the user
chooses to enter is stored (alias + free-text notes). No phone / ID / address
fields are ever created.

Schema versioning
-----------------
`SCHEMA_VERSION` is the version that the DDL below declares, and it is stamped
into the database via `PRAGMA user_version`. `Database._migrate()` compares the
two and does nothing when they match, so the common case costs a single integer
read instead of re-scanning `PRAGMA table_info` on every CLI invocation.

To add a column: extend the DDL below, bump `SCHEMA_VERSION`, and add a
matching `_migrate_vN_to_vN1` step in `storage/database.py`. Never renumber an
existing version — databases in the wild are already stamped with it.
"""

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS relationships (
    id          TEXT PRIMARY KEY,
    alias       TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    id                      TEXT PRIMARY KEY,
    relationship_id         TEXT NOT NULL,
    timestamp               TEXT NOT NULL,
    category                TEXT NOT NULL,
    observation             TEXT NOT NULL,
    interpretation          TEXT NOT NULL DEFAULT '',
    alternative_explanation TEXT NOT NULL DEFAULT '',
    source                  TEXT NOT NULL DEFAULT 'self',
    confidence              REAL NOT NULL DEFAULT 5.0,
    rationalization         INTEGER NOT NULL DEFAULT 0,
    inconsistency_flag      INTEGER NOT NULL DEFAULT 0,
    signal_type             TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS relationship_state (
    relationship_id  TEXT PRIMARY KEY,
    attraction      REAL NOT NULL DEFAULT 0.0,
    trust           REAL NOT NULL DEFAULT 0.0,
    uncertainty     REAL NOT NULL DEFAULT 0.0,
    emotional_state TEXT NOT NULL DEFAULT 'NEUTRAL',
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS exposure (
    relationship_id TEXT PRIMARY KEY,
    time            REAL NOT NULL DEFAULT 0.0,
    emotional       REAL NOT NULL DEFAULT 0.0,
    privacy         REAL NOT NULL DEFAULT 0.0,
    financial       REAL NOT NULL DEFAULT 0.0,
    life_decision   REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS boundaries (
    id               TEXT PRIMARY KEY,
    description      TEXT NOT NULL,
    severity         TEXT NOT NULL DEFAULT 'HARD',
    active           INTEGER NOT NULL DEFAULT 1,
    trigger_keywords TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS boundary_hits (
    id               TEXT PRIMARY KEY,
    boundary_id      TEXT NOT NULL,
    relationship_id  TEXT NOT NULL,
    evidence         TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    FOREIGN KEY (boundary_id) REFERENCES boundaries(id),
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS inconsistencies (
    id              TEXT PRIMARY KEY,
    relationship_id TEXT NOT NULL,
    description     TEXT NOT NULL,
    resolved        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'manual',
    attribute       TEXT,
    value_a         TEXT,
    value_b         TEXT,
    obs_a           TEXT,
    obs_b           TEXT,
    resolution      TEXT,
    resolution_note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS observation_claims (
    observation_id TEXT NOT NULL,
    attribute      TEXT NOT NULL,
    value          TEXT NOT NULL,
    idx            INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (observation_id) REFERENCES observations(id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id                        TEXT PRIMARY KEY,
    relationship_id           TEXT NOT NULL,
    timestamp                 TEXT NOT NULL,
    triggered_hooks           TEXT NOT NULL DEFAULT '[]',
    unresolved_inconsistencies INTEGER NOT NULL DEFAULT 0,
    recommendation            TEXT NOT NULL,
    notes                     TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS cooldowns (
    id              TEXT PRIMARY KEY,
    relationship_id TEXT NOT NULL,
    decision        TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    started_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS override_log (
    id              TEXT PRIMARY KEY,
    relationship_id TEXT NOT NULL,
    cooldown_id     TEXT,
    reason          TEXT NOT NULL DEFAULT '',
    timestamp       TEXT NOT NULL,
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);
"""
