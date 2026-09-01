"""SQLite-backed storage for LoveRiskEngine.

Pure stdlib (sqlite3). IDs are readable sequential tokens (R001, O001, B001,
...) for easy CLI use.

Every query returns a **domain object**, never a raw `sqlite3.Row`:
  - observations, relationship state, exposure, boundaries, boundary hits,
    relationships, inconsistencies, reviews, cooldowns, overrides.

Callers use attribute access (`row.id`), which is why the SIM118 exemption
for `sqlite3.Row` no longer applies anywhere — there are no rows left.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ..core.boundaries import Boundary, BoundaryHit
from ..core.cooldown import Cooldown
from ..core.exposure import Exposure
from ..core.history import ExposureChange, StateChange
from ..core.inconsistency import Inconsistency
from ..core.observation import Claim, Observation
from ..core.override import OverrideLog
from ..core.relationship import Kind, Relationship
from ..core.review import Review
from ..core.signals import SignalType
from ..core.state import EmotionalState, RelationshipState
from ..core.verification import VerificationItem, VerificationStatus
from .schema import SCHEMA, SCHEMA_VERSION, TABLE_ORDER

# SQL identifiers can never be bound as parameters, so we allow-list them.
# Adding a table/column to this set is a deliberate, reviewable act.
_ALLOWED_IDENTIFIERS = {
    ("relationships", "id"),
    ("observations", "id"),
    ("boundaries", "id"),
    ("boundary_hits", "id"),
    ("inconsistencies", "id"),
    ("cooldowns", "id"),
    ("override_log", "id"),
    ("state_history", "id"),
    ("exposure_history", "id"),
    ("verification_items", "id"),
}

_VALID_KINDS = frozenset(k.value for k in Kind)

_VALID_VERIFICATION_STATUSES = frozenset(s.value for s in VerificationStatus)


def _validate_kind(kind: str) -> None:
    """Allow-list relationship kinds before they reach the database.

    `kind` is stored as TEXT; anything outside the enum is rejected at write
    time so no garbage can enter through the CLI (same rationale as
    `_ALLOWED_IDENTIFIERS`).
    """
    if kind not in _VALID_KINDS:
        raise ValueError(f"unknown relationship kind: {kind!r}")


def _validate_verification_status(status: str) -> None:
    """Allow-list verification statuses before they reach the database."""
    if status not in _VALID_VERIFICATION_STATUSES:
        raise ValueError(f"unknown verification status: {status!r}")


def _now() -> str:
    """UTC ISO-8601 with an explicit offset.

    Naive local time made timeline ordering ambiguous across DST and
    timezones. UTC keeps every stored timestamp directly comparable.
    """
    return datetime.now(UTC).isoformat(timespec="seconds")


def _next_id(db: Database, prefix: str, table: str, column: str) -> str:
    if (table, column) not in _ALLOWED_IDENTIFIERS:
        raise ValueError(f"refusing to build an id from {table}.{column}")
    # Identifiers cannot be parameterised in SQL, so they are allow-listed
    # above. Every value that reaches the query is still bound as a parameter.
    cur = db._db.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ?",  # noqa: S608
        (prefix + "%",),
    )
    nums: list[int] = []
    for (val,) in cur.fetchall():
        with contextlib.suppress(ValueError):
            nums.append(int(str(val)[len(prefix) :]))
    n = (max(nums) + 1) if nums else 1
    token = f"{prefix}{n:03d}"
    # `id` is the PRIMARY KEY, so a duplicate insert would raise IntegrityError.
    # That is enough under the single-user CLI model, but we also defend here:
    # if the candidate already exists (e.g. a recycled id, or a concurrent
    # writer), walk forward to the next free token instead of failing.
    while db._db.execute(
        f"SELECT 1 FROM {table} WHERE {column}=?",  # noqa: S608
        (token,),
    ).fetchone():
        n += 1
        token = f"{prefix}{n:03d}"
    return token


class Database:
    def __init__(self, path: str = "love_risk.db") -> None:
        self.path = path
        self.conn: sqlite3.Connection | None = None
        self._tx_depth = 0

    @property
    def _db(self) -> sqlite3.Connection:
        """Non-optional accessor for the live connection.

        Preferred over scattering `# type: ignore[union-attr]`: the Optional is
        resolved once, here, and misuse raises instead of silently passing.
        """
        if self.conn is None:
            raise RuntimeError(
                "Database is not connected. Call connect() or use `with Database(...)`."
            )
        return self.conn

    def _commit(self) -> None:
        """Commit, unless an outer `transaction()` owns the boundary.

        Write methods must call this instead of `conn.commit()` directly.
        Without it, a helper that commits internally would silently destroy the
        atomicity of any transaction wrapping it — the outer rollback would
        have nothing left to undo.
        """
        if self._tx_depth:
            return
        self._db.commit()

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Group writes into one atomic unit: all-or-nothing, and faster.

        Without this, a bulk import that fails halfway leaves partial data
        behind and pays a commit (fsync) per row. Nesting is supported: only
        the outermost block commits, and any failure rolls back the lot.
        """
        conn = self._db
        self._tx_depth += 1
        try:
            yield conn
        except Exception:
            self._tx_depth -= 1
            conn.rollback()
            raise
        else:
            self._tx_depth -= 1
            conn.commit()

    # --- lifecycle ---
    def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def init(self) -> None:
        if self.conn is None:
            self.connect()
        self._db.executescript(SCHEMA)
        self._migrate()
        self._commit()

    # --- schema versioning ---
    def _user_version(self) -> int:
        row = self._db.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0

    def _set_user_version(self, version: int) -> None:
        # PRAGMA does not accept bound parameters. `version` is an int constant
        # owned by this package and is coerced with int(), never user input.
        self._db.execute(f"PRAGMA user_version = {int(version)}")

    def _migrate(self) -> None:
        """Bring an existing database up to `SCHEMA_VERSION`.

        The version lives in `PRAGMA user_version`. An up-to-date database
        returns after one integer read; previously every `init()` — i.e. every
        single CLI invocation — re-ran three `PRAGMA table_info` scans and a
        batch of speculative `ALTER TABLE` statements to rediscover that there
        was nothing to do.
        """
        version = self._user_version()
        if version >= SCHEMA_VERSION:
            return
        if version == 0:
            # Either a database just created from the DDL above (which already
            # declares every column) or one written before versioning existed.
            # The back-fill is idempotent and covers both; it runs exactly once.
            self._migrate_v0_to_v1()
        if version < 2:
            self._migrate_v1_to_v2()
        if version < 3:
            self._migrate_v2_to_v3()
        if version < 4:
            self._migrate_v3_to_v4()
        self._set_user_version(SCHEMA_VERSION)

    def _migrate_v0_to_v1(self) -> None:
        """Back-fill columns added after the original v0.1 schema shipped."""
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS observation_claims ("
            "observation_id TEXT NOT NULL, attribute TEXT NOT NULL, "
            "value TEXT NOT NULL, idx INTEGER NOT NULL DEFAULT 0, "
            "FOREIGN KEY (observation_id) REFERENCES observations(id))"
        )
        cols = {
            r[1]
            for r in self._db.execute("PRAGMA table_info(inconsistencies)").fetchall()
        }
        new_cols = {
            "kind": "TEXT NOT NULL DEFAULT 'manual'",
            "attribute": "TEXT",
            "value_a": "TEXT",
            "value_b": "TEXT",
            "obs_a": "TEXT",
            "obs_b": "TEXT",
        }
        for col, ddl in new_cols.items():
            if col not in cols:
                self._db.execute(f"ALTER TABLE inconsistencies ADD COLUMN {col} {ddl}")
        # signal_type on observations (v0.2 costly-signal classification)
        obs_cols = {
            r[1] for r in self._db.execute("PRAGMA table_info(observations)").fetchall()
        }
        if "signal_type" not in obs_cols:
            self._db.execute(
                "ALTER TABLE observations ADD COLUMN signal_type "
                "TEXT NOT NULL DEFAULT 'UNSPECIFIED'"
            )
        # resolution tracking on inconsistencies (v0.2 contradiction UX)
        inc_cols = {
            r[1]
            for r in self._db.execute("PRAGMA table_info(inconsistencies)").fetchall()
        }
        for col, ddl in {
            "resolution": "TEXT",
            "resolution_note": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if col not in inc_cols:
                self._db.execute(f"ALTER TABLE inconsistencies ADD COLUMN {col} {ddl}")

    def _migrate_v1_to_v2(self) -> None:
        """Add `relationships.kind` (relationship-kinds proposal, S1).

        Existing rows back-fill to 'LOVER', which equals today's behavior
        exactly. Runs for databases stamped v1, and for fresh v0 ones right
        after the v0→v1 back-fill; both paths are idempotent.
        """
        cols = {
            r[1]
            for r in self._db.execute("PRAGMA table_info(relationships)").fetchall()
        }
        if "kind" not in cols:
            self._db.execute(
                "ALTER TABLE relationships ADD COLUMN kind "
                "TEXT NOT NULL DEFAULT 'LOVER'"
            )

    def _migrate_v2_to_v3(self) -> None:
        """Create the state/exposure history tables (roadmap item #1).

        No backfill: the upsert-based past left no trace, so history starts at
        the first change after this migration — stated honestly, not hidden.
        """
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS state_history (
                id              TEXT PRIMARY KEY,
                relationship_id  TEXT NOT NULL,
                timestamp        TEXT NOT NULL,
                attraction       REAL NOT NULL,
                trust            REAL NOT NULL,
                uncertainty      REAL NOT NULL,
                emotional_state  TEXT NOT NULL,
                FOREIGN KEY (relationship_id) REFERENCES relationships(id)
            );
            CREATE TABLE IF NOT EXISTS exposure_history (
                id              TEXT PRIMARY KEY,
                relationship_id  TEXT NOT NULL,
                timestamp        TEXT NOT NULL,
                time             REAL NOT NULL,
                emotional        REAL NOT NULL,
                privacy          REAL NOT NULL,
                financial        REAL NOT NULL,
                life_decision    REAL NOT NULL,
                FOREIGN KEY (relationship_id) REFERENCES relationships(id)
            );
            """
        )

    def _migrate_v3_to_v4(self) -> None:
        """Create the verification checklist table (roadmap #3)."""
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_items (
                id              TEXT PRIMARY KEY,
                relationship_id  TEXT NOT NULL,
                item             TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'unverified',
                note             TEXT NOT NULL DEFAULT '',
                created_at       TEXT NOT NULL,
                verified_at      TEXT,
                FOREIGN KEY (relationship_id) REFERENCES relationships(id)
            )
            """
        )

    def __enter__(self) -> Database:
        self.init()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self.close()

    # --- relationships ---
    def add_relationship(
        self, alias: str, status: str = "ACTIVE", kind: str = Kind.LOVER.value
    ) -> str:
        _validate_kind(kind)
        rid = _next_id(self, "R", "relationships", "id")
        self._db.execute(
            "INSERT INTO relationships(id, alias, status, created_at, kind) "
            "VALUES (?,?,?,?,?)",
            (rid, alias, status, _now(), kind),
        )
        self._commit()
        return rid

    def set_relationship_kind(self, relationship_id: str, kind: str) -> bool:
        """Change a relationship's kind. Returns False if unknown.

        The kind is an attribute of the relationship, not a global switch —
        there is deliberately no `lre mode` command that would imply one.
        """
        _validate_kind(kind)
        cur = self._db.execute(
            "UPDATE relationships SET kind=? WHERE id=?", (kind, relationship_id)
        )
        self._commit()
        return cur.rowcount > 0

    def get_relationship(self, token: str) -> Relationship | None:
        row = self._db.execute(
            "SELECT * FROM relationships WHERE id=? OR alias=?",
            (token, token),
        ).fetchone()
        return self._row_to_relationship(row) if row else None

    def list_relationships(self) -> list[Relationship]:
        return [
            self._row_to_relationship(r)
            for r in self._db.execute(
                "SELECT * FROM relationships ORDER BY id"
            ).fetchall()
        ]

    def _row_to_relationship(self, r: sqlite3.Row) -> Relationship:
        return Relationship(
            id=r["id"],
            alias=r["alias"],
            status=r["status"],
            created_at=r["created_at"],
            kind=r["kind"],
        )

    # --- observations ---
    def add_observation(
        self,
        relationship_id: str,
        category: str,
        observation: str,
        interpretation: str,
        alternative: str,
        source: str,
        confidence: float,
        rationalization: bool = False,
        inconsistency_flag: bool = False,
        claims: list[Claim] | None = None,
        signal_type: SignalType = SignalType.UNSPECIFIED,
    ) -> str:
        oid = _next_id(self, "O", "observations", "id")
        self._db.execute(
            "INSERT INTO observations("
            "id, relationship_id, timestamp, category, observation, "
            "interpretation, alternative_explanation, source, confidence, "
            "rationalization, inconsistency_flag, signal_type) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                oid,
                relationship_id,
                _now(),
                category,
                observation,
                interpretation,
                alternative,
                source,
                float(confidence),
                int(bool(rationalization)),
                int(bool(inconsistency_flag)),
                signal_type.value,
            ),
        )
        for idx, c in enumerate(claims or []):
            self._db.execute(
                "INSERT INTO observation_claims("
                "observation_id, attribute, value, idx) VALUES (?,?,?,?)",
                (oid, c.attribute.strip(), c.value.strip(), idx),
            )
        self._commit()
        return oid

    def get_observations(self, relationship_id: str) -> list[Observation]:
        rows = self._db.execute(
            "SELECT * FROM observations WHERE relationship_id=? ORDER BY timestamp",
            (relationship_id,),
        ).fetchall()
        return [self._row_to_observation(r) for r in rows]

    def import_observations(
        self, relationship_id: str, observations: list[Observation]
    ) -> int:
        """Bulk-insert observations (e.g. from a chat import).

        Reuses add_observation so claims are persisted too. Returns the number
        of observations inserted. Never deletes or overwrites existing data.

        The whole batch runs in one transaction: a failure part-way through
        rolls back every row rather than leaving the import half-applied.
        """
        count = 0
        with self.transaction():
            for o in observations:
                self.add_observation(
                    relationship_id,
                    o.category,
                    o.observation,
                    o.interpretation,
                    o.alternative_explanation,
                    o.source,
                    o.confidence,
                    o.rationalization,
                    o.inconsistency_flag,
                    claims=o.claims,
                    signal_type=o.signal_type,
                )
                count += 1
        return count

    def _row_to_observation(self, r: sqlite3.Row) -> Observation:
        claim_rows = self._db.execute(
            "SELECT attribute, value FROM observation_claims "
            "WHERE observation_id=? ORDER BY idx",
            (r["id"],),
        ).fetchall()
        claims = [
            Claim(attribute=cr["attribute"], value=cr["value"]) for cr in claim_rows
        ]
        return Observation(
            id=r["id"],
            relationship_id=r["relationship_id"],
            timestamp=r["timestamp"],
            category=r["category"],
            observation=r["observation"],
            interpretation=r["interpretation"],
            alternative_explanation=r["alternative_explanation"],
            source=r["source"],
            confidence=r["confidence"],
            rationalization=bool(r["rationalization"]),
            inconsistency_flag=bool(r["inconsistency_flag"]),
            claims=claims,
            signal_type=SignalType(r["signal_type"]),
        )

    # --- state ---
    def upsert_state(self, state: RelationshipState) -> None:
        state.clamp()
        previous = self.get_state(state.relationship_id)
        self._db.execute(
            "INSERT INTO relationship_state("
            "relationship_id, attraction, trust, uncertainty, emotional_state) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(relationship_id) DO UPDATE SET "
            "attraction=excluded.attraction, trust=excluded.trust, "
            "uncertainty=excluded.uncertainty, "
            "emotional_state=excluded.emotional_state",
            (
                state.relationship_id,
                state.attraction,
                state.trust,
                state.uncertainty,
                state.emotional_state.value,
            ),
        )
        if previous is None or self._state_changed(previous, state):
            sid = _next_id(self, "SH", "state_history", "id")
            self._db.execute(
                "INSERT INTO state_history("
                "id, relationship_id, timestamp, attraction, trust, "
                "uncertainty, emotional_state) VALUES (?,?,?,?,?,?,?)",
                (
                    sid,
                    state.relationship_id,
                    _now(),
                    state.attraction,
                    state.trust,
                    state.uncertainty,
                    state.emotional_state.value,
                ),
            )
        self._commit()

    @staticmethod
    def _state_changed(previous: RelationshipState, current: RelationshipState) -> bool:
        return (
            previous.attraction != current.attraction
            or previous.trust != current.trust
            or previous.uncertainty != current.uncertainty
            or previous.emotional_state != current.emotional_state
        )

    def list_state_history(self, relationship_id: str) -> list[StateChange]:
        return [
            self._row_to_state_change(r)
            for r in self._db.execute(
                "SELECT * FROM state_history WHERE relationship_id=? "
                "ORDER BY timestamp, id",
                (relationship_id,),
            ).fetchall()
        ]

    def _row_to_state_change(self, r: sqlite3.Row) -> StateChange:
        return StateChange(
            id=r["id"],
            relationship_id=r["relationship_id"],
            timestamp=r["timestamp"],
            attraction=r["attraction"],
            trust=r["trust"],
            uncertainty=r["uncertainty"],
            emotional_state=r["emotional_state"],
        )

    def get_state(self, relationship_id: str) -> RelationshipState | None:
        r = self._db.execute(
            "SELECT * FROM relationship_state WHERE relationship_id=?",
            (relationship_id,),
        ).fetchone()
        if not r:
            return None
        return RelationshipState(
            relationship_id=r["relationship_id"],
            attraction=r["attraction"],
            trust=r["trust"],
            uncertainty=r["uncertainty"],
            emotional_state=EmotionalState(r["emotional_state"]),
        )

    # --- exposure ---
    def upsert_exposure(self, exposure: Exposure) -> None:
        exposure.clamp()
        previous = self.get_exposure(exposure.relationship_id)
        self._db.execute(
            "INSERT INTO exposure("
            "relationship_id, time, emotional, privacy, financial, life_decision) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(relationship_id) DO UPDATE SET "
            "time=excluded.time, emotional=excluded.emotional, "
            "privacy=excluded.privacy, financial=excluded.financial, "
            "life_decision=excluded.life_decision",
            (
                exposure.relationship_id,
                exposure.time,
                exposure.emotional,
                exposure.privacy,
                exposure.financial,
                exposure.life_decision,
            ),
        )
        if previous is None or self._exposure_changed(previous, exposure):
            eid = _next_id(self, "EH", "exposure_history", "id")
            self._db.execute(
                "INSERT INTO exposure_history("
                "id, relationship_id, timestamp, time, emotional, privacy, "
                "financial, life_decision) VALUES (?,?,?,?,?,?,?,?)",
                (
                    eid,
                    exposure.relationship_id,
                    _now(),
                    exposure.time,
                    exposure.emotional,
                    exposure.privacy,
                    exposure.financial,
                    exposure.life_decision,
                ),
            )
        self._commit()

    @staticmethod
    def _exposure_changed(previous: Exposure, current: Exposure) -> bool:
        return (
            previous.time != current.time
            or previous.emotional != current.emotional
            or previous.privacy != current.privacy
            or previous.financial != current.financial
            or previous.life_decision != current.life_decision
        )

    def list_exposure_history(self, relationship_id: str) -> list[ExposureChange]:
        return [
            self._row_to_exposure_change(r)
            for r in self._db.execute(
                "SELECT * FROM exposure_history WHERE relationship_id=? "
                "ORDER BY timestamp, id",
                (relationship_id,),
            ).fetchall()
        ]

    def _row_to_exposure_change(self, r: sqlite3.Row) -> ExposureChange:
        return ExposureChange(
            id=r["id"],
            relationship_id=r["relationship_id"],
            timestamp=r["timestamp"],
            time=r["time"],
            emotional=r["emotional"],
            privacy=r["privacy"],
            financial=r["financial"],
            life_decision=r["life_decision"],
        )

    def get_exposure(self, relationship_id: str) -> Exposure | None:
        r = self._db.execute(
            "SELECT * FROM exposure WHERE relationship_id=?",
            (relationship_id,),
        ).fetchone()
        if not r:
            return None
        return Exposure(
            relationship_id=r["relationship_id"],
            time=r["time"],
            emotional=r["emotional"],
            privacy=r["privacy"],
            financial=r["financial"],
            life_decision=r["life_decision"],
        )

    # --- boundaries ---
    def add_boundary(
        self, description: str, severity: str = "HARD", trigger_keywords: str = ""
    ) -> str:
        bid = _next_id(self, "B", "boundaries", "id")
        self._db.execute(
            "INSERT INTO boundaries(id, description, severity, active, "
            "trigger_keywords) VALUES (?,?,?,?,?)",
            (bid, description, severity, 1, trigger_keywords),
        )
        self._commit()
        return bid

    def get_boundary(self, boundary_id: str) -> Boundary | None:
        row = self._db.execute(
            "SELECT * FROM boundaries WHERE id=?", (boundary_id,)
        ).fetchone()
        return self._row_to_boundary(row) if row else None

    def list_boundaries(self, active_only: bool = False) -> list[Boundary]:
        sql = "SELECT * FROM boundaries"
        params: tuple = ()
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY id"
        return [
            self._row_to_boundary(r) for r in self._db.execute(sql, params).fetchall()
        ]

    def deactivate_boundary(self, boundary_id: str) -> bool:
        """Retire a boundary without deleting it. Returns False if unknown.

        Boundaries are retired, never dropped: `list_boundaries(active_only=False)`
        still reports them, so earlier boundary_hits stay interpretable and the
        audit trail remains intact.
        """
        cur = self._db.execute(
            "UPDATE boundaries SET active=0 WHERE id=?", (boundary_id,)
        )
        self._commit()
        return cur.rowcount > 0

    def _row_to_boundary(self, r: sqlite3.Row) -> Boundary:
        return Boundary(
            id=r["id"],
            description=r["description"],
            severity=r["severity"],
            active=bool(r["active"]),
            trigger_keywords=r["trigger_keywords"],
        )

    def _row_to_boundary_hit(self, r: sqlite3.Row) -> BoundaryHit:
        return BoundaryHit(
            id=r["id"],
            boundary_id=r["boundary_id"],
            relationship_id=r["relationship_id"],
            evidence=r["evidence"],
            timestamp=r["timestamp"],
        )

    # --- boundary hits ---
    def add_boundary_hit(
        self, boundary_id: str, relationship_id: str, evidence: str
    ) -> str:
        hid = _next_id(self, "H", "boundary_hits", "id")
        self._db.execute(
            "INSERT INTO boundary_hits("
            "id, boundary_id, relationship_id, evidence, timestamp) "
            "VALUES (?,?,?,?,?)",
            (hid, boundary_id, relationship_id, evidence, _now()),
        )
        self._commit()
        return hid

    def list_boundary_hits(
        self, relationship_id: str, only_hard: bool = False
    ) -> list[BoundaryHit]:
        sql = (
            "SELECT h.* FROM boundary_hits h "
            "JOIN boundaries b ON h.boundary_id = b.id "
            "WHERE h.relationship_id=?"
        )
        params: list = [relationship_id]
        if only_hard:
            sql += " AND b.severity='HARD'"
        return [
            self._row_to_boundary_hit(r)
            for r in self._db.execute(sql, tuple(params)).fetchall()
        ]

    # --- inconsistencies ---
    def add_inconsistency(self, relationship_id: str, description: str) -> str:
        iid = _next_id(self, "I", "inconsistencies", "id")
        self._db.execute(
            "INSERT INTO inconsistencies("
            "id, relationship_id, description, resolved, created_at) "
            "VALUES (?,?,?,?,?)",
            (iid, relationship_id, description, 0, _now()),
        )
        self._commit()
        return iid

    def resolve_inconsistency(
        self,
        inconsistency_id: str,
        resolution: str = "sequential_change",
        note: str = "",
    ) -> bool:
        """Mark an inconsistency resolved with a resolution type and note.

        resolution is one of:
          'sequential_change'     — values changed over time (not a lie)
          'genuine_inconsistency' — real contradiction, acknowledged as a flag
          'dismissed'             — reviewed, not a real conflict
        All three close the item; the type is kept for audit.
        """
        cur = self._db.execute(
            "UPDATE inconsistencies SET resolved=1, resolution=?, resolution_note=? "
            "WHERE id=?",
            (resolution, note, inconsistency_id),
        )
        self._commit()
        return cur.rowcount > 0

    def list_inconsistencies(
        self, relationship_id: str, resolved: bool = False
    ) -> list[Inconsistency]:
        return [
            self._row_to_inconsistency(r)
            for r in self._db.execute(
                "SELECT * FROM inconsistencies "
                "WHERE relationship_id=? AND resolved=? ORDER BY id",
                (relationship_id, 1 if resolved else 0),
            ).fetchall()
        ]

    def acknowledged_inconsistencies(self, relationship_id: str) -> list[Inconsistency]:
        """Resolved items kept as audit / 'acknowledged yellow flags'.

        All resolved items are returned; callers distinguish by `resolution`.
        """
        return [
            self._row_to_inconsistency(r)
            for r in self._db.execute(
                "SELECT * FROM inconsistencies "
                "WHERE relationship_id=? AND resolved=1 ORDER BY id",
                (relationship_id,),
            ).fetchall()
        ]

    def _row_to_inconsistency(self, r: sqlite3.Row) -> Inconsistency:
        return Inconsistency(
            id=r["id"],
            relationship_id=r["relationship_id"],
            description=r["description"],
            resolved=bool(r["resolved"]),
            created_at=r["created_at"],
            kind=r["kind"],
            attribute=r["attribute"],
            value_a=r["value_a"],
            value_b=r["value_b"],
            obs_a=r["obs_a"],
            obs_b=r["obs_b"],
            resolution=r["resolution"],
            resolution_note=r["resolution_note"],
        )

    # --- contradictions (auto-detected inconsistencies) ---
    def find_contradiction(
        self, relationship_id: str, attribute: str, obs_a: str, obs_b: str
    ) -> bool:
        ka, kb = (obs_a, obs_b) if obs_a <= obs_b else (obs_b, obs_a)
        cur = self._db.execute(
            "SELECT 1 FROM inconsistencies "
            "WHERE relationship_id=? AND kind='detected' "
            "AND attribute=? AND obs_a=? AND obs_b=? LIMIT 1",
            (relationship_id, attribute, ka, kb),
        )
        return cur.fetchone() is not None

    def save_contradiction_candidate(
        self,
        relationship_id: str,
        attribute: str,
        value_a: str,
        value_b: str,
        obs_a: str,
        obs_b: str,
    ) -> str | None:
        """Persist a detected conflict as an unresolved inconsistency.

        Idempotent: returns None if an equivalent candidate is already saved.
        """
        ka, kb = (obs_a, obs_b) if obs_a <= obs_b else (obs_b, obs_a)
        if self.find_contradiction(relationship_id, attribute, ka, kb):
            return None
        iid = _next_id(self, "I", "inconsistencies", "id")
        description = f"[{attribute}] {value_a!r} vs {value_b!r} (obs {ka}, {kb})"
        self._db.execute(
            "INSERT INTO inconsistencies("
            "id, relationship_id, description, resolved, created_at, "
            "kind, attribute, value_a, value_b, obs_a, obs_b) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                iid,
                relationship_id,
                description,
                0,
                _now(),
                "detected",
                attribute,
                value_a,
                value_b,
                ka,
                kb,
            ),
        )
        self._commit()
        return iid

    # --- reviews ---
    def save_review(self, review: Review) -> None:
        self._db.execute(
            "INSERT INTO reviews("
            "id, relationship_id, timestamp, triggered_hooks, "
            "unresolved_inconsistencies, recommendation, notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                review.id,
                review.relationship_id,
                review.timestamp,
                json.dumps(review.triggered_hooks),
                review.unresolved_inconsistencies,
                review.recommendation,
                review.notes,
            ),
        )
        self._commit()

    def list_reviews(self, relationship_id: str) -> list[Review]:
        return [
            self._row_to_review(r)
            for r in self._db.execute(
                "SELECT * FROM reviews WHERE relationship_id=? ORDER BY timestamp",
                (relationship_id,),
            ).fetchall()
        ]

    def get_review(self, review_id: str) -> Review | None:
        row = self._db.execute(
            "SELECT * FROM reviews WHERE id=?", (review_id,)
        ).fetchone()
        return self._row_to_review(row) if row else None

    def _row_to_review(self, r: sqlite3.Row) -> Review:
        hooks = r["triggered_hooks"]
        return Review(
            id=r["id"],
            relationship_id=r["relationship_id"],
            timestamp=r["timestamp"],
            triggered_hooks=json.loads(hooks) if hooks else [],
            unresolved_inconsistencies=r["unresolved_inconsistencies"],
            recommendation=r["recommendation"],
            notes=r["notes"] or "",
        )

    def list_all_inconsistencies(self, relationship_id: str) -> list[Inconsistency]:
        """All inconsistencies (open + resolved) for the timeline / audit view."""
        return [
            self._row_to_inconsistency(r)
            for r in self._db.execute(
                "SELECT * FROM inconsistencies WHERE relationship_id=? ORDER BY id",
                (relationship_id,),
            ).fetchall()
        ]

    # --- cooldowns / precommitment ---
    def add_cooldown(
        self,
        relationship_id: str,
        decision: str,
        reason: str,
        started_at: str,
        expires_at: str,
    ) -> str:
        cid = _next_id(self, "C", "cooldowns", "id")
        self._db.execute(
            "INSERT INTO cooldowns("
            "id, relationship_id, decision, reason, started_at, expires_at, active) "
            "VALUES (?,?,?,?,?,?,1)",
            (cid, relationship_id, decision, reason, started_at, expires_at),
        )
        self._commit()
        return cid

    def list_cooldowns(
        self, relationship_id: str, active_only: bool = True
    ) -> list[Cooldown]:
        sql = "SELECT * FROM cooldowns WHERE relationship_id=?"
        params: list = [relationship_id]
        if active_only:
            sql += " AND active=1"
        sql += " ORDER BY started_at DESC"
        return [
            self._row_to_cooldown(r)
            for r in self._db.execute(sql, tuple(params)).fetchall()
        ]

    def _row_to_cooldown(self, r: sqlite3.Row) -> Cooldown:
        return Cooldown(
            id=r["id"],
            relationship_id=r["relationship_id"],
            decision=r["decision"],
            reason=r["reason"],
            started_at=r["started_at"],
            expires_at=r["expires_at"],
            active=bool(r["active"]),
        )

    def clear_cooldowns(self, relationship_id: str) -> int:
        """Deactivate all active cooldowns for a relationship. Returns count."""
        cur = self._db.execute(
            "UPDATE cooldowns SET active=0 WHERE relationship_id=? AND active=1",
            (relationship_id,),
        )
        self._commit()
        return cur.rowcount

    def log_override(
        self,
        relationship_id: str,
        cooldown_id: str | None,
        reason: str,
        timestamp: str,
    ) -> str:
        oid = _next_id(self, "OV", "override_log", "id")
        self._db.execute(
            "INSERT INTO override_log("
            "id, relationship_id, cooldown_id, reason, timestamp) "
            "VALUES (?,?,?,?,?)",
            (oid, relationship_id, cooldown_id, reason, timestamp),
        )
        self._commit()
        return oid

    def list_overrides(self, relationship_id: str) -> list[OverrideLog]:
        return [
            self._row_to_override(r)
            for r in self._db.execute(
                "SELECT * FROM override_log WHERE relationship_id=? ORDER BY timestamp",
                (relationship_id,),
            ).fetchall()
        ]

    def _row_to_override(self, r: sqlite3.Row) -> OverrideLog:
        return OverrideLog(
            id=r["id"],
            relationship_id=r["relationship_id"],
            cooldown_id=r["cooldown_id"],
            reason=r["reason"],
            timestamp=r["timestamp"],
        )

    # --- bulk export / restore / integrity (architecture phase 1) ---
    def export_all_tables(self) -> dict[str, list[dict[str, object]]]:
        """Dump every table as dict rows (bulk primitive; no domain mapping).

        Table names come from `schema.TABLE_ORDER` — package-owned constants,
        never caller input, so the interpolated identifiers below are safe by
        construction.
        """
        tables: dict[str, list[dict[str, object]]] = {}
        for table in TABLE_ORDER:
            rows = self._db.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
            tables[table] = [dict(r) for r in rows]
        return tables

    def restore_all_tables(self, tables: dict[str, list[dict[str, object]]]) -> int:
        """Replace the entire database with `tables`, all-or-nothing.

        Deletes in FK-child-first order, inserts in parent-first order, inside
        one transaction. Returns the number of rows restored.
        """
        total = 0
        with self.transaction():
            for table in reversed(TABLE_ORDER):
                self._db.execute(f"DELETE FROM {table}")  # noqa: S608
            for table in TABLE_ORDER:
                rows = tables.get(table, [])
                if not rows:
                    continue
                columns = list(rows[0].keys())
                col_names = ",".join(columns)
                placeholders = ",".join("?" * len(columns))
                self._db.executemany(
                    f"INSERT INTO {table} ({col_names}) "  # noqa: S608
                    f"VALUES ({placeholders})",
                    [tuple(r.get(c) for c in columns) for r in rows],
                )
                total += len(rows)
        return total

    def integrity_check(self) -> tuple[bool, str, list[dict[str, object]]]:
        """`PRAGMA integrity_check` + `PRAGMA foreign_key_check`.

        Returns (ok, detail, violations). A damaged or tampered database must
        fail loudly, never pass silently.
        """
        row = self._db.execute("PRAGMA integrity_check").fetchone()
        detail = str(row[0]) if row else "no result"
        violations = [
            dict(v) for v in self._db.execute("PRAGMA foreign_key_check").fetchall()
        ]
        return (detail == "ok" and not violations, detail, violations)

    # --- verification checklist (roadmap #3) ---
    def add_verification_item(self, relationship_id: str, item: str) -> str:
        vid = _next_id(self, "V", "verification_items", "id")
        self._db.execute(
            "INSERT INTO verification_items("
            "id, relationship_id, item, status, note, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                vid,
                relationship_id,
                item,
                VerificationStatus.UNVERIFIED.value,
                "",
                _now(),
            ),
        )
        self._commit()
        return vid

    def set_verification_status(
        self, item_id: str, status: str, note: str = ""
    ) -> bool:
        """Transition an item's status. Returns False if the item is unknown.

        `verified_at` is stamped on every transition out of unverified; items
        are append-only — status changes, never deletions.
        """
        _validate_verification_status(status)
        cur = self._db.execute(
            "UPDATE verification_items SET status=?, note=?, verified_at=? WHERE id=?",
            (status, note, _now(), item_id),
        )
        self._commit()
        return cur.rowcount > 0

    def list_verification_items(self, relationship_id: str) -> list[VerificationItem]:
        return [
            self._row_to_verification_item(r)
            for r in self._db.execute(
                "SELECT * FROM verification_items WHERE relationship_id=? ORDER BY id",
                (relationship_id,),
            ).fetchall()
        ]

    def _row_to_verification_item(self, r: sqlite3.Row) -> VerificationItem:
        return VerificationItem(
            id=r["id"],
            relationship_id=r["relationship_id"],
            item=r["item"],
            status=r["status"],
            note=r["note"],
            created_at=r["created_at"],
            verified_at=r["verified_at"],
        )
