"""Self-consistency audit: pure rules and service assembly.

The audit surfaces record-level inconsistencies. These tests deliberately pin
the non-diagnostic boundary: every finding is informational and has no proposed
decision.
"""

from __future__ import annotations

import pytest
from love_risk_engine.core.consistency import (
    audit_consistency,
    detect_criterion_direction_conflicts,
    interpretation_without_alternative,
    normalize_criterion_key,
    self_reported_rationalization_run,
    trust_change_without_new_evidence,
    unresolved_structured_conflicts,
)
from love_risk_engine.core.history import StateChange
from love_risk_engine.core.observation import JudgmentDirection, Observation
from love_risk_engine.services.consistency import run_consistency_audit
from love_risk_engine.storage.database import Database

START = "2026-08-01T00:00:00+00:00"
END = "2026-09-01T00:00:00+00:00"


def _state(oid: str, timestamp: str, trust: float) -> StateChange:
    return StateChange(
        oid,
        "R001",
        timestamp,
        attraction=5.0,
        trust=trust,
        uncertainty=5.0,
        emotional_state="NEUTRAL",
    )


def _obs(
    oid: str,
    timestamp: str,
    *,
    relationship_id: str = "R001",
    interpretation: str = "",
    alternative: str = "",
    rationalization: bool = False,
    criterion_key: str = "",
    direction: JudgmentDirection = JudgmentDirection.UNSPECIFIED,
) -> Observation:
    return Observation(
        id=oid,
        relationship_id=relationship_id,
        timestamp=timestamp,
        category="general",
        observation="recorded fact",
        interpretation=interpretation,
        alternative_explanation=alternative,
        source="self",
        confidence=5.0,
        rationalization=rationalization,
        criterion_key=criterion_key,
        judgment_direction=direction,
    )


def test_trust_change_without_new_evidence_fires() -> None:
    history = [
        _state("SH001", "2026-07-30T00:00:00+00:00", 3.0),
        _state("SH002", "2026-08-10T00:00:00+00:00", 6.0),
    ]
    finding = trust_change_without_new_evidence(history, [], START, END)
    assert finding is not None
    assert finding.rule_id == "trust_change_without_new_evidence"
    assert finding.proposed_decision is None
    assert finding.msg_params["count"] == "1"
    assert "3.0 -> 6.0" in finding.message


def test_trust_change_interval_is_open_then_closed() -> None:
    history = [
        _state("SH001", "2026-08-02T00:00:00+00:00", 3.0),
        _state("SH002", "2026-08-10T00:00:00+00:00", 6.0),
    ]
    # Evidence at the previous snapshot is not new and does not suppress.
    assert (
        trust_change_without_new_evidence(
            history, ["2026-08-02T00:00:00+00:00"], START, END
        )
        is not None
    )
    # Evidence at the current snapshot is included and does suppress.
    assert (
        trust_change_without_new_evidence(
            history, ["2026-08-10T00:00:00+00:00"], START, END
        )
        is None
    )


def test_trust_change_ignores_unchanged_out_of_window_and_bad_timestamps() -> None:
    history = [
        _state("SH001", "2026-06-01T00:00:00+00:00", 3.0),
        _state("SH002", "2026-07-01T00:00:00+00:00", 6.0),
        _state("SH003", "not-a-time", 8.0),
        _state("SH004", "2026-08-20T00:00:00+00:00", 6.0),
    ]
    assert trust_change_without_new_evidence(history, [], START, END) is None


@pytest.mark.parametrize(
    "start, end, message",
    [
        ("not-a-time", END, "valid ISO-8601"),
        (END, START, "start must not be after end"),
    ],
)
def test_audit_window_rejects_invalid_bounds(start, end, message) -> None:
    with pytest.raises(ValueError, match=message):
        interpretation_without_alternative([], start, end)


def test_interpretation_without_alternative_is_windowed() -> None:
    observations = [
        _obs(
            "O001",
            "2026-08-10T00:00:00+00:00",
            interpretation="they do not care",
        ),
        _obs(
            "O002",
            "2026-07-10T00:00:00+00:00",
            interpretation="outside",
        ),
        _obs("O003", "2026-08-11T00:00:00+00:00"),
        _obs(
            "O004",
            "2026-08-12T00:00:00+00:00",
            interpretation="one reading",
            alternative="another reading",
        ),
    ]
    finding = interpretation_without_alternative(observations, START, END)
    assert finding is not None
    assert finding.rule_id == "interpretation_without_alternative"
    assert finding.msg_params == {"count": "1", "ids": "O001"}


def test_interpretation_finding_truncates_long_id_list() -> None:
    observations = [
        _obs(
            f"O{index:03d}",
            f"2026-08-{index:02d}T00:00:00+00:00",
            interpretation="one-sided",
        )
        for index in range(1, 7)
    ]
    finding = interpretation_without_alternative(observations, START, END)
    assert finding is not None
    assert finding.msg_params["count"] == "6"
    assert finding.msg_params["ids"].endswith(", ...")


def test_self_reported_rationalization_run_sorts_and_resets() -> None:
    observations = [
        _obs("O004", "2026-08-04T00:00:00+00:00", rationalization=True),
        _obs("O001", "2026-08-01T01:00:00+00:00", rationalization=True),
        _obs("O003", "2026-08-03T00:00:00+00:00"),
        _obs("O006", "2026-08-06T00:00:00+00:00", rationalization=True),
        _obs("O005", "2026-08-05T00:00:00+00:00", rationalization=True),
        _obs("O002", "2026-08-02T00:00:00+00:00", rationalization=True),
    ]
    finding = self_reported_rationalization_run(observations, START, END)
    assert finding is not None
    assert finding.rule_id == "self_reported_rationalization_run"
    assert finding.msg_params["count"] == "3"
    assert "self-reported" in finding.message


def test_self_reported_rationalization_below_run_is_silent() -> None:
    observations = [
        _obs("O001", "2026-08-01T01:00:00+00:00", rationalization=True),
        _obs("O002", "2026-08-02T00:00:00+00:00", rationalization=True),
    ]
    assert self_reported_rationalization_run(observations, START, END) is None


def test_unresolved_structured_conflicts_only_fires_for_positive_count() -> None:
    finding = unresolved_structured_conflicts(2)
    assert finding is not None
    assert finding.msg_params["count"] == "2"
    assert finding.proposed_decision is None
    assert unresolved_structured_conflicts(0) is None


def test_normalize_criterion_key_collapses_separators() -> None:
    assert normalize_criterion_key(" Missed-Reply ") == "missed_reply"
    assert normalize_criterion_key("missed__reply") == "missed_reply"


def test_opposite_directions_under_same_criterion_form_candidate() -> None:
    observations = [
        _obs(
            "O001",
            "2026-08-10T00:00:00+00:00",
            criterion_key="Missed Reply",
            direction=JudgmentDirection.WEAKENS_TRUST,
        ),
        _obs(
            "O002",
            "2026-08-11T00:00:00+00:00",
            relationship_id="R002",
            criterion_key="missed-reply",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        ),
    ]
    candidates = detect_criterion_direction_conflicts(observations, "R001", START, END)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.criterion_key == "missed_reply"
    assert {candidate.observation_a_id, candidate.observation_b_id} == {
        "O001",
        "O002",
    }
    assert {candidate.relationship_a_id, candidate.relationship_b_id} == {
        "R001",
        "R002",
    }


def test_criterion_comparison_ignores_non_comparable_rows() -> None:
    observations = [
        _obs(
            "O001",
            "2026-08-10T00:00:00+00:00",
            relationship_id="R002",
            criterion_key="reply",
            direction=JudgmentDirection.WEAKENS_TRUST,
        ),
        _obs(
            "O002",
            "2026-08-11T00:00:00+00:00",
            relationship_id="R003",
            criterion_key="reply",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        ),
        _obs(
            "O003",
            "2026-08-12T00:00:00+00:00",
            criterion_key="reply",
            direction=JudgmentDirection.NEUTRAL,
        ),
        _obs(
            "O004",
            "2026-08-13T00:00:00+00:00",
            criterion_key="different",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        ),
        _obs(
            "O005",
            "2026-07-01T00:00:00+00:00",
            criterion_key="reply",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        ),
        _obs(
            "O006",
            "2026-08-14T00:00:00+00:00",
            criterion_key="same-direction",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        ),
        _obs(
            "O007",
            "2026-08-15T00:00:00+00:00",
            relationship_id="R002",
            criterion_key="same_direction",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        ),
    ]
    assert detect_criterion_direction_conflicts(observations, "R001", START, END) == []


def test_same_relationship_opposite_directions_are_reviewable() -> None:
    observations = [
        _obs(
            "O001",
            "2026-08-10T00:00:00+00:00",
            criterion_key="reply",
            direction=JudgmentDirection.WEAKENS_TRUST,
        ),
        _obs(
            "O002",
            "2026-08-11T00:00:00+00:00",
            criterion_key="reply",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        ),
    ]
    assert (
        len(detect_criterion_direction_conflicts(observations, "R001", START, END)) == 1
    )


def test_audit_order_and_no_decision_impact() -> None:
    state_history = [
        _state("SH001", "2026-08-01T00:00:00+00:00", 2.0),
        _state("SH002", "2026-08-02T00:00:00+00:00", 5.0),
    ]
    observations = [
        _obs(
            "O001",
            "2026-08-03T00:00:00+00:00",
            interpretation="one-sided",
            rationalization=True,
            criterion_key="reply",
            direction=JudgmentDirection.WEAKENS_TRUST,
        ),
        _obs("O002", "2026-08-04T00:00:00+00:00", rationalization=True),
        _obs("O003", "2026-08-05T00:00:00+00:00", rationalization=True),
    ]
    all_observations = observations + [
        _obs(
            "O004",
            "2026-08-06T00:00:00+00:00",
            relationship_id="R002",
            criterion_key="reply",
            direction=JudgmentDirection.SUPPORTS_TRUST,
        )
    ]
    findings = audit_consistency(
        target_relationship_id="R001",
        state_history=state_history,
        observations=observations,
        all_observations=all_observations,
        evidence_timestamps=[o.timestamp for o in observations],
        unresolved_structured_count=1,
        start=START,
        end=END,
    )
    assert [finding.rule_id for finding in findings] == [
        "trust_change_without_new_evidence",
        "interpretation_without_alternative",
        "self_reported_rationalization_run",
        "unresolved_structured_conflicts",
        "criterion_direction_conflict",
    ]
    assert all(finding.proposed_decision is None for finding in findings)


def test_service_assembles_both_audit_stages(tmp_path, monkeypatch) -> None:
    import love_risk_engine.storage.database as database_module

    db = Database(str(tmp_path / "audit.db"))
    try:
        db.init()
        rid = db.add_relationship("Alex")
        other_rid = db.add_relationship("Sam")
        monkeypatch.setattr(
            database_module, "_now", lambda: "2026-08-01T00:00:00+00:00"
        )
        from love_risk_engine.core.state import RelationshipState

        db.upsert_state(RelationshipState(rid, trust=2.0))
        monkeypatch.setattr(
            database_module, "_now", lambda: "2026-08-02T00:00:00+00:00"
        )
        db.upsert_state(RelationshipState(rid, trust=5.0))
        db.add_observation(
            rid,
            "general",
            "no reply",
            "does not care",
            "",
            "self",
            5.0,
            criterion_key="reply",
            judgment_direction=JudgmentDirection.WEAKENS_TRUST,
            timestamp="2026-08-03T00:00:00+00:00",
        )
        db.add_observation(
            other_rid,
            "general",
            "no reply",
            "giving space",
            "might be busy",
            "self",
            5.0,
            criterion_key="reply",
            judgment_direction=JudgmentDirection.SUPPORTS_TRUST,
            timestamp="2026-08-04T00:00:00+00:00",
        )
        db.save_contradiction_candidate(
            rid, "status", "single", "married", "O010", "O011"
        )

        report = run_consistency_audit(
            db, rid, days=30, now="2026-09-01T00:00:00+00:00"
        )
        rule_ids = [finding.rule_id for finding in report.findings]
        assert "trust_change_without_new_evidence" in rule_ids
        assert "interpretation_without_alternative" in rule_ids
        assert "unresolved_structured_conflicts" in rule_ids
        assert "criterion_direction_conflict" in rule_ids
        assert report.start == "2026-08-02T00:00:00+00:00"
        assert report.end == "2026-09-01T00:00:00+00:00"
    finally:
        db.close()


@pytest.mark.parametrize(
    "relationship_id, days, now, message",
    [
        ("R001", 0, END, "positive integer"),
        ("R999", 30, END, "not found"),
        ("R001", 30, "not-a-time", "valid ISO-8601"),
    ],
)
def test_service_rejects_invalid_inputs(
    tmp_path, relationship_id, days, now, message
) -> None:
    db = Database(str(tmp_path / "invalid.db"))
    try:
        db.init()
        db.add_relationship("Alex")
        with pytest.raises(ValueError, match=message):
            run_consistency_audit(db, relationship_id, days=days, now=now)
    finally:
        db.close()


def test_service_counts_verification_transition_as_new_evidence(
    tmp_path, monkeypatch
) -> None:
    import love_risk_engine.storage.database as database_module
    from love_risk_engine.core.state import RelationshipState

    db = Database(str(tmp_path / "verification.db"))
    try:
        db.init()
        rid = db.add_relationship("Alex")
        monkeypatch.setattr(
            database_module, "_now", lambda: "2026-08-01T00:00:00+00:00"
        )
        db.upsert_state(RelationshipState(rid, trust=2.0))
        item_id = db.add_verification_item(rid, "met friends")
        monkeypatch.setattr(
            database_module, "_now", lambda: "2026-08-02T00:00:00+00:00"
        )
        db.set_verification_status(item_id, "verified")
        monkeypatch.setattr(
            database_module, "_now", lambda: "2026-08-03T00:00:00+00:00"
        )
        db.upsert_state(RelationshipState(rid, trust=5.0))

        report = run_consistency_audit(db, rid, days=30, now=END)
        assert "trust_change_without_new_evidence" not in {
            finding.rule_id for finding in report.findings
        }
    finally:
        db.close()
