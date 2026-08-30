from love_risk_engine.core.observation import Observation
from love_risk_engine.core.patterns import (
    EARLY_WINDOW_OBSERVATIONS,
    MIN_CHEAP_FOR_LOVE_BOMBING,
    MIN_COSTLY_FOR_LOVE_BOMBING,
    MIN_TOTAL_SIGNALS,
    detect_love_bombing,
)
from love_risk_engine.core.signals import SignalType


def _obs(idx, signal=SignalType.UNSPECIFIED):
    return Observation(
        id=f"O{idx:03d}", relationship_id="R001",
        timestamp=f"2026-01-{idx:02d}T10:00:00",
        category="x", observation="o", interpretation="i",
        alternative_explanation="a", source="self", confidence=5.0,
        signal_type=signal,
    )


def test_no_observations_returns_none():
    assert detect_love_bombing([]) is None


def test_fires_on_early_cheap_plus_costly_cluster():
    # 3 cheap + 2 costly in the first 5 observations => love bombing
    obs = [
        _obs(1, SignalType.CHEAP),
        _obs(2, SignalType.CHEAP),
        _obs(3, SignalType.CHEAP),
        _obs(4, SignalType.COSTLY),
        _obs(5, SignalType.COSTLY),
    ]
    f = detect_love_bombing(obs)
    assert f is not None
    assert f.rule_id == "love_bombing_pattern"
    assert f.proposed_decision == "PAUSE"


def test_silent_when_only_cheap_no_costly():
    # cheap talk alone is just enthusiasm, not love bombing (no costly pairing)
    obs = [_obs(i, SignalType.CHEAP) for i in range(1, 6)]
    assert detect_love_bombing(obs) is None


def test_silent_when_only_costly_no_cheap():
    # costly gestures without the cheap-talk burst is just moving fast
    obs = [_obs(i, SignalType.COSTLY) for i in range(1, 6)]
    assert detect_love_bombing(obs) is None


def test_silent_when_too_few_total_signals():
    # 3 cheap but only 3 total (< MIN_TOTAL_SIGNALS=5)
    obs = [
        _obs(1, SignalType.CHEAP),
        _obs(2, SignalType.CHEAP),
        _obs(3, SignalType.CHEAP),
        _obs(4, SignalType.UNSPECIFIED),
        _obs(5, SignalType.UNSPECIFIED),
    ]
    assert detect_love_bombing(obs) is None


def test_only_early_window_matters():
    # 5 cheap + 5 costly, but all AFTER the first EARLY_WINDOW observations
    # (we add 10 unspecified first to push them out of the window)
    head = [_obs(i, SignalType.UNSPECIFIED) for i in range(1, 11)]
    tail = [
        _obs(11, SignalType.CHEAP),
        _obs(12, SignalType.CHEAP),
        _obs(13, SignalType.CHEAP),
        _obs(14, SignalType.COSTLY),
        _obs(15, SignalType.COSTLY),
    ]
    assert detect_love_bombing(head + tail) is None


def test_thresholds_are_documented_placeholders():
    # sanity: keep test in sync with module constants
    assert EARLY_WINDOW_OBSERVATIONS == 10
    assert MIN_CHEAP_FOR_LOVE_BOMBING == 3
    assert MIN_COSTLY_FOR_LOVE_BOMBING == 1
    assert MIN_TOTAL_SIGNALS == 5
