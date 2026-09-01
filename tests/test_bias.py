from love_risk_engine.core.bias_detector import (
    Sensitivity,
    attraction_exceeds_trust,
    exposure_outpaces_evidence,
    high_emotion_major_decision,
    repeated_rationalization,
    unresolved_inconsistencies,
)
from love_risk_engine.core.evidence import compute_evidence_support
from love_risk_engine.core.exposure import Exposure
from love_risk_engine.core.observation import Observation
from love_risk_engine.core.state import EmotionalState, RelationshipState


def _obs(ts, rationalization=False, inconsistency=False):
    return Observation(
        id=f"O{ts}",
        relationship_id="R001",
        timestamp=f"2026-01-01T00:0{ts}:00",
        category="x",
        observation="o",
        interpretation="i",
        alternative_explanation="a",
        source="self",
        confidence=5.0,
        rationalization=rationalization,
        inconsistency_flag=inconsistency,
    )


def test_attraction_exceeds_trust_fires():
    st = RelationshipState("R001", attraction=9, trust=3)
    f = attraction_exceeds_trust(st, [_obs(1)])
    assert f is not None
    assert f.rule_id == "attraction_exceeds_trust"
    assert f.msg_key == "attraction_exceeds_trust"  # localizable by key


def test_attraction_exceeds_trust_silent_when_evidence_present():
    st = RelationshipState("R001", attraction=9, trust=3)
    obs = [_obs(i) for i in range(1, 5)]  # 4 observations => enough evidence
    assert attraction_exceeds_trust(st, obs) is None


def test_attraction_exceeds_trust_silent_when_gap_small():
    st = RelationshipState("R001", attraction=5, trust=4)
    assert attraction_exceeds_trust(st, [_obs(1)]) is None


def test_repeated_rationalization_fires():
    obs = [_obs(i, rationalization=True) for i in range(1, 4)]
    f = repeated_rationalization(obs)
    assert f is not None and f.rule_id == "repeated_rationalization"


def test_repeated_rationalization_resets_on_gap():
    obs = [
        _obs(1, rationalization=True),
        _obs(2, rationalization=True),
        _obs(3, rationalization=False),
        _obs(4, rationalization=True),
    ]
    assert repeated_rationalization(obs) is None


def test_exposure_outpaces_evidence_fires():
    exp = Exposure("R001", time=5, emotional=5)  # total 10
    support = compute_evidence_support([_obs(1)])  # 1 obs, support ~3.5
    f = exposure_outpaces_evidence(exp, support)
    assert f.severity > 0 and f.proposed_decision == "DECREASE_EXPOSURE"


def test_exposure_within_support_is_info():
    exp = Exposure("R001", time=1)
    support = compute_evidence_support([_obs(1)])
    f = exposure_outpaces_evidence(exp, support)
    assert f.severity == 0 and f.proposed_decision is None
    assert "within" in f.message


def test_exposure_no_observations_is_info():
    exp = Exposure("R001", time=3)
    support = compute_evidence_support([])
    f = exposure_outpaces_evidence(exp, support)
    assert f.severity == 0
    assert "empty" in f.message


def test_high_emotion_major_decision_fires():
    st = RelationshipState("R001", emotional_state=EmotionalState.OVERWHELMED)
    exp = Exposure("R001", life_decision=4)
    f = high_emotion_major_decision(st, exp)
    assert f is not None and f.proposed_decision == "PAUSE"


def test_high_emotion_no_major_decision_silent():
    st = RelationshipState("R001", emotional_state=EmotionalState.ANXIOUS)
    exp = Exposure("R001")  # life_decision = 0
    assert high_emotion_major_decision(st, exp) is None


def test_unresolved_inconsistencies():
    assert unresolved_inconsistencies(2).severity == 3
    assert unresolved_inconsistencies(0) is None


# ---------------------------------------------------------------------------
# exit-cost sensitivity (relationship-kinds proposal, S3)
# ---------------------------------------------------------------------------


def test_attraction_high_exit_cost_fires_earlier():
    st = RelationshipState("R001", attraction=8.5, trust=6)  # gap 2.5
    obs = [_obs(1)]  # fewer than MIN_OBSERVATIONS_FOR_TRUST
    assert attraction_exceeds_trust(st, obs) is None  # NORMAL: 2.5 < 3.0
    f = attraction_exceeds_trust(st, obs, sensitivity=Sensitivity.HIGH_EXIT_COST)
    assert f is not None
    assert f.rule_id == "attraction_exceeds_trust"


def test_attraction_shifted_message_states_threshold():
    st = RelationshipState("R001", attraction=8.5, trust=6)
    f = attraction_exceeds_trust(st, [_obs(1)], sensitivity=Sensitivity.HIGH_EXIT_COST)
    assert "gap threshold 2.0" in f.message
    assert "exit-cost sensitive" in f.message


def test_attraction_normal_message_unchanged():
    st = RelationshipState("R001", attraction=9, trust=3)
    f = attraction_exceeds_trust(st, [_obs(1)])
    assert "exit-cost" not in f.message
    assert f.message.startswith(
        "Attraction (9.0) significantly exceeds supported trust (3.0)."
    )


def test_rationalization_high_exit_cost_fires_earlier():
    obs = [_obs(1, rationalization=True), _obs(2, rationalization=True)]
    assert repeated_rationalization(obs) is None  # NORMAL: needs a run of 3
    f = repeated_rationalization(obs, sensitivity=Sensitivity.HIGH_EXIT_COST)
    assert f is not None
    assert "run threshold 2" in f.message
