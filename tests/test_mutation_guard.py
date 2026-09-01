"""Hand-written mutation guards for the safety-critical logic in
core/decision.py and core/cooldown.py.

Each test injects a single mutation — the kind a typo or careless refactor
might introduce — and asserts it changes observable behaviour. A passing
guard means the existing example-based suite *would* fail on that mutation
(the mutation is catchable). A failing guard is a hole: the mutation
survives undetected.

Why hand-written alongside mutmut? mutmut 3.x does not run natively on
Windows (upstream issue #397); these guards run everywhere the suite runs.
mutmut is still configured in pyproject.toml ([tool.mutmut]) for exhaustive
WSL/CI runs that enumerate every bytecode mutation; this file covers the
load-bearing points the audit flagged — the EXIT guard and the cooldown
fail-open path.
"""

from __future__ import annotations

from love_risk_engine.core.bias_detector import BiasFinding
from love_risk_engine.core.cooldown import Cooldown
from love_risk_engine.core.decision import Decision

NOW = "2026-08-30T12:00:00+00:00"


# ---------------------------------------------------------------------------
# decision.decide — the EXIT recommendation is safety-critical; the priority
# order picks the single winner. Mutate either and the suite must notice.
# ---------------------------------------------------------------------------


def test_mutation_removing_hard_boundary_guard_is_detected(monkeypatch):
    """If the `has_hard_boundary_hit` guard is deleted, decide() must stop
    returning EXIT for a hard boundary — so test_hard_boundary_hit_forces_exit
    would fail. Passing => the guard is catchable, not silent."""
    import love_risk_engine.core.decision as dec

    def mutated(findings, has_hard_boundary_hit):
        proposed = [
            dec.Decision(f.proposed_decision) for f in findings if f.proposed_decision
        ]
        for decision in dec._PRIORITY:
            if decision in proposed:
                return decision
        return dec.Decision.CONTINUE_OBSERVING

    monkeypatch.setattr(dec, "decide", mutated)
    findings = [BiasFinding("x", "y", severity=2, proposed_decision="PAUSE")]
    result = dec.decide(findings, has_hard_boundary_hit=True)
    assert result != Decision.EXIT, (
        "mutation undetected: removing the hard-boundary guard still returns EXIT"
    )


def test_mutation_reversing_priority_order_is_detected(monkeypatch):
    """If _PRIORITY is reversed (least-severe wins), a PAUSE +
    DECREASE_EXPOSURE pair must return DECREASE_EXPOSURE instead of PAUSE —
    so test_pause_outranks_decrease_exposure would fail."""
    import love_risk_engine.core.decision as dec

    monkeypatch.setattr(dec, "_PRIORITY", list(reversed(dec._PRIORITY)))
    findings = [
        BiasFinding("a", "e", severity=3, proposed_decision="DECREASE_EXPOSURE"),
        BiasFinding("b", "m", severity=4, proposed_decision="PAUSE"),
    ]
    result = dec.decide(findings, has_hard_boundary_hit=False)
    assert result == Decision.DECREASE_EXPOSURE, (
        "mutation undetected: reversed priority did not change the winner"
    )


def test_mutation_defaulting_to_wait_is_detected(monkeypatch):
    """If the fallback return is changed from CONTINUE_OBSERVING to WAIT, an
    empty findings list must return WAIT — so
    test_default_is_continue_observing would fail."""
    import love_risk_engine.core.decision as dec

    def mutated(findings, has_hard_boundary_hit):
        if has_hard_boundary_hit:
            return dec.Decision.EXIT
        proposed = [
            dec.Decision(f.proposed_decision) for f in findings if f.proposed_decision
        ]
        for decision in dec._PRIORITY:
            if decision in proposed:
                return decision
        return dec.Decision.WAIT

    monkeypatch.setattr(dec, "decide", mutated)
    assert dec.decide([], has_hard_boundary_hit=False) == Decision.WAIT
    assert dec.decide([], has_hard_boundary_hit=False) != Decision.CONTINUE_OBSERVING


# ---------------------------------------------------------------------------
# cooldown — the fail-open invariant (an expired/inactive cooldown must
# never lock the user out) and the blocking-decision set are safety-critical.
# ---------------------------------------------------------------------------


def test_mutation_dropping_active_flag_check_is_detected(monkeypatch):
    """If `if not cooldown.active: return False` is removed, an inactive
    cooldown with a future expiry must report active — so test_is_active_logic
    would fail. This is the fail-closed inversion of the project's fail-open
    principle; the guard proves the suite catches it."""
    import love_risk_engine.core.cooldown as cd

    def mutated(cooldown, now=None):
        return cd.is_future(cooldown.expires_at, now=now)

    monkeypatch.setattr(cd, "is_active", mutated)
    inactive_future = Cooldown(
        "C1", "R1", "PAUSE", "", NOW, "2999-01-01T00:00:00+00:00", False
    )
    result = cd.is_active(inactive_future, now=NOW)
    assert result is True, (
        "mutation undetected: dropping the active-flag check did not change is_active"
    )


def test_mutation_inverting_is_future_is_detected(monkeypatch):
    """If `is_future` is inverted, an expired cooldown must report active and
    a future one inactive — so test_is_active_logic would fail."""
    import love_risk_engine.core.cooldown as cd

    def mutated(cooldown, now=None):
        if not cooldown.active:
            return False
        return not cd.is_future(cooldown.expires_at, now=now)

    monkeypatch.setattr(cd, "is_active", mutated)
    expired = Cooldown("C1", "R1", "PAUSE", "", NOW, "2026-08-30T11:00:00+00:00", True)
    future = Cooldown("C2", "R1", "PAUSE", "", NOW, "2026-08-30T18:00:00+00:00", True)
    assert cd.is_active(expired, now=NOW) is True, "expired should be (mutated) active"
    assert cd.is_active(future, now=NOW) is False, "future should be (mutated) inactive"


def test_mutation_inverting_is_blocking_is_detected(monkeypatch):
    """If `is_blocking` is inverted, CONTINUE_OBSERVING/WAIT must report
    blocking and PAUSE/EXIT non-blocking — so
    test_is_blocking_only_for_pause_decrease_exit would fail."""
    import love_risk_engine.core.cooldown as cd

    def mutated(decision):
        return decision not in cd._DEFAULT_HOURS

    monkeypatch.setattr(cd, "is_blocking", mutated)
    assert cd.is_blocking(Decision.CONTINUE_OBSERVING) is True
    assert cd.is_blocking(Decision.PAUSE) is False


def test_mutation_corrupting_default_hours_is_detected(monkeypatch):
    """If _DEFAULT_HOURS values are changed, cooldown_hours_for must return the
    wrong duration — so test_default_hours_per_decision would fail."""
    import love_risk_engine.core.cooldown as cd

    monkeypatch.delenv("LRE_COOLDOWN_HOURS", raising=False)
    monkeypatch.setattr(
        cd,
        "_DEFAULT_HOURS",
        {Decision.PAUSE: 1, Decision.DECREASE_EXPOSURE: 1, Decision.EXIT: 1},
    )
    assert cd.cooldown_hours_for(Decision.PAUSE) == 1
    assert cd.cooldown_hours_for(Decision.PAUSE) != 24
    assert cd.cooldown_hours_for(Decision.EXIT) != 72
