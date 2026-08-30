from love_risk_engine.core.evidence import EvidenceSupport, compute_evidence_support
from love_risk_engine.core.observation import Claim, Observation
from love_risk_engine.core.signals import SignalType


def _obs(alt="", source="self", claims=None, confidence=5.0, signal=SignalType.UNSPECIFIED):
    return Observation(
        id="O1", relationship_id="R001", timestamp="2026-01-01T00:00:00",
        category="x", observation="o", interpretation="i",
        alternative_explanation=alt, source=source, confidence=confidence,
        claims=claims or [], signal_type=signal,
    )


def test_empty_support():
    s = compute_evidence_support([])
    assert s.observation_count == 0
    assert s.support_units == 0.0
    assert s.rigor_ratio == 0.0
    assert s.costly_count == 0 and s.cheap_count == 0


def test_confidence_weight_neutral_at_5():
    # one observation, confidence=5, unspecified signal -> weight 1.0
    s = compute_evidence_support([_obs(confidence=5.0)])
    # base = 2.0 * (0.5+0.5) * 1.0 = 2.0
    assert abs(s.support_units - 2.0) < 1e-9


def test_costly_signal_weighs_more_than_cheap():
    costly = compute_evidence_support([_obs(signal=SignalType.COSTLY)])
    cheap = compute_evidence_support([_obs(signal=SignalType.CHEAP)])
    unspecified = compute_evidence_support([_obs(signal=SignalType.UNSPECIFIED)])
    # all confidence=5 -> conf_weight 1.0; base 2.0 * weight
    assert abs(costly.support_units - 4.0) < 1e-9   # 2.0 * 2.0
    assert abs(cheap.support_units - 1.0) < 1e-9    # 2.0 * 0.5
    assert abs(unspecified.support_units - 2.0) < 1e-9
    assert costly.support_units > unspecified.support_units > cheap.support_units


def test_support_rewards_rigor_and_claims_and_signals():
    obs = [
        _obs(alt="other reading", claims=[Claim("job", "barista")], signal=SignalType.COSTLY),
        _obs(alt="maybe neutral"),
        _obs(source="friend", alt="", claims=[Claim("city", "Berlin")]),
    ]
    s = compute_evidence_support(obs)
    assert s.observation_count == 3
    assert s.distinct_sources == 2
    assert s.with_alternative == 2
    assert s.with_claims == 2
    assert s.costly_count == 1
    assert s.cheap_count == 0
    # o1: 2.0 * 1.0 * 2.0 = 4.0
    # o2: 2.0 * 1.0 * 1.0 = 2.0
    # o3: 2.0 * 1.0 * 1.0 = 2.0  (unspecified)
    # base = 8.0; triangulation 0.5*(2-1)=0.5; rigor 2*1=2; concreteness 2*1=2
    # total = 12.5
    assert abs(s.support_units - 12.5) < 1e-9


def test_low_confidence_halves_contribution():
    s_low = compute_evidence_support([_obs(confidence=0.0)])   # conf_weight 0.5
    s_high = compute_evidence_support([_obs(confidence=10.0)]) # conf_weight 1.5
    assert s_low.support_units < s_high.support_units
    # 2.0*0.5 vs 2.0*1.5
    assert abs(s_low.support_units - 1.0) < 1e-9
    assert abs(s_high.support_units - 3.0) < 1e-9
