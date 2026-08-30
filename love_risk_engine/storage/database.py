"""SQLite-backed storage for LoveRiskEngine.

Pure stdlib (sqlite3). All public methods take/return domain objects defined
in `core`, so the rest of the app never touches raw rows. IDs are readable
sequential tokens (R001, O001, B001, ...) for easy CLI use.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from ..core.exposure import Exposure
from ..core.observation import Claim, Observation
from ..core.signals import SignalType
from ..core.state import EmotionalState, RelationshipState
from .schema import SCHEMA


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _next_id(db: "Database", prefix: str, table: str, column: str) -> str:
    cur = db.conn.execute(  # type: ignore[union-attr]
        f"SELECT {column} FROM {table} WHERE {column} LIKE ?", (prefix + "%",)
    )
    nums: List[int] = []
    for (val,) in cur.fetchall():
        try:
            nums.append(int(str(val)[len(prefix):]))
        except ValueError:
            pass
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:03d}"


class Database:
    def __init__(self, path: str = "love_risk.db") -> None:
        self.path = path
        self.conn: Optional[sqlite3.Connection] = None

    # --- lifecycle ---
    def connect(self) -> None:
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def init(self) -> None:
        if self.conn is None:
            self.connect()
        assert self.conn is not None
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Make schema additions backward-compatible with older databases."""
        self.conn.execute(  # type: ignore[union-attr]
            "CREATE TABLE IF NOT EXISTS observation_claims ("
            "observation_id TEXT NOT NULL, attribute TEXT NOT NULL, "
            "value TEXT NOT NULL, idx INTEGER NOT NULL DEFAULT 0, "
            "FOREIGN KEY (observation_id) REFERENCES observations(id))"
        )
        cols = {
            r[1]
            for r in self.conn.execute(  # type: ignore[union-attr]
                "PRAGMA table_info(inconsistencies)"
            ).fetchall()
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
                self.conn.execute(  # type: ignore[union-attr]
                    f"ALTER TABLE inconsistencies ADD COLUMN {col} {ddl}"
                )
        # signal_type on observations (v0.2 costly-signal classification)
        obs_cols = {
            r[1]
            for r in self.conn.execute(  # type: ignore[union-attr]
                "PRAGMA table_info(observations)"
            ).fetchall()
        }
        if "signal_type" not in obs_cols:
            self.conn.execute(  # type: ignore[union-attr]
                "ALTER TABLE observations ADD COLUMN signal_type "
                "TEXT NOT NULL DEFAULT 'UNSPECIFIED'"
            )
        # resolution tracking on inconsistencies (v0.2 contradiction UX)
        inc_cols = {
            r[1]
            for r in self.conn.execute(  # type: ignore[union-attr]
                "PRAGMA table_info(inconsistencies)"
            ).fetchall()
        }
        for col, ddl in {
            "resolution": "TEXT",
            "resolution_note": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if col not in inc_cols:
                self.conn.execute(  # type: ignore[union-attr]
                    f"ALTER TABLE inconsistencies ADD COLUMN {col} {ddl}"
                )

    def __enter__(self) -> "Database":
        self.init()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- relationships ---
    def add_relationship(self, alias: str, status: str = "ACTIVE") -> str:
        rid = _next_id(self, "R", "relationships", "id")
        self.conn.execute(  # type: ignore[union-attr]
            "INSERT INTO relationships(id, alias, status, created_at) "
            "VALUES (?,?,?,?)",
            (rid, alias, status, _now()),
        )
        self.conn.commit()  # type: ignore[union-attr]
        return rid

    def get_relationship(self, token: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM relationships WHERE id=? OR alias=?",
            (token, token),
        ).fetchone()

    def list_relationships(self) -> List[sqlite3.Row]:
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM relationships ORDER BY id"
        ).fetchall()

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
        claims: Optional[List[Claim]] = None,
        signal_type: SignalType = SignalType.UNSPECIFIED,
    ) -> str:
        oid = _next_id(self, "O", "observations", "id")
        self.conn.execute(  # type: ignore[union-attr]
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
            self.conn.execute(  # type: ignore[union-attr]
                "INSERT INTO observation_claims("
                "observation_id, attribute, value, idx) VALUES (?,?,?,?)",
                (oid, c.attribute.strip(), c.value.strip(), idx),
            )
        self.conn.commit()  # type: ignore[union-attr]
        return oid

    def get_observations(self, relationship_id: str) -> List[Observation]:
        rows = self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM observations WHERE relationship_id=? ORDER BY timestamp",
            (relationship_id,),
        ).fetchall()
        return [self._row_to_observation(r) for r in rows]

    def import_observations(
        self, relationship_id: str, observations: List[Observation]
    ) -> int:
        """Bulk-insert observations (e.g. from a chat import).

        Reuses add_observation so claims are persisted too. Returns the number
        of observations inserted. Never deletes or overwrites existing data.
        """
        count = 0
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
        claim_rows = self.conn.execute(  # type: ignore[union-attr]
            "SELECT attribute, value FROM observation_claims "
            "WHERE observation_id=? ORDER BY idx",
            (r["id"],),
        ).fetchall()
        claims = [Claim(attribute=cr["attribute"], value=cr["value"]) for cr in claim_rows]
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
        self.conn.execute(  # type: ignore[union-attr]
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
        self.conn.commit()  # type: ignore[union-attr]

    def get_state(self, relationship_id: str) -> Optional[RelationshipState]:
        r = self.conn.execute(  # type: ignore[union-attr]
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
        self.conn.execute(  # type: ignore[union-attr]
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
        self.conn.commit()  # type: ignore[union-attr]

    def get_exposure(self, relationship_id: str) -> Optional[Exposure]:
        r = self.conn.execute(  # type: ignore[union-attr]
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
        self.conn.execute(  # type: ignore[union-attr]
            "INSERT INTO boundaries(id, description, severity, active, "
            "trigger_keywords) VALUES (?,?,?,?,?)",
            (bid, description, severity, 1, trigger_keywords),
        )
        self.conn.commit()  # type: ignore[union-attr]
        return bid

    def get_boundary(self, boundary_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM boundaries WHERE id=?", (boundary_id,)
        ).fetchone()

    def list_boundaries(self, active_only: bool = False) -> List[sqlite3.Row]:
        sql = "SELECT * FROM boundaries"
        params: tuple = ()
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY id"
        return self.conn.execute(sql, params).fetchall()  # type: ignore[union-attr]

    # --- boundary hits ---
    def add_boundary_hit(
        self, boundary_id: str, relationship_id: str, evidence: str
    ) -> str:
        hid = _next_id(self, "H", "boundary_hits", "id")
        self.conn.execute(  # type: ignore[union-attr]
            "INSERT INTO boundary_hits("
            "id, boundary_id, relationship_id, evidence, timestamp) "
            "VALUES (?,?,?,?,?)",
            (hid, boundary_id, relationship_id, evidence, _now()),
        )
        self.conn.commit()  # type: ignore[union-attr]
        return hid

    def list_boundary_hits(
        self, relationship_id: str, only_hard: bool = False
    ) -> List[sqlite3.Row]:
        sql = (
            "SELECT h.* FROM boundary_hits h "
            "JOIN boundaries b ON h.boundary_id = b.id "
            "WHERE h.relationship_id=?"
        )
        params: list = [relationship_id]
        if only_hard:
            sql += " AND b.severity='HARD'"
        return self.conn.execute(sql, tuple(params)).fetchall()  # type: ignore[union-attr]

    # --- inconsistencies ---
    def add_inconsistency(self, relationship_id: str, description: str) -> str:
        iid = _next_id(self, "I", "inconsistencies", "id")
        self.conn.execute(  # type: ignore[union-attr]
            "INSERT INTO inconsistencies("
            "id, relationship_id, description, resolved, created_at) "
            "VALUES (?,?,?,?,?)",
            (iid, relationship_id, description, 0, _now()),
        )
        self.conn.commit()  # type: ignore[union-attr]
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
        cur = self.conn.execute(  # type: ignore[union-attr]
            "UPDATE inconsistencies SET resolved=1, resolution=?, resolution_note=? "
            "WHERE id=?",
            (resolution, note, inconsistency_id),
        )
        self.conn.commit()  # type: ignore[union-attr]
        return cur.rowcount > 0

    def list_inconsistencies(
        self, relationship_id: str, resolved: bool = False
    ) -> List[sqlite3.Row]:
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM inconsistencies "
            "WHERE relationship_id=? AND resolved=? ORDER BY id",
            (relationship_id, 1 if resolved else 0),
        ).fetchall()

    def acknowledged_inconsistencies(
        self, relationship_id: str
    ) -> List[sqlite3.Row]:
        """Resolved items kept as audit / 'acknowledged yellow flags'.

        All resolved items are returned; callers distinguish by `resolution`.
        """
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM inconsistencies "
            "WHERE relationship_id=? AND resolved=1 ORDER BY id",
            (relationship_id,),
        ).fetchall()

    # --- contradictions (auto-detected inconsistencies) ---
    def find_contradiction(
        self, relationship_id: str, attribute: str, obs_a: str, obs_b: str
    ) -> bool:
        ka, kb = (obs_a, obs_b) if obs_a <= obs_b else (obs_b, obs_a)
        cur = self.conn.execute(  # type: ignore[union-attr]
            "SELECT 1 FROM inconsistencies "
            "WHERE relationship_id=? AND kind='detected' "
            "AND attribute=? AND obs_a=? AND obs_b=? LIMIT 1",
            (relationship_id, attribute, ka, kb),
        )
        return cur.fetchone() is not None

    def save_contradiction_candidate(
        self, relationship_id: str, attribute: str, value_a: str, value_b: str, obs_a: str, obs_b: str
    ) -> Optional[str]:
        """Persist a detected conflict as an unresolved inconsistency.

        Idempotent: returns None if an equivalent candidate is already saved.
        """
        ka, kb = (obs_a, obs_b) if obs_a <= obs_b else (obs_b, obs_a)
        if self.find_contradiction(relationship_id, attribute, ka, kb):
            return None
        iid = _next_id(self, "I", "inconsistencies", "id")
        description = (
            f"[{attribute}] {value_a!r} vs {value_b!r} (obs {ka}, {kb})"
        )
        self.conn.execute(  # type: ignore[union-attr]
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
        self.conn.commit()  # type: ignore[union-attr]
        return iid

    # --- reviews ---
    def save_review(self, review: "Review") -> None:  # type: ignore[name-defined]
        self.conn.execute(  # type: ignore[union-attr]
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
        self.conn.commit()  # type: ignore[union-attr]

    def list_reviews(self, relationship_id: str) -> List[sqlite3.Row]:
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM reviews WHERE relationship_id=? ORDER BY timestamp",
            (relationship_id,),
        ).fetchall()

    def list_all_inconsistencies(self, relationship_id: str) -> List[sqlite3.Row]:
        """All inconsistencies (open + resolved) for the timeline / audit view."""
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM inconsistencies WHERE relationship_id=? ORDER BY id",
            (relationship_id,),
        ).fetchall()

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
        self.conn.execute(  # type: ignore[union-attr]
            "INSERT INTO cooldowns("
            "id, relationship_id, decision, reason, started_at, expires_at, active) "
            "VALUES (?,?,?,?,?,?,1)",
            (cid, relationship_id, decision, reason, started_at, expires_at),
        )
        self.conn.commit()  # type: ignore[union-attr]
        return cid

    def list_cooldowns(
        self, relationship_id: str, active_only: bool = True
    ) -> List[sqlite3.Row]:
        sql = "SELECT * FROM cooldowns WHERE relationship_id=?"
        params: list = [relationship_id]
        if active_only:
            sql += " AND active=1"
        sql += " ORDER BY started_at DESC"
        return self.conn.execute(sql, tuple(params)).fetchall()  # type: ignore[union-attr]

    def clear_cooldowns(self, relationship_id: str) -> int:
        """Deactivate all active cooldowns for a relationship. Returns count."""
        cur = self.conn.execute(  # type: ignore[union-attr]
            "UPDATE cooldowns SET active=0 WHERE relationship_id=? AND active=1",
            (relationship_id,),
        )
        self.conn.commit()  # type: ignore[union-attr]
        return cur.rowcount

    def log_override(
        self,
        relationship_id: str,
        cooldown_id: Optional[str],
        reason: str,
        timestamp: str,
    ) -> str:
        oid = _next_id(self, "OV", "override_log", "id")
        self.conn.execute(  # type: ignore[union-attr]
            "INSERT INTO override_log(id, relationship_id, cooldown_id, reason, timestamp) "
            "VALUES (?,?,?,?,?)",
            (oid, relationship_id, cooldown_id, reason, timestamp),
        )
        self.conn.commit()  # type: ignore[union-attr]
        return oid

    def list_overrides(self, relationship_id: str) -> List[sqlite3.Row]:
        return self.conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM override_log WHERE relationship_id=? ORDER BY timestamp",
            (relationship_id,),
        ).fetchall()
