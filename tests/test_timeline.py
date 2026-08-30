from love_risk_engine.core.observation import Observation
from love_risk_engine.core.signals import SignalType
from love_risk_engine.core.timeline import build_timeline, format_timeline


def _obs(idx, signal=SignalType.UNSPECIFIED, claims=None, rationalization=False):
    return Observation(
        id=f"O{idx:03d}", relationship_id="R001",
        timestamp=f"2026-01-{idx:02d}T10:00:00",
        category="signal", observation=f"obs {idx}", interpretation="i",
        alternative_explanation="alt", source="self", confidence=5.0,
        signal_type=signal, claims=claims or [], rationalization=rationalization,
    )


def _row(d):
    """Build a sqlite3.Row-like dict for timeline tests."""
    return _DictRow(d)


class _DictRow:
    def __init__(self, d):
        self._d = d

    def __getitem__(self, k):
        return self._d[k]

    def keys(self):
        return self._d.keys()


def test_empty_timeline():
    events = build_timeline([], [], [], [])
    assert events == []
    assert format_timeline(events) == "(no timestamped events yet)"


def test_observations_appear_with_signal_tag():
    obs = [_obs(1, SignalType.COSTLY), _obs(2, SignalType.CHEAP)]
    events = build_timeline(obs, [], [], [])
    assert len(events) == 2
    assert "[COSTLY]" in events[0].label
    assert "[CHEAP]" in events[1].label


def test_events_sorted_chronologically():
    obs = [_obs(5), _obs(1), _obs(3)]
    events = build_timeline(obs, [], [], [])
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


def test_mixed_event_types_merge():
    obs = [_obs(1)]
    hits = [_row({"id": "H001", "timestamp": "2026-01-02T00:00:00",
                  "boundary_id": "B001", "evidence": "crossed a line"})]
    incs = [_row({"id": "I001", "created_at": "2026-01-03T00:00:00",
                  "description": "story mismatch", "kind": "detected",
                  "resolved": 0, "resolution": None, "resolution_note": ""})]
    revs = [_row({"id": "RV001", "timestamp": "2026-01-04T00:00:00",
                  "recommendation": "PAUSE", "notes": "high emotion"})]
    events = build_timeline(obs, hits, incs, revs)
    kinds = [e.kind for e in events]
    assert kinds == ["observation", "boundary_hit", "inconsistency", "review"]


def test_format_timeline_groups_by_day():
    obs = [_obs(1), _obs(2)]
    events = build_timeline(obs, [], [], [])
    out = format_timeline(events)
    assert "--- 2026-01-01 ---" in out
    assert "--- 2026-01-02 ---" in out


def test_resolved_inconsistency_shows_resolution():
    incs = [_row({
        "id": "I001", "created_at": "2026-01-01T00:00:00",
        "description": "x", "kind": "detected", "resolved": 1,
        "resolution": "genuine_inconsistency", "resolution_note": "red flag",
    })]
    events = build_timeline([], [], incs, [])
    assert "genuine_inconsistency" in events[0].detail
    assert "red flag" in events[0].detail
