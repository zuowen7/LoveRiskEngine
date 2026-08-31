"""Time handling is easy to get subtly wrong, so it is tested directly.

Everything here is UTC with an explicit offset. The engine sorts events by
timestamp string, and compares cooldown expiries against "now"; both break if
a producer ever emits naive local time.
"""

from love_risk_engine.core.timeutil import (
    expires_utc_iso,
    is_future,
    parse_iso,
    utc_now_iso,
)


def test_utc_now_carries_an_explicit_offset():
    now = utc_now_iso()
    assert "+00:00" in now
    parsed = parse_iso(now)
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_expires_is_further_in_the_future_than_now():
    now = utc_now_iso()
    later = expires_utc_iso(24)
    assert later > now
    assert is_future(later, now=now)


def test_is_future_rejects_past_and_malformed_values():
    now = utc_now_iso()
    past = "2020-01-01T00:00:00+00:00"
    assert not is_future(past, now=now)
    assert not is_future("", now=now)
    assert not is_future("not-a-timestamp", now=now)


def test_naive_timestamps_are_treated_as_utc():
    """Legacy rows written without an offset must still compare correctly."""
    parsed = parse_iso("2026-08-30T10:00:00")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_mixed_offsets_compare_by_instant_not_by_string():
    """+00:00 and +08:00 describing the same instant compare as equal."""
    same_instant_utc = "2026-08-30T10:00:00+00:00"
    same_instant_shanghai = "2026-08-30T18:00:00+08:00"
    assert same_instant_shanghai > same_instant_utc  # string compare is wrong
    assert parse_iso(same_instant_shanghai) == parse_iso(same_instant_utc)


def test_parse_iso_returns_none_for_empty_or_invalid():
    assert parse_iso("") is None
    assert parse_iso("garbage") is None
