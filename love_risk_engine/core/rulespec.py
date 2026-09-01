"""Rule metadata registry: theory anchors and evidence levels per rule.

Developer-facing metadata only. A RuleSpec is *not* user data: it is never
persisted to SQLite, never exported, and never rendered by `status` /
`review`. Its consumers are documentation generation, developer review, and
the doc-contract tests (tests/test_docs.py, tests/test_rulespec.py). If a
runtime surface ever needs it, expose it via a read-only command (e.g.
`lre explain <rule>`); the persistence contract stays untouched.

Two rules govern this registry (docs/SCIENTIFIC_FOUNDATIONS.md):

1. Borrow constructs, not numbers. A literature anchor justifies the *shape*
   of a rule, never its thresholds. No literature says "cooldown 24h" or
   "trust gap 3.0"; those remain engineering choices.
2. Every threshold stays `uncalibrated` until calibration work exists. Adding
   a spec never justifies retuning a rule.

Provenance: all citations below were verified against the primary source on
2026-09-01 (see the audit appendix in docs/SCIENTIFIC_FOUNDATIONS.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

THRESHOLD_UNCALIBRATED = "uncalibrated"


class EvidenceLevel(StrEnum):
    """How much published evidence stands behind a rule's design.

    THEORY_SUPPORTED — the *mechanism* has direct experimental support
      (e.g. consider-the-opposite reduces bias in social judgment).
    THEORY_INFORMED — the design is informed by adjacent literature, but the
      literature studies a related phenomenon, not this rule as implemented.
    CONSTRUCT_INFORMED — the rule borrows the structure of a validated
      psychological construct without reproducing its measurement.
    EMERGING_EVIDENCE — empirical work on the phenomenon exists but is thin,
      early, or methodologically limited; treat as hypothesis-generating.
    ENGINEERING_HEURISTIC — project-specific rule with no direct literature
      anchor; kept because it is transparent, explainable, and auditable.
    """

    THEORY_SUPPORTED = "theory_supported"
    THEORY_INFORMED = "theory_informed"
    CONSTRUCT_INFORMED = "construct_informed"
    EMERGING_EVIDENCE = "emerging_evidence"
    ENGINEERING_HEURISTIC = "engineering_heuristic"


@dataclass(frozen=True)
class RuleSpec:
    """Metadata for one detector rule.

    `hypothesis` states the design hypothesis in testable form — the table in
    docs/SCIENTIFIC_FOUNDATIONS.md is structured so it can be reused as
    research material later; today it serves design discipline only.
    """

    rule_id: str
    hypothesis: str
    basis: str
    evidence_level: EvidenceLevel
    threshold_status: str = THRESHOLD_UNCALIBRATED
    references: tuple[str, ...] = ()


RULE_SPECS: dict[str, RuleSpec] = {
    spec.rule_id: spec
    for spec in (
        RuleSpec(
            rule_id="attraction_exceeds_trust",
            hypothesis=(
                "Flagging a large attraction-trust gap on a thin evidence base "
                "increases the chance that trust commitments are withheld "
                "until evidence accumulates."
            ),
            basis=(
                "Interpersonal trust as a construct distinct from "
                "liking/attraction in close relationships."
            ),
            evidence_level=EvidenceLevel.CONSTRUCT_INFORMED,
            references=("Rempel, Holmes & Zanna (1985)",),
        ),
        RuleSpec(
            rule_id="repeated_rationalization",
            hypothesis=(
                "Making consecutive self-justifications visible reduces the "
                "length of rationalization runs."
            ),
            basis=(
                "Motivated reasoning / self-justification runs; the "
                "theory-supported countermeasure (requiring alternative "
                "explanations) lives in the observation schema, not this rule."
            ),
            evidence_level=EvidenceLevel.ENGINEERING_HEURISTIC,
        ),
        RuleSpec(
            rule_id="exposure_outpaces_evidence",
            hypothesis=(
                "Gating exposure growth on accumulated evidence support "
                "reduces impulsive escalation relative to an unstructured "
                "baseline."
            ),
            basis=(
                "Evidence-gated exposure; investment-to-commitment path "
                "dependence used *indirectly* (see direction caveat in "
                "docs/SCIENTIFIC_FOUNDATIONS.md)."
            ),
            evidence_level=EvidenceLevel.THEORY_INFORMED,
            references=("Rusbult, Martz & Agnew (1998)",),
        ),
        RuleSpec(
            rule_id="exposure_within_support",
            hypothesis=(
                "Explicitly reporting a healthy exposure/evidence ratio "
                "reduces anxiety-driven premature withdrawal."
            ),
            basis=(
                "Epistemic vigilance: the exposure/evidence ratio stays "
                "visible even when it is healthy."
            ),
            evidence_level=EvidenceLevel.ENGINEERING_HEURISTIC,
        ),
        RuleSpec(
            rule_id="high_emotion_major_decision",
            hypothesis=(
                "A forced pause during high emotional arousal before a major "
                "decision reduces affect-driven irreversible choices."
            ),
            basis=(
                "Affect-driven judgment; the pause behaves like a soft "
                "commitment device and an if-then plan."
            ),
            evidence_level=EvidenceLevel.THEORY_INFORMED,
            references=(
                "Bryan, Karlan & Nelson (2010)",
                "Gollwitzer & Sheeran (2006)",
            ),
        ),
        RuleSpec(
            rule_id="unresolved_inconsistencies",
            hypothesis=(
                "Surfacing unresolved contradictions increases the "
                "probability that they are resolved rather than normalized."
            ),
            basis="Epistemic consistency checking (project-specific).",
            evidence_level=EvidenceLevel.ENGINEERING_HEURISTIC,
        ),
        RuleSpec(
            rule_id="love_bombing_pattern",
            hypothesis=(
                "Flagging early cheap-talk + costly-gesture clusters helps "
                "users delay exposure escalation during the early window. "
                "Hypothesis-generating, not validated."
            ),
            basis=(
                "Love-bombing literature (emerging and thin; the founding "
                "study is exploratory and published in a student journal)."
            ),
            evidence_level=EvidenceLevel.EMERGING_EVIDENCE,
            references=(
                "Strutzenberg et al. (2017)",
                "Klein, Li & Wood (2023)",
                "Çalışkan Sarı (2026)",
            ),
        ),
        RuleSpec(
            rule_id="rapid_exposure_escalation",
            hypothesis=(
                "Detecting rapid exposure growth with zero new observations "
                "prompts evidence collection before further escalation."
            ),
            basis=(
                "Escalation-of-commitment concern (project-specific "
                "operationalization; no audited anchor)."
            ),
            evidence_level=EvidenceLevel.ENGINEERING_HEURISTIC,
        ),
        RuleSpec(
            rule_id="promise_expiry",
            hypothesis=(
                "Surfacing expired future-directed claims reduces reliance "
                "on unfulfilled verbal commitments."
            ),
            basis="Cheap talk vs. costly-signal distinction (no audited anchor).",
            evidence_level=EvidenceLevel.ENGINEERING_HEURISTIC,
        ),
        RuleSpec(
            rule_id="repeated_repromises",
            hypothesis=(
                "Counting repeated re-promises cheapens renewed cheap talk "
                "and increases demand for costly follow-through."
            ),
            basis="Cheap talk vs. costly-signal distinction (no audited anchor).",
            evidence_level=EvidenceLevel.ENGINEERING_HEURISTIC,
        ),
    )
}
