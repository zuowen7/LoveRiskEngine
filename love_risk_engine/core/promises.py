"""Promise-expiry detector (relationship-kinds proposal, S2).

Flags *future-directed* structured claims that have gone untouched past the
profile's promise window. Complements the contradiction tracker, which needs
two conflicting observations: an expired promise has zero follow-up, so this
detector works on absence.

Exact semantics (PLAN_S2_S3.md §2.1) — for each normalized attribute, only the
**latest mention** governs:

  1. latest mention not future-directed (e.g. `funding=delivered`) → the
     promise was resolved or belongs to the contradiction tracker's domain →
     skipped;
  2. latest mention future-directed, age <= window → *within window*;
  3. latest mention future-directed, age > window → *expired*.

So "expired" means exactly: the attribute has gone untouched longer than the
window while still pointing at the future. A re-mention restarts the window by
construction. A malformed timestamp fails open — the claim is excluded from
both lists and never crashes anything.

Honest limitations (same contract as core/signals.py): the future-tense
lexicon is a keyword heuristic — it misses paraphrases and may over-match, so
the warning lists every claim it fired on and the user always decides. Output
proposes WAIT, never a conviction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .bias_detector import BiasFinding
from .contradiction import normalize_attribute
from .observation import Observation
from .timeutil import parse_iso, utc_now_iso

# Conservative, word-bounded future-tense markers. Hint-grade, not a model.
_FUTURE_PATTERN = re.compile(
    r"\b(?:will|going to|gonna|promises?|promised|"
    r"next (?:week|month|year|quarter|semester)|"
    r"by the end of|plans? to|intends? to|upcoming|by next)\b",
    re.IGNORECASE,
)

# Cap on detailed entries in the finding message; the rest collapse into a count.
_MAX_DETAILS = 3


@dataclass(frozen=True)
class PromiseClaim:
    attribute: str  # normalized (see core/contradiction.py)
    value: str
    observation_id: str
    timestamp: str
    age_days: int


@dataclass(frozen=True)
class PromiseReport:
    window_days: int | None
    within: list[PromiseClaim]
    expired: list[PromiseClaim]


def is_future_directed(value: str) -> bool:
    """Conservative keyword check on a claim value. Hint-grade, never a model."""
    return bool(_FUTURE_PATTERN.search(value))


def _age_days(timestamp: str, now_ts: str) -> int | None:
    """Whole days between two UTC ISO timestamps; None when unparseable.

    Fails open: an age we cannot compute must never flag anything, and must
    never crash the caller.
    """
    t = parse_iso(timestamp)
    n = parse_iso(now_ts)
    if t is None or n is None:
        return None
    return (n - t).days


def collect_promises(
    observations: list[Observation],
    window_days: int | None,
    now: str | None = None,
) -> PromiseReport:
    """Split latest-mention future-directed claims into within/expired.

    `window_days` None (kinds without a promise window) returns an empty
    report. `now` is injectable for tests; production uses UTC now.
    """
    report = PromiseReport(window_days=window_days, within=[], expired=[])
    if window_days is None:
        return report
    now_ts = now or utc_now_iso()

    # attribute -> (timestamp, observation_id, value) of the latest mention.
    # Ties (same second) break by observation id, deterministically.
    latest: dict[str, tuple[str, str, str]] = {}
    for o in sorted(observations, key=lambda x: (x.timestamp, x.id)):
        for c in o.claims:
            attr = normalize_attribute(c.attribute)
            value = c.value.strip()
            if not attr or not value:
                continue
            latest[attr] = (o.timestamp, o.id, value)

    for attr, (ts, oid, value) in latest.items():
        if not is_future_directed(value):
            continue
        age = _age_days(ts, now_ts)
        if age is None:
            continue  # malformed timestamp: fail open, never flag
        claim = PromiseClaim(attr, value, oid, ts, age)
        (report.expired if age > window_days else report.within).append(claim)

    report.within.sort(key=lambda p: (p.timestamp, p.observation_id))
    report.expired.sort(key=lambda p: (p.timestamp, p.observation_id))
    return report


def detect_expired_promises(
    observations: list[Observation],
    window_days: int | None,
    now: str | None = None,
) -> BiasFinding | None:
    """Warn (WAIT) when promise claims outlive the window untouched.

    The message carries the window, each claim's value, observation id, date
    and age — the basis stays fully auditable (DESIGN.md Do's #3).
    """
    if window_days is None:
        return None
    expired = collect_promises(observations, window_days, now=now).expired
    if not expired:
        return None

    shown = expired[:_MAX_DETAILS]
    details = "; ".join(
        f"{p.attribute}={p.value!r} (obs {p.observation_id}, "
        f"{p.timestamp[:10]}, {p.age_days}d)"
        for p in shown
    )
    if len(expired) > _MAX_DETAILS:
        details += f"; +{len(expired) - _MAX_DETAILS} more"
    return BiasFinding(
        "promise_expiry",
        f"{len(expired)} promise claim(s) untouched for > {window_days} days: "
        f"{details}.",
        severity=2,
        proposed_decision="WAIT",
    )
