"""Rapid exposure escalation detector tests (roadmap #1 follow-up).

Written test-first per PLAN_rapid_escalation.md: these fail until
core/escalation.py exists, then pin the exact semantics — 2-day window, +3.0
threshold, zero-new-evidence pairing, baseline carry-forward and fail-open.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from love_risk_engine.core.escalation import detect_rapid_exposure_escalation
from love_risk_engine.core.history import ExposureChange
from love_risk_engine.core.observation import Observation

NOW = "2026-09-01T00:00:00+00:00"


def _days_ago(days: float) -> str:
    return (datetime.fromisoformat(NOW) - timedelta(days=days)).isoformat(
        timespec="seconds"
    )


def _exp(oid: str, days_ago: float, total: float) -> ExposureChange:
    return ExposureChange(
        id=oid,
        relationship_id="R001",
        timestamp=_days_ago(days_ago),
        time=total,
        emotional=0.0,
        privacy=0.0,
        financial=0.0,
        life_decision=0.0,
    )


def _obs(oid: str, days_ago: float) -> Observation:
    return Observation(
        id=oid,
        relationship_id="R001",
        timestamp=_days_ago(days_ago),
        category="general",
        observation="o",
        interpretation="i",
        alternative_explanation="a",
        source="self",
        confidence=5.0,
    )


def test_fires_when_exposure_grew_in_window_without_observations():
    history = [_exp("EH001", 3.0, 2.0), _exp("EH002", 1.0, 5.5)]
    f = detect_rapid_exposure_escalation(history, [], now=NOW)
    assert f is not None
    assert f.rule_id == "rapid_exposure_escalation"
    assert f.proposed_decision == "PAUSE"


def test_silent_when_an_observation_exists_in_window():
    history = [_exp("EH001", 3.0, 2.0), _exp("EH002", 1.0, 5.5)]
    obs = [_obs("O001", 0.5)]
    assert detect_rapid_exposure_escalation(history, obs, now=NOW) is None


def test_silent_when_growth_below_threshold():
    history = [_exp("EH001", 3.0, 2.0), _exp("EH002", 1.0, 4.5)]
    assert detect_rapid_exposure_escalation(history, [], now=NOW) is None


def test_silent_when_growth_predates_window():
    # Latest snapshot is 3 days old — nothing happened inside the 2-day window.
    history = [_exp("EH001", 5.0, 2.0), _exp("EH002", 3.0, 5.5)]
    assert detect_rapid_exposure_escalation(history, [], now=NOW) is None


def test_silent_without_exposure_history():
    assert detect_rapid_exposure_escalation([], [], now=NOW) is None


def test_series_started_inside_window_uses_earliest_row_as_baseline():
    history = [_exp("EH001", 1.0, 0.0), _exp("EH002", 0.5, 5.0)]
    f = detect_rapid_exposure_escalation(history, [], now=NOW)
    assert f is not None


def test_baseline_is_latest_snapshot_at_or_before_cutoff():
    # 0.5 was written just before the window; the 3-day-old 0.0 must be ignored.
    history = [
        _exp("EH001", 3.0, 0.0),
        _exp("EH002", 2.5, 0.5),
        _exp("EH003", 1.0, 5.0),
    ]
    f = detect_rapid_exposure_escalation(history, [], now=NOW)
    assert f is not None
    assert "0.5 -> 5.0" in f.message


def test_fails_open_on_malformed_timestamps():
    bad = ExposureChange(
        id="EH000",
        relationship_id="R001",
        timestamp="not-a-date",
        time=999.0,
        emotional=0.0,
        privacy=0.0,
        financial=0.0,
        life_decision=0.0,
    )
    history = [bad, _exp("EH001", 3.0, 2.0), _exp("EH002", 1.0, 5.5)]
    f = detect_rapid_exposure_escalation(history, [], now=NOW)
    assert f is not None  # the un-datable row is skipped, the valid pair fires


def test_fails_open_when_every_row_is_un_datable():
    bad = ExposureChange(
        id="EH000",
        relationship_id="R001",
        timestamp="not-a-date",
        time=999.0,
        emotional=0.0,
        privacy=0.0,
        financial=0.0,
        life_decision=0.0,
    )
    assert detect_rapid_exposure_escalation([bad], [], now=NOW) is None


def test_fails_open_when_now_is_unparseable():
    history = [_exp("EH001", 3.0, 2.0), _exp("EH002", 1.0, 5.5)]
    assert detect_rapid_exposure_escalation(history, [], now="garbage") is None


def test_un_datable_observation_is_skipped():
    history = [_exp("EH001", 3.0, 2.0), _exp("EH002", 1.0, 5.5)]
    bad_obs = Observation(
        id="O000",
        relationship_id="R001",
        timestamp="not-a-date",
        category="general",
        observation="o",
        interpretation="i",
        alternative_explanation="a",
        source="self",
        confidence=5.0,
    )
    f = detect_rapid_exposure_escalation(history, [bad_obs], now=NOW)
    assert f is not None  # un-datable evidence cannot count as "evidence grew"


def test_message_states_window_delta_and_evidence():
    history = [_exp("EH001", 3.0, 3.0), _exp("EH002", 1.0, 8.0)]
    f = detect_rapid_exposure_escalation(history, [], now=NOW)
    assert f is not None
    assert f.message == (
        "Exposure grew 5.0 points in the last 2 days (3.0 -> 8.0) with no "
        "new observations recorded in that window."
    )
