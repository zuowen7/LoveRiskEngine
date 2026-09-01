"""Property-based tests for timeutil invariants (stdlib only, no hypothesis).

These exercise the *contract* of timeutil on randomized inputs: coverage
measures which lines ran; properties measure which invariants hold across
arbitrary valid input. A fixed seed makes failures reproducible.

Why stdlib not hypothesis: the audit flagged hypothesis as a research
investment, but pulling a new dev dep re-triggers the dependency hell that
just cost us mypy + coverage (RECORD churn from force-reinstalls). These
property checks use only `random` and cover the same ground for timeutil's
core invariants — parse_iso never returns naive, is_future matches instant
comparison, strict ordering is antisymmetric, and re-parsing never drifts.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from love_risk_engine.core.timeutil import is_future, parse_iso

_SEED = 20260901
_N = 200


def _random_iso(rng: random.Random) -> str:
    """Generate a random valid ISO-8601 timestamp with an explicit UTC offset."""
    base = datetime(2020, 1, 1, tzinfo=UTC)
    delta = timedelta(seconds=rng.randint(0, 10 * 365 * 24 * 3600))
    return (base + delta).isoformat(timespec="seconds")


def test_parse_iso_never_returns_naive():
    """Invariant: parse_iso either returns None or a tz-aware datetime.

    A naive return would silently break every downstream comparison (timelines
    sort by string; a naive datetime formats differently from an aware one).
    """
    rng = random.Random(_SEED)
    for _ in range(_N):
        parsed = parse_iso(_random_iso(rng))
        assert parsed is None or parsed.tzinfo is not None


def test_is_future_matches_instant_comparison():
    """Invariant: is_future(value, now) == (parse_iso(value) > parse_iso(now))
    when both parse — string comparison is never used, so mixed offsets and
    legacy naive values compare correctly."""
    rng = random.Random(_SEED)
    for _ in range(_N):
        a = _random_iso(rng)
        b = _random_iso(rng)
        pa = parse_iso(a)
        pb = parse_iso(b)
        assert pa is not None and pb is not None
        assert is_future(a, now=b) == (pa > pb)


def test_is_future_is_antisymmetric():
    """Invariant: for two distinct instants, exactly one of
    is_future(a, now=b) / is_future(b, now=a) holds — strict ordering, never
    both-true (which would let an expired cooldown look live AND dead)."""
    rng = random.Random(_SEED + 1)
    for _ in range(_N):
        a = _random_iso(rng)
        b = _random_iso(rng)
        if parse_iso(a) != parse_iso(b):
            assert is_future(a, now=b) != is_future(b, now=a)


def test_parse_iso_round_trips_instant():
    """Invariant: parse_iso(x).isoformat() re-parses to the same instant —
    re-serialization never drifts, so a cooldown written and re-read never
    silently moves in time."""
    rng = random.Random(_SEED + 2)
    for _ in range(_N):
        ts = _random_iso(rng)
        parsed = parse_iso(ts)
        assert parsed is not None
        reparsed = parse_iso(parsed.isoformat(timespec="seconds"))
        assert reparsed is not None
        assert reparsed == parsed
