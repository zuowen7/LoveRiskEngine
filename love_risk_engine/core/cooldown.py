"""Cooldown / precommitment hooks (roadmap feature, v0.2).

Turns the decision engine's output into a real guardrail. When `run_review`
returns PAUSE / DECREASE_EXPOSURE / EXIT, a cooldown record is written. While
active, the CLI blocks any action that would *raise* total exposure unless the
user explicitly overrides with `--override` (which itself is logged).

Design constraints (honest, no pseudoscience):
  - The cooldown is a precommitment device, not a punishment. It exists to
    impose a pause between "the engine says stop" and "I raise exposure
    anyway", so decisions are made deliberately, not impulsively.
  - Durations are placeholder defaults, configurable via LRE_COOLDOWN_HOURS.
  - Override is always possible (we never trap the user), but it is logged so
    the user can later audit their own override pattern.
  - Only exposure-*raising* actions are gated. Recording observations, running
    reviews, resolving inconsistencies — all still allowed, because those are
    exactly what the user should do during a cooldown.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass

from .decision import Decision
from .timeutil import is_future, parse_iso, utc_now_iso

# Default cooldown durations (hours) per decision. Placeholder values.
_DEFAULT_HOURS = {
    Decision.PAUSE: 24,
    Decision.DECREASE_EXPOSURE: 48,
    Decision.EXIT: 72,
}


def cooldown_hours_for(decision: Decision) -> int:
    """Return the cooldown duration (hours) for a blocking decision.

    Honors LRE_COOLDOWN_HOURS env var if set to a positive int (applies to all
    blocking decisions uniformly). Otherwise uses the per-decision defaults.
    """
    env = os.environ.get("LRE_COOLDOWN_HOURS")
    if env:
        with contextlib.suppress(ValueError):
            hours = int(env)
            if hours > 0:
                return hours
    return _DEFAULT_HOURS.get(decision, 24)


def is_blocking(decision: Decision) -> bool:
    """Only PAUSE / DECREASE_EXPOSURE / EXIT trigger a cooldown."""
    return decision in _DEFAULT_HOURS


@dataclass
class Cooldown:
    id: str
    relationship_id: str
    decision: str
    reason: str
    started_at: str
    expires_at: str
    active: bool = True


def is_active(cooldown: Cooldown, now: str | None = None) -> bool:
    """A cooldown is active if flagged active AND not yet expired.

    Compares parsed datetimes rather than raw strings, so a row written by an
    older version (naive timestamp) is still evaluated correctly.
    """
    if not cooldown.active:
        return False
    return is_future(cooldown.expires_at, now=now)


def format_remaining(cooldown: Cooldown, now: str | None = None) -> str:
    """Human-readable time remaining, or 'expired'/'inactive'."""
    if not cooldown.active:
        return "inactive"
    now = now or utc_now_iso()
    if not is_future(cooldown.expires_at, now=now):
        return "expired"
    exp = parse_iso(cooldown.expires_at)
    cur = parse_iso(now)
    if exp is None or cur is None:
        return f"until {cooldown.expires_at}"
    delta = exp - cur
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    if hours > 0:
        return f"{hours}h{minutes}m remaining"
    return f"{minutes}m remaining"
