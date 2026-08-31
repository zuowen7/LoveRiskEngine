"""Tests for the contradiction tracker (roadmap feature)."""

import pytest
from love_risk_engine.core.contradiction import (
    contradiction_key,
    detect_contradictions,
    normalize_attribute,
)
from love_risk_engine.core.observation import Claim, Observation
from love_risk_engine.storage.database import Database


def _obs(oid, claims):
    return Observation(
        id=oid,
        relationship_id="R001",
        timestamp="2026-01-01T00:00:00",
        category="signal",
        observation="x",
        interpretation="y",
        alternative_explanation="z",
        source="self",
        confidence=5.0,
        claims=[Claim(a, v) for a, v in claims],
    )


# --- pure detection -------------------------------------------------------
def test_no_contradiction_when_values_match():
    obs = [
        _obs("O001", [("status", "single")]),
        _obs("O002", [("status", "single")]),
    ]
    assert detect_contradictions(obs) == []


def test_contradiction_when_same_attribute_differs():
    obs = [
        _obs("O001", [("status", "single")]),
        _obs("O002", [("status", "married")]),
    ]
    cands = detect_contradictions(obs)
    assert len(cands) == 1
    c = cands[0]
    assert c.attribute == "status"
    assert {c.value_a, c.value_b} == {"single", "married"}
    assert {c.obs_a_id, c.obs_b_id} == {"O001", "O002"}


def test_multiple_values_produce_all_pairs():
    obs = [
        _obs("O001", [("job", "barista")]),
        _obs("O002", [("job", "engineer")]),
        _obs("O003", [("job", "doctor")]),
    ]
    cands = detect_contradictions(obs)
    # 3 distinct values -> 3 unordered pairs
    assert len(cands) == 3


def test_normalize_attribute_collapses_variants():
    assert normalize_attribute("Relationship Status") == "relationship_status"
    assert normalize_attribute("relationship-status") == "relationship_status"
    assert normalize_attribute("  Job ") == "job"


def test_different_attributes_do_not_conflict():
    obs = [
        _obs("O001", [("status", "single")]),
        _obs("O002", [("job", "single")]),
    ]
    assert detect_contradictions(obs) == []


def test_empty_claims_ignored():
    obs = [_obs("O001", []), _obs("O002", [("", "x"), ("name", "  ")])]
    assert detect_contradictions(obs) == []


def test_contradiction_key_is_order_independent():
    assert contradiction_key("status", "O001", "O002") == contradiction_key(
        "status", "O002", "O001"
    )


# --- storage round-trip ---------------------------------------------------
@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "t.db"))
    d.init()
    yield d
    d.close()


def test_claims_round_trip(db):
    db.add_relationship("Alex")
    db.add_observation(
        "R001",
        "signal",
        "he said he is single",
        "honest",
        "could be joking",
        "self",
        5.0,
        claims=[Claim("relationship_status", "single")],
    )
    obs = db.get_observations("R001")
    assert len(obs) == 1
    assert obs[0].claims == [Claim("relationship_status", "single")]


def test_save_contradiction_idempotent(db):
    db.add_relationship("Alex")
    db.add_observation(
        "R001",
        "signal",
        "a",
        "",
        "",
        "self",
        5.0,
        claims=[Claim("status", "single")],
    )
    db.add_observation(
        "R001",
        "signal",
        "b",
        "",
        "",
        "self",
        5.0,
        claims=[Claim("status", "married")],
    )
    # detect
    cands = detect_contradictions(db.get_observations("R001"))
    assert len(cands) == 1
    c = cands[0]
    # save twice -> only one persisted
    id1 = db.save_contradiction_candidate(
        "R001", c.attribute, c.value_a, c.value_b, c.obs_a_id, c.obs_b_id
    )
    id2 = db.save_contradiction_candidate(
        "R001", c.attribute, c.value_a, c.value_b, c.obs_a_id, c.obs_b_id
    )
    assert id1 is not None
    assert id2 is None
    # feeds the inconsistency pipeline (and thus review counts)
    unresolved = db.list_inconsistencies("R001", resolved=False)
    assert len(unresolved) == 1
    assert unresolved[0].kind == "detected"


# --- CLI smoke ------------------------------------------------------------
def test_cli_contradiction_flow(tmp_path, monkeypatch):
    import love_risk_engine.cli as cli

    db_path = str(tmp_path / "cli.db")
    monkeypatch.setenv("LRE_DB_PATH", db_path)
    cli.main(["init"])
    cli.main(["relationship", "add", "Alex"])
    cli.main(
        [
            "observe",
            "Alex",
            "--observation",
            "said single",
            "--claim",
            "relationship_status=single",
        ]
    )
    cli.main(
        [
            "observe",
            "Alex",
            "--observation",
            "mentioned wife",
            "--claim",
            "relationship_status=married",
        ]
    )
    # detect (not saved yet)
    out = []
    monkeypatch.setattr("sys.stdout", _Collector(out))
    cli.main(["contradictions", "Alex"])
    assert any("Conflicting" in line for line in out)
    # nothing persisted yet
    assert db_unresolved(db_path) == 0
    # save
    out.clear()
    cli.main(["contradictions", "Alex", "--save"])
    assert db_unresolved(db_path) == 1
    # idempotent re-run
    cli.main(["contradictions", "Alex", "--save"])
    assert db_unresolved(db_path) == 1


class _Collector:
    def __init__(self, target):
        self._t = target

    def write(self, s):
        self._t.append(s)

    def flush(self):
        pass


def db_unresolved(path):
    d = Database(path)
    d.init()
    try:
        return len(d.list_inconsistencies("R001", resolved=False))
    finally:
        d.close()
