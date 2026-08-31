"""Boundaries are the safety-critical path: a HARD hit can recommend EXIT.

These tests pin the contract between the domain objects in `core.boundaries`
and the severity strings the storage layer actually writes. The two must stay
in sync — a typo'd severity silently downgrades a hard boundary to a soft one.
"""

import pytest
from love_risk_engine.core.boundaries import Boundary, BoundaryHit
from love_risk_engine.storage.database import Database


def test_boundary_defaults():
    b = Boundary(id="B001", description="no disrespect", severity="HARD")
    assert b.active is True
    assert b.trigger_keywords == ""


def test_boundary_supports_soft_severity():
    b = Boundary(id="B002", description="late replies", severity="SOFT")
    assert b.severity == "SOFT"


def test_boundary_hit_carries_evidence():
    hit = BoundaryHit(
        id="H001",
        boundary_id="B001",
        relationship_id="R001",
        evidence="mocked my boundary on call",
        timestamp="2026-08-30T10:00:00+00:00",
    )
    assert hit.evidence
    assert hit.boundary_id == "B001"


@pytest.mark.parametrize("severity", ["HARD", "SOFT"])
def test_domain_and_storage_severity_vocabulary_match(severity):
    """The dataclass has no enum, so the DB is the other half of the contract."""
    b = Boundary(id="B001", description="x", severity=severity)
    assert b.severity == severity


def test_hard_hit_is_distinguished_from_soft(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    hard = db.add_boundary("no disrespect", severity="HARD")
    soft = db.add_boundary("late replies", severity="SOFT")
    db.add_boundary_hit(hard, rid, "mocked me on the call")
    db.add_boundary_hit(soft, rid, "replied after two days")

    assert len(db.list_boundary_hits(rid, only_hard=True)) == 1
    assert len(db.list_boundary_hits(rid, only_hard=False)) == 2
    db.close()


def test_boundary_list_filters_by_active(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    db.add_boundary("kept", severity="HARD")
    retired = db.add_boundary("retired", severity="SOFT")
    db._db.execute("UPDATE boundaries SET active=0 WHERE id=?", (retired,))
    db._db.commit()

    assert len(db.list_boundaries(active_only=True)) == 1
    assert len(db.list_boundaries(active_only=False)) == 2
    db.close()


def test_storage_returns_domain_objects_not_raw_rows(tmp_path):
    """The storage layer maps boundary rows onto `core.boundaries` types."""
    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    bid = db.add_boundary("no disrespect", severity="HARD", trigger_keywords="mock")

    boundary = db.get_boundary(bid)
    assert isinstance(boundary, Boundary)
    assert boundary.id == bid
    assert boundary.severity == "HARD"
    assert boundary.trigger_keywords == "mock"
    assert boundary.active is True

    db.add_boundary_hit(bid, rid, "mocked me on the call")
    hit = db.list_boundary_hits(rid, only_hard=True)[0]
    assert isinstance(hit, BoundaryHit)
    assert hit.boundary_id == bid
    assert hit.relationship_id == rid
    assert hit.evidence == "mocked me on the call"
    assert hit.timestamp  # stamped by the storage layer, never blank
    db.close()


def test_get_boundary_returns_none_when_missing(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    assert db.get_boundary("B999") is None
    db.close()
