"""Export/restore bundle tests (architecture phase 1, D1).

Written test-first per docs/proposals/PLAN_phase1_data_safety.md: these fail
until `services/export.py` exists, then pin lossless round-tripping across
every table, checksum tamper detection, schema-version refusal and
replace-not-append semantics.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from love_risk_engine.core.exposure import Exposure
from love_risk_engine.core.observation import Claim
from love_risk_engine.core.review import Review
from love_risk_engine.core.signals import SignalType
from love_risk_engine.core.state import EmotionalState, RelationshipState
from love_risk_engine.services.export import (
    BUNDLE_FORMAT,
    BUNDLE_VERSION,
    _canonical,
    restore_bundle,
    save_bundle,
)
from love_risk_engine.storage.database import Database
from love_risk_engine.storage.schema import SCHEMA_VERSION


def _seed(db: Database) -> str:
    """Insert at least one row into every table. Returns the relationship id."""
    rid = db.add_relationship("Alex", kind="MENTOR")
    db.upsert_state(
        RelationshipState(
            rid, attraction=7.5, trust=4.0, emotional_state=EmotionalState.ANXIOUS
        )
    )
    db.upsert_exposure(Exposure(rid, time=1, emotional=2))
    db.add_observation(
        rid,
        "honesty",
        "said X",
        "losing trust",
        "work deadline",
        "self",
        5.0,
        rationalization=True,
        claims=[Claim("funding", "will fund")],
        signal_type=SignalType.CHEAP,
    )
    bid = db.add_boundary("no lying", severity="HARD")
    db.add_boundary_hit(bid, rid, "denied a message")
    iid = db.add_inconsistency(rid, "story differs")
    db.resolve_inconsistency(iid, "dismissed", "not a real conflict")
    db.save_review(
        Review(
            id="RV001",
            relationship_id=rid,
            timestamp="2026-09-01T00:00:00+00:00",
            triggered_hooks=["attraction_exceeds_trust"],
            unresolved_inconsistencies=0,
            recommendation="CONTINUE_OBSERVING",
            notes="",
        )
    )
    db.add_cooldown(
        rid, "PAUSE", "test", "2026-09-01T00:00:00+00:00", "2026-09-03T00:00:00+00:00"
    )
    db.log_override(rid, "C001", "because", "2026-09-01T00:00:00+00:00")
    return rid


def test_export_restore_roundtrip_is_lossless(tmp_path):
    src = Database(str(tmp_path / "src.db"))
    try:
        src.init()
        _seed(src)
        bundle_path = str(tmp_path / "backup.json")
        save_bundle(src, bundle_path)
        expected = src.export_all_tables()
    finally:
        src.close()
    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        dst.add_relationship("JunkThatMustBeReplaced")
        restored = restore_bundle(dst, bundle_path)
        assert restored > 0
        assert dst.export_all_tables() == expected
    finally:
        dst.close()


def test_restore_replaces_existing_contents(tmp_path):
    src = Database(str(tmp_path / "src.db"))
    try:
        src.init()
        _seed(src)
        bundle_path = str(tmp_path / "backup.json")
        save_bundle(src, bundle_path)
        n_src_relationships = len(src.list_relationships())
    finally:
        src.close()

    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        dst.add_relationship("A")
        dst.add_relationship("B")
        restore_bundle(dst, bundle_path)
        assert len(dst.list_relationships()) == n_src_relationships
    finally:
        dst.close()


def test_restore_rejects_tampered_bundle(tmp_path):
    src = Database(str(tmp_path / "src.db"))
    try:
        src.init()
        _seed(src)
        bundle_path = str(tmp_path / "backup.json")
        save_bundle(src, bundle_path)
    finally:
        src.close()

    with open(bundle_path, encoding="utf-8") as f:
        bundle = json.load(f)
    bundle["tables"]["relationships"][0]["alias"] = "TAMPERED"
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f)

    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        with pytest.raises(ValueError, match="checksum"):
            restore_bundle(dst, bundle_path)
    finally:
        dst.close()


def test_restore_rejects_wrong_schema_version(tmp_path):
    # A *validly checksummed* bundle with an older schema version must still be
    # refused — cross-version restore is out of scope by decision.
    payload = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "schema_version": SCHEMA_VERSION - 1,
        "tables": {},
    }
    payload["sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    bundle_path = tmp_path / "old_schema.json"
    bundle_path.write_text(json.dumps(payload), encoding="utf-8")

    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        with pytest.raises(ValueError, match="schema"):
            restore_bundle(dst, str(bundle_path))
    finally:
        dst.close()


def test_restore_rejects_missing_schema_version(tmp_path):
    # A validly checksummed bundle without a schema version is refused.
    payload = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "tables": {},
    }
    payload["sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    bundle_path = tmp_path / "no_schema.json"
    bundle_path.write_text(json.dumps(payload), encoding="utf-8")

    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        with pytest.raises(ValueError, match="schema_version"):
            restore_bundle(dst, str(bundle_path))
    finally:
        dst.close()


def test_restore_rejects_unsupported_version(tmp_path):
    bundle_path = tmp_path / "v99.json"
    bundle_path.write_text(
        json.dumps({"format": BUNDLE_FORMAT, "version": 99}), encoding="utf-8"
    )
    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        with pytest.raises(ValueError, match="version"):
            restore_bundle(dst, str(bundle_path))
    finally:
        dst.close()


def test_restore_rejects_missing_tables(tmp_path):
    # A validly checksummed bundle without a tables payload is refused.
    payload = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    payload["sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    bundle_path = tmp_path / "no_tables.json"
    bundle_path.write_text(json.dumps(payload), encoding="utf-8")

    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        with pytest.raises(ValueError, match="tables"):
            restore_bundle(dst, str(bundle_path))
    finally:
        dst.close()


def test_restore_rejects_unknown_format(tmp_path):
    bundle_path = tmp_path / "not_a_bundle.json"
    bundle_path.write_text(json.dumps({"format": "something-else"}), encoding="utf-8")

    dst = Database(str(tmp_path / "dst.db"))
    try:
        dst.init()
        with pytest.raises(ValueError, match="format"):
            restore_bundle(dst, str(bundle_path))
    finally:
        dst.close()
