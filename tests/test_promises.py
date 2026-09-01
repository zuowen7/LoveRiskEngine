"""Promise-expiry detector tests (relationship-kinds proposal, S2).

Written test-first per PLAN_S2_S3.md: these fail until `core/promises.py`
exists, then pin its exact semantics — future-directed lexicon, latest-mention
governance, window split, fail-open behaviour, and the auditable WAIT finding.
"""

from __future__ import annotations

from love_risk_engine.core.observation import Claim, Observation
from love_risk_engine.core.promises import (
    collect_promises,
    collect_repromises,
    detect_expired_promises,
    detect_repeated_repromises,
    is_future_directed,
)

NOW = "2026-09-01T00:00:00+00:00"


def _obs(oid: str, ts: str, *claims: tuple[str, str]) -> Observation:
    return Observation(
        id=oid,
        relationship_id="R001",
        timestamp=ts,
        category="general",
        observation="o",
        interpretation="i",
        alternative_explanation="a",
        source="self",
        confidence=5.0,
        claims=[Claim(attribute=a, value=v) for a, v in claims],
    )


# ---------------------------------------------------------------------------
# lexicon
# ---------------------------------------------------------------------------


def test_is_future_directed_matches_lexicon():
    assert is_future_directed("will fund the trip")
    assert is_future_directed("promised to pay me back")
    assert is_future_directed("by the end of 2026")
    assert is_future_directed("going to introduce me to her advisor")


def test_is_future_directed_rejects_past_and_bare_words():
    assert not is_future_directed("funded the trip")
    assert not is_future_directed("willpower issues")
    assert not is_future_directed("")
    assert not is_future_directed("recommended me to the lab")


# ---------------------------------------------------------------------------
# collect_promises
# ---------------------------------------------------------------------------


def test_collect_promises_ignores_non_future_claims():
    obs = [_obs("O001", "2026-08-20T00:00:00+00:00", ("funding", "was cut"))]
    report = collect_promises(obs, 90, now=NOW)
    assert report.within == []
    assert report.expired == []


def test_collect_promises_splits_within_and_expired():
    obs = [
        _obs("O001", "2026-08-20T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-04-01T00:00:00+00:00", ("rec", "will recommend me")),
    ]
    report = collect_promises(obs, 90, now=NOW)
    assert [p.attribute for p in report.within] == ["funding"]
    assert [p.attribute for p in report.expired] == ["rec"]
    assert report.expired[0].age_days == 153


def test_collect_promises_latest_mention_governs():
    # re-promised: the window restarts from the newer mention
    obs = [
        _obs("O001", "2026-04-01T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-08-20T00:00:00+00:00", ("funding", "will fund it")),
    ]
    report = collect_promises(obs, 90, now=NOW)
    assert [p.attribute for p in report.within] == ["funding"]
    assert report.expired == []

    # later non-future value: resolved / contradicted — skipped entirely
    resolved = [
        _obs("O001", "2026-04-01T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-08-20T00:00:00+00:00", ("funding", "was delivered")),
    ]
    report2 = collect_promises(resolved, 90, now=NOW)
    assert report2.within == []
    assert report2.expired == []


def test_collect_promises_empty_without_window():
    obs = [_obs("O001", "2026-04-01T00:00:00+00:00", ("funding", "will fund it"))]
    report = collect_promises(obs, None, now=NOW)
    assert report.within == []
    assert report.expired == []
    assert report.window_days is None


def test_collect_promises_skips_empty_claims():
    obs = [
        _obs("O001", "2026-08-20T00:00:00+00:00", ("", "will fund")),
        _obs("O002", "2026-08-20T00:00:00+00:00", ("funding", "")),
    ]
    report = collect_promises(obs, 90, now=NOW)
    assert report.within == []
    assert report.expired == []


def test_collect_promises_fails_open_on_malformed_timestamp():
    obs = [_obs("O001", "not-a-timestamp", ("funding", "will fund it"))]
    report = collect_promises(obs, 90, now=NOW)
    assert report.within == []
    assert report.expired == []


# ---------------------------------------------------------------------------
# detect_expired_promises
# ---------------------------------------------------------------------------


def test_detect_expired_promises_fires_wait_with_audit_details():
    obs = [_obs("O001", "2026-04-01T00:00:00+00:00", ("rec", "will recommend me"))]
    f = detect_expired_promises(obs, 90, now=NOW)
    assert f is not None
    assert f.rule_id == "promise_expiry"
    assert f.proposed_decision == "WAIT"
    assert "90" in f.message
    assert "rec='will recommend me'" in f.message
    assert "O001" in f.message
    assert "2026-04-01" in f.message
    assert "153d" in f.message


def test_detect_expired_promises_caps_at_three_with_count():
    obs = [
        _obs(f"O{i:03d}", "2026-04-01T00:00:00+00:00", (f"attr{i}", "will happen"))
        for i in range(1, 6)
    ]
    f = detect_expired_promises(obs, 90, now=NOW)
    assert f is not None
    assert "5 promise claim(s)" in f.message
    assert "+2 more" in f.message
    assert "attr4" not in f.message  # collapsed into the count


def test_detect_expired_promises_none_when_fresh_or_no_window():
    fresh = [_obs("O001", "2026-08-20T00:00:00+00:00", ("funding", "will fund it"))]
    assert detect_expired_promises(fresh, 90, now=NOW) is None
    assert detect_expired_promises(fresh, None, now=NOW) is None


# ---------------------------------------------------------------------------
# repeated re-promises (phase 2: promise re-promise counting)
# ---------------------------------------------------------------------------


def test_collect_repromises_counts_repeated_future_mentions():
    obs = [
        _obs("O001", "2026-08-01T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-08-10T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O003", "2026-08-20T00:00:00+00:00", ("funding", "will fund it")),
    ]
    repromises = collect_repromises(obs, 90, now=NOW)
    assert [r.attribute for r in repromises] == ["funding"]
    assert repromises[0].count == 3
    assert repromises[0].latest_value == "will fund it"
    assert repromises[0].latest_observation_id == "O003"


def test_collect_repromises_ignores_non_future_mentions():
    obs = [
        _obs("O001", "2026-08-01T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-08-10T00:00:00+00:00", ("funding", "was delivered")),
        _obs("O003", "2026-08-20T00:00:00+00:00", ("funding", "will fund it")),
    ]
    repromises = collect_repromises(obs, 90, now=NOW)
    assert repromises[0].count == 2  # only future-directed mentions count


def test_collect_repromises_ignores_mentions_outside_window():
    obs = [
        _obs("O001", "2026-04-01T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-04-10T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O003", "2026-04-20T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O004", "2026-08-20T00:00:00+00:00", ("funding", "will fund it")),
    ]
    repromises = collect_repromises(obs, 90, now=NOW)
    assert repromises[0].count == 1  # only in-window mentions count


def test_collect_repromises_empty_without_window():
    obs = [_obs("O001", "2026-08-01T00:00:00+00:00", ("funding", "will fund it"))]
    assert collect_repromises(obs, None, now=NOW) == []


def test_detect_repeated_repromises_fires_wait_with_details():
    obs = [
        _obs("O001", "2026-08-01T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-08-10T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O003", "2026-08-20T00:00:00+00:00", ("funding", "will fund it")),
    ]
    f = detect_repeated_repromises(obs, 90, now=NOW)
    assert f is not None
    assert f.rule_id == "repeated_repromises"
    assert f.proposed_decision == "WAIT"
    assert "90" in f.message
    assert "funding x3" in f.message
    assert "'will fund it'" in f.message
    assert "O003" in f.message


def test_detect_repeated_repromises_silent_below_threshold():
    obs = [
        _obs("O001", "2026-08-01T00:00:00+00:00", ("funding", "will fund it")),
        _obs("O002", "2026-08-10T00:00:00+00:00", ("funding", "will fund it")),
    ]
    assert detect_repeated_repromises(obs, 90, now=NOW) is None


def test_detect_repeated_repromises_none_without_window():
    obs = [_obs("O001", "2026-08-01T00:00:00+00:00", ("funding", "will fund it"))]
    assert detect_repeated_repromises(obs, None, now=NOW) is None
