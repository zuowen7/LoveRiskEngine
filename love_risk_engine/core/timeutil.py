"""Single source of truth for time handling.

Rule: every timestamp the engine persists is UTC ISO-8601 with an explicit
offset (e.g. ``2026-08-30T15:59:54+00:00``).

Why it matters here:
  - Timelines are built by *sorting timestamp strings*. Mixing naive local
    time with UTC silently reorders events (a UTC evening can sort before a
    local-time morning of the same day).
  - Cooldowns compare an expiry against "now". String comparison only works
    while every producer formats identically; parsing to ``datetime`` works
    even if a value was written by an older version.
  - Local time is ambiguous across DST transitions; UTC is not.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with an explicit offset."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def expires_utc_iso(hours: int) -> str:
    """Timestamp `hours` from now, UTC, same format as `utc_now_iso`."""
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime | None:
    """Parse a stored timestamp; return None if it is empty or malformed.

    Naive values (no offset) are assumed UTC so legacy rows still compare
    correctly instead of raising.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def is_future(value: str, now: str | None = None) -> bool:
    """True when `value` is strictly after `now` (default: current UTC).

    Compares parsed datetimes, not raw strings, so mixed-offset data and
    legacy naive timestamps are handled correctly.
    """
    target = parse_iso(value)
    if target is None:
        return False
    reference = parse_iso(now) if now else datetime.now(UTC)
    if reference is None:
        return False
    return target > reference
