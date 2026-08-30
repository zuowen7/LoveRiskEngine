"""Timeline view (roadmap feature, v0.2).

Merges the timestamped events we actually have — observations, boundary hits,
inconsistencies, reviews — into a single chronological stream so the user can
see the relationship's history at a glance.

Honesty note: relationship_state and exposure are upserted (last-write-wins),
so we have no history of their changes. The timeline therefore shows only the
events that carry an explicit timestamp. Tracking state/exposure deltas is a
separate roadmap item (it would need an event log); for now, this view is the
"event log" of what happened, not a continuous trace of every score.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .observation import Observation
from .signals import SignalType


@dataclass
class TimelineEvent:
    timestamp: str
    kind: str          # observation | boundary_hit | inconsistency | review
    label: str         # one-line human-readable summary
    detail: str = ""   # optional second line (claims, resolution, etc.)


def build_timeline(
    observations: List[Observation],
    boundary_hits: List,
    inconsistencies: List,
    reviews: List,
) -> List[TimelineEvent]:
    """Merge all timestamped events into one chronologically-sorted stream."""
    events: List[TimelineEvent] = []

    for o in observations:
        sig = ""
        if o.signal_type is SignalType.COSTLY:
            sig = " [COSTLY]"
        elif o.signal_type is SignalType.CHEAP:
            sig = " [CHEAP]"
        flags = []
        if o.rationalization:
            flags.append("rationalization")
        if o.inconsistency_flag:
            flags.append("inconsistency_flag")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        claims_str = ""
        if o.claims:
            claims_str = " | claims: " + ", ".join(
                f"{c.attribute}={c.value}" for c in o.claims
            )
        events.append(
            TimelineEvent(
                timestamp=o.timestamp,
                kind="observation",
                label=f"{o.id} {o.category}{sig}{flag_str}: {o.observation}",
                detail=(
                    f"interp: {o.interpretation}"
                    + (f" | alt: {o.alternative_explanation}"
                       if o.alternative_explanation else "")
                    + claims_str
                ).strip(" |"),
            )
        )

    for h in boundary_hits:
        ts = h["timestamp"] if "timestamp" in h.keys() else ""
        events.append(
            TimelineEvent(
                timestamp=ts,
                kind="boundary_hit",
                label=f"{h['id']} BOUNDARY HIT ({h['boundary_id']}): {h['evidence']}",
            )
        )

    for i in inconsistencies:
        ts = i["created_at"] if "created_at" in i.keys() else ""
        kind_tag = i["kind"] if "kind" in i.keys() else "manual"
        status = "resolved" if i["resolved"] else "open"
        resolution = i["resolution"] if "resolution" in i.keys() and i["resolution"] else ""
        note = i["resolution_note"] if "resolution_note" in i.keys() else ""
        detail = f"[{kind_tag}] {status}"
        if resolution:
            detail += f" -> {resolution}"
        if note:
            detail += f" | {note}"
        events.append(
            TimelineEvent(
                timestamp=ts,
                kind="inconsistency",
                label=f"{i['id']} INCONSISTENCY: {i['description']}",
                detail=detail,
            )
        )

    for r in reviews:
        ts = r["timestamp"] if "timestamp" in r.keys() else ""
        events.append(
            TimelineEvent(
                timestamp=ts,
                kind="review",
                label=f"{r['id']} REVIEW -> {r['recommendation']}",
                detail=r["notes"] if "notes" in r.keys() else "",
            )
        )

    # Sort by timestamp; events without a timestamp go last but keep stable order
    events.sort(key=lambda e: (e.timestamp or "9999",))
    return events


def format_timeline(events: List[TimelineEvent]) -> str:
    if not events:
        return "(no timestamped events yet)"
    lines: List[str] = []
    last_ts = ""
    for e in events:
        ts = e.timestamp or "?"
        day = ts[:10] if len(ts) >= 10 else ts
        if day != last_ts:
            lines.append(f"--- {day} ---")
            last_ts = day
        lines.append(f"  [{e.kind}] {e.label}")
        if e.detail:
            lines.append(f"        {e.detail}")
    return "\n".join(lines)
