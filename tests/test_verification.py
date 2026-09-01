"""Mutual verification checklist tests (roadmap #3, architecture phase 2).

Written test-first per docs/proposals/PLAN_verification_checklist.md: these
fail until schema v4 + `core/verification.py` exist, then pin the three-state
lifecycle, the append-only semantics, and the status integration.
"""

from __future__ import annotations

import pytest
from love_risk_engine.core.verification import VerificationItem, VerificationStatus
from love_risk_engine.storage.database import Database


def _db(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init()
    return db, db.add_relationship("Alex")


def test_add_item_defaults_unverified(tmp_path):
    db, rid = _db(tmp_path)
    vid = db.add_verification_item(rid, "introduced me to their friends")
    item = db.list_verification_items(rid)[0]
    assert vid == "V001"
    assert item.status == VerificationStatus.UNVERIFIED.value
    assert item.verified_at is None
    assert item.note == ""
    db.close()


def test_check_marks_verified_with_timestamp(tmp_path):
    db, rid = _db(tmp_path)
    vid = db.add_verification_item(rid, "met them at their workplace")
    assert db.set_verification_status(vid, "verified") is True
    item = db.list_verification_items(rid)[0]
    assert item.status == VerificationStatus.VERIFIED.value
    assert item.verified_at is not None
    db.close()


def test_fail_marks_failed_with_note(tmp_path):
    db, rid = _db(tmp_path)
    vid = db.add_verification_item(rid, "has no secret family")
    assert (
        db.set_verification_status(vid, "failed", note="friends confirmed otherwise")
        is True
    )
    item = db.list_verification_items(rid)[0]
    assert item.status == VerificationStatus.FAILED.value
    assert item.note == "friends confirmed otherwise"
    db.close()


def test_set_status_unknown_item_returns_false(tmp_path):
    db, _rid = _db(tmp_path)
    assert db.set_verification_status("V999", "verified") is False
    db.close()


def test_set_status_rejects_invalid_status(tmp_path):
    db, rid = _db(tmp_path)
    vid = db.add_verification_item(rid, "x")
    with pytest.raises(ValueError):
        db.set_verification_status(vid, "maybe")
    db.close()


def test_list_returns_ordered_domain_objects(tmp_path):
    db, rid = _db(tmp_path)
    db.add_verification_item(rid, "a")
    db.add_verification_item(rid, "b")
    items = db.list_verification_items(rid)
    assert [i.id for i in items] == ["V001", "V002"]
    assert all(isinstance(i, VerificationItem) for i in items)
    db.close()
