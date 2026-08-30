from love_risk_engine.core.bias_detector import BiasFinding
from love_risk_engine.core.decision import Decision, decide


def test_default_is_continue_observing():
    assert decide([], has_hard_boundary_hit=False) == Decision.CONTINUE_OBSERVING


def test_hard_boundary_hit_forces_exit():
    findings = [BiasFinding("x", "y", severity=2, proposed_decision="PAUSE")]
    assert decide(findings, has_hard_boundary_hit=True) == Decision.EXIT


def test_highest_severity_wins():
    findings = [
        BiasFinding("a", "low", severity=2, proposed_decision="CONTINUE_OBSERVING"),
        BiasFinding("b", "mid", severity=3, proposed_decision="DECREASE_EXPOSURE"),
    ]
    assert decide(findings, has_hard_boundary_hit=False) == Decision.DECREASE_EXPOSURE


def test_pause_outranks_decrease_exposure():
    findings = [
        BiasFinding("exposure", "e", severity=3, proposed_decision="DECREASE_EXPOSURE"),
        BiasFinding("emotion", "m", severity=4, proposed_decision="PAUSE"),
    ]
    assert decide(findings, has_hard_boundary_hit=False) == Decision.PAUSE
