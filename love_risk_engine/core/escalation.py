"""Rapid exposure escalation detector (roadmap #1 follow-up).

Flags the pairing the history log makes visible: exposure climbing fast while
no new evidence arrives — "exposure grew 3 points in 2 days while evidence
grew 0". Speed impairs judgement, so the finding proposes PAUSE, never a
conviction.

Semantics (PLAN_rapid_escalation.md):
  - window: the last `RAPID_EXPOSURE_WINDOW_DAYS` days;
  - growth: total exposure increased by >= `RAPID_EXPOSURE_INCREASE` inside the
    window, measured against the latest snapshot at or before the window start
    (the earliest snapshot overall when the series started inside the window);
  - pairing: any observation inside the window means evidence grew -> silent;
  - fail open: un-datable rows are skipped, unparseable `now` silences the
    detector — it must never crash or flag on data it cannot date.

Both thresholds are uncalibrated placeholders, documented as such, and the
finding message carries every number the decision rests on (window, delta,
baseline, current) so the basis stays auditable.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .bias_detector import BiasFinding
from .history import ExposureChange
from .observation import Observation
from .timeutil import parse_iso, utc_now_iso

RAPID_EXPOSURE_WINDOW_DAYS = 2  # uncalibrated placeholder
RAPID_EXPOSURE_INCREASE = 3.0  # uncalibrated placeholder


def detect_rapid_exposure_escalation(
    exposure_history: list[ExposureChange],
    observations: list[Observation],
    now: str | None = None,
) -> BiasFinding | None:
    """Warn (PAUSE) when exposure climbs fast with zero new evidence.

    `now` is injectable for tests; production uses UTC now.
    """
    if not exposure_history:
        return None
    now_ts = now or utc_now_iso()
    now_dt = parse_iso(now_ts)
    if now_dt is None:
        return None  # fail open: cannot date anything
    cutoff = now_dt - timedelta(days=RAPID_EXPOSURE_WINDOW_DAYS)

    dated: list[tuple[datetime, ExposureChange]] = []
    for h in exposure_history:
        dt = parse_iso(h.timestamp)
        if dt is not None:
            dated.append((dt, h))
    if not dated:
        return None
    dated.sort(key=lambda pair: pair[0])

    current_dt, current = dated[-1]
    if current_dt <= cutoff:
        return None  # growth happened entirely before the window

    at_or_before = [h for dt, h in dated if dt <= cutoff]
    baseline = at_or_before[-1] if at_or_before else dated[0][1]

    delta = current.total - baseline.total
    if delta < RAPID_EXPOSURE_INCREASE:
        return None

    new_observations = 0
    for o in observations:
        t = parse_iso(o.timestamp)
        if t is not None and t > cutoff:
            new_observations += 1
    if new_observations > 0:
        return None  # evidence grew in the same window

    return BiasFinding(
        "rapid_exposure_escalation",
        f"Exposure grew {delta:.1f} points in the last "
        f"{RAPID_EXPOSURE_WINDOW_DAYS} days ({baseline.total:.1f} -> "
        f"{current.total:.1f}) with no new observations recorded in that window.",
        severity=3,
        proposed_decision="PAUSE",
    )
