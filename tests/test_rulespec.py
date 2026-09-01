"""Invariants of the rule metadata registry (core/rulespec.py).

The registry is developer-facing metadata only — these tests pin its
contract so it cannot silently rot: every active detector must declare its
theory anchor, and nothing may claim calibration that does not exist.
"""

from __future__ import annotations

from love_risk_engine.core.profiles import PROFILES
from love_risk_engine.core.rulespec import (
    RULE_SPECS,
    THRESHOLD_UNCALIBRATED,
    EvidenceLevel,
)


def _enabled_hooks() -> set[str]:
    return {hook for p in PROFILES.values() for hook in p.enabled_hooks}


def test_every_enabled_hook_is_registered():
    """A detector wired into any profile must carry a RuleSpec.

    This is the guard against adding a new detector and forgetting to state
    its theoretical basis (or its lack of one).
    """
    missing = _enabled_hooks() - set(RULE_SPECS)
    assert not missing, f"hooks without a RuleSpec: {sorted(missing)}"


def test_every_spec_is_complete():
    for spec in RULE_SPECS.values():
        assert spec.rule_id, "rule_id must be non-empty"
        assert spec.hypothesis.strip(), f"{spec.rule_id}: empty hypothesis"
        assert spec.basis.strip(), f"{spec.rule_id}: empty basis"
        assert isinstance(spec.evidence_level, EvidenceLevel)
        assert spec.threshold_status == THRESHOLD_UNCALIBRATED, (
            f"{spec.rule_id}: threshold_status must stay uncalibrated until "
            "calibration work exists"
        )


def test_finding_rule_ids_in_core_are_registered():
    """Every BiasFinding rule_id constructable in core/ has a spec.

    Grep-style guard: catches informational variants (e.g.
    `exposure_within_support`) that never appear in enabled_hooks.
    """
    import re
    from pathlib import Path

    core = Path(__file__).resolve().parent.parent / "love_risk_engine" / "core"
    pattern = re.compile(r'BiasFinding\(\s*\n?\s*"([a-z_]+)"')
    constructed: set[str] = set()
    for path in core.glob("*.py"):
        constructed |= set(pattern.findall(path.read_text(encoding="utf-8")))
    missing = constructed - set(RULE_SPECS)
    assert not missing, f"BiasFinding rule_ids without a RuleSpec: {sorted(missing)}"
