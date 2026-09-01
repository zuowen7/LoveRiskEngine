# Scientific Foundations — Theory-Informed Design

LoveRiskEngine is an engineering project, not a validated scientific
instrument. This document states, construct by construct, which parts of the
design are anchored in published research, how strong that anchoring is, and
which parts are project-specific engineering choices. It exists so that
anyone reading the code can tell science from invention at a glance — and so
that the design discipline ("every rule must say why it exists") is
checkable, not aspirational.

**Reading rule:** every specific threshold, duration, weight, and score in
this codebase is an **uncalibrated engineering heuristic**. Literature below
justifies the *shape* of a mechanism, never its numbers. No paper says
"cooldown 24h", "trust gap 3.0", or "3 cheap + 1 costly signals". Those are
ours, and they stay marked as ours.

## How this document relates to validity claims

Following the standard layering of validity in judgment-and-decision-making
research, we explicitly claim **only the first layer**:

| Layer | Claim | Status in LoveRiskEngine |
|---|---|---|
| Theory validity | Each core design decision has a literature anchor or is flagged as not having one | **Claimed here** (tables below) |
| Construct validity | Our variables measure what they claim to measure | Not claimed. Partial (backlog: trust decomposition, see §Backlog) |
| Mechanism validity | Using LRE reduces measured bias in experiments | Not claimed. No user studies have been run |
| Real-world validity | Using LRE improves outcomes over months | Not claimed |

The research question this architecture is *shaped for* (should anyone ever
pursue it) is not "can software judge a person's character" but:

> Can a structured cognitive-forcing framework reduce cognitive bias and
> improve evidence sensitivity in high-uncertainty relationship decisions?

The `hypothesis` column in the tables below is written in testable form for
exactly that reason: today it enforces design discipline; later it could be
reused as a research-program skeleton. Nothing here has been empirically
tested.

## Evidence levels

Every rule in the registry carries one of five evidence levels
(`core/rulespec.py`, `EvidenceLevel`):

- **theory_supported** — the *mechanism* has direct experimental support.
- **theory_informed** — the design is informed by adjacent literature; the
  literature studies a related phenomenon, not this rule as implemented.
- **construct_informed** — the rule borrows the structure of a validated
  psychological construct without reproducing its measurement.
- **emerging_evidence** — empirical work on the phenomenon exists but is
  thin, early, or methodologically limited. Hypothesis-generating only.
- **engineering_heuristic** — project-specific rule with no direct anchor,
  kept because it is transparent, explainable, and auditable.

## Table 1 — Design mechanisms (schema- and workflow-level)

Mechanisms are properties of the observation schema and the review workflow.
They do not fire as detectors; they shape what gets recorded.

| Mechanism | Design hypothesis | Literature anchor | Evidence level | Notes |
|---|---|---|---|---|
| Structured observation (observation / interpretation / **alternative required when an interpretation is supplied**) | Separating the record from the reading, plus forcing at least one alternative explanation for an interpretation, reduces confirmatory assimilation of ambiguous evidence | *Consider the opposite* — Lord, Lepper & Preston (1984) | theory_supported | Facts-only observations may omit both interpretation and alternative; enforced for new CLI input, while legacy/imported rows remain auditable |
| Cooldown guardrails (24/48/72 h) | A forced delay between "the engine says stop" and "I raise exposure anyway" reduces impulsive escalation | Commitment devices, soft commitment — Bryan, Karlan & Nelson (2010) | theory_informed | Durations are engineering defaults, configurable via `LRE_COOLDOWN_HOURS`; override always possible and logged |
| Pre-set boundaries in if-then form ("if X, then pause") | Pre-committing a boundary as an if-then plan makes it hold under emotional pressure | Implementation intentions — Gollwitzer & Sheeran (2006, meta-analysis, d = .65 over 94 tests) | theory_informed | Boundary *content* is user-authored; the engine only enforces the evidence-basis rule for EXIT |
| Attraction and trust stored and mutated independently | Keeping liking separate from evidence-supported trust prevents halo transfer | Interpersonal trust as a distinct construct — Rempel, Holmes & Zanna (1985) | construct_informed | Scalar 0–10 is a construct-informed engineering representation, not a psychometric scale; see §Backlog |
| Values / boundary elicitation at onboarding | Making the user articulate values before decisions reduces value-incongruent choices and decisional conflict | Values clarification methods — Witteman et al. (2021, 33 articles, 43 methods) | theory_informed | Domain-transfer caveat: evidence is from medical decision aids, not romantic decisions |
| Counterfactual review of past decisions | Re-examining a past decision against what was known *then* reduces hindsight contamination of the evidence ledger | Counterfactual / hindsight reasoning literature | engineering_heuristic | No anchor audited in the current provenance pass |
| Evidence-support quality weighting (cheap vs costly, triangulation, rigor, concreteness) | Weighting hard-to-fake signals above easy talk makes the exposure gate track evidence quality, not volume | Signaling theory: cheap talk vs costly signals | engineering_heuristic | No anchor audited in the current provenance pass |
| Explicit criterion/direction labels | Comparing only judgments that the user explicitly assigns the same criterion avoids opaque semantic inference while making opposite recorded directions reviewable | Project-specific structured consistency check | engineering_heuristic | `UNSPECIFIED` and `NEUTRAL` do not form conflicts; a candidate is not proof of bias |

## Table 2 — Detector rule registry

This table is the documentation projection of `core/rulespec.py::RULE_SPECS`
and is kept in lockstep by tests (`tests/test_docs.py`): a rule not in the
table fails the build, and a table row without a registered rule fails the
build. Thresholds are uncalibrated for **every** entry.

| Rule | Hypothesis | Basis | Evidence level | Thresholds | References |
|---|---|---|---|---|---|
| `attraction_exceeds_trust` | Flagging a large attraction-trust gap on a thin evidence base increases the chance that trust commitments are withheld until evidence accumulates | Interpersonal trust as a construct distinct from liking/attraction | construct_informed | uncalibrated | Rempel, Holmes & Zanna (1985) |
| `repeated_rationalization` | Making consecutive self-justifications visible reduces the length of rationalization runs | Motivated reasoning / self-justification runs; the theory-supported countermeasure (alternative explanations for interpretations) lives in the observation schema, not this rule | engineering_heuristic | uncalibrated | — |
| `exposure_outpaces_evidence` | Gating exposure growth on accumulated evidence support reduces impulsive escalation relative to an unstructured baseline | Evidence-gated exposure; investment-to-commitment path dependence used *indirectly* (see §Direction caveat) | theory_informed | uncalibrated | Rusbult, Martz & Agnew (1998) |
| `exposure_within_support` | Explicitly reporting a healthy exposure/evidence ratio reduces anxiety-driven premature withdrawal | Epistemic vigilance: the ratio stays visible even when healthy | engineering_heuristic | uncalibrated | — |
| `high_emotion_major_decision` | A forced pause during high emotional arousal before a major decision reduces affect-driven irreversible choices | Affect-driven judgment; the pause behaves like a soft commitment device and an if-then plan | theory_informed | uncalibrated | Bryan, Karlan & Nelson (2010); Gollwitzer & Sheeran (2006) |
| `unresolved_inconsistencies` | Surfacing unresolved contradictions increases the probability that they are resolved rather than normalized | Epistemic consistency checking (project-specific) | engineering_heuristic | uncalibrated | — |
| `love_bombing_pattern` | Flagging early cheap-talk + costly-gesture clusters helps users delay exposure escalation during the early window — **hypothesis-generating, not validated** | Love-bombing literature (emerging and thin; founding study is exploratory, in a student journal) | emerging_evidence | uncalibrated | Strutzenberg et al. (2017); Klein, Li & Wood (2023); Çalışkan Sarı (2026) |
| `rapid_exposure_escalation` | Detecting rapid exposure growth with zero new observations prompts evidence collection before further escalation | Escalation-of-commitment concern (project-specific operationalization; no audited anchor) | engineering_heuristic | uncalibrated | — |
| `promise_expiry` | Surfacing expired future-directed claims reduces reliance on unfulfilled verbal commitments | Cheap talk vs costly-signal distinction (no audited anchor) | engineering_heuristic | uncalibrated | — |
| `repeated_repromises` | Counting repeated re-promises cheapens renewed cheap talk and increases demand for costly follow-through | Cheap talk vs costly-signal distinction (no audited anchor) | engineering_heuristic | uncalibrated | — |
| `trust_change_without_new_evidence` | Showing trust changes that have no newly recorded evidence in the same interval prompts the user to record or reconsider the basis of the update | Record-level temporal consistency check; reconsideration of older evidence remains a valid alternative | engineering_heuristic | uncalibrated | — |
| `interpretation_without_alternative` | Surfacing legacy or imported interpretations without an alternative reading increases visibility of one-sided records | Project-specific audit projection of the structured-observation mechanism | engineering_heuristic | uncalibrated | — |
| `self_reported_rationalization_run` | Labeling runs of user-marked rationalizations as self-reported avoids overstating them as automatic psychological detection | Project-specific audit of explicit user annotations | engineering_heuristic | uncalibrated | — |
| `unresolved_structured_conflicts` | Reporting current unresolved structured conflicts in the consistency audit makes their limited, non-semantic scope explicit | Project-specific projection of persisted contradiction candidates | engineering_heuristic | uncalibrated | — |
| `criterion_direction_conflict` | Surfacing opposite trust directions recorded under the same explicit criterion makes possible standard drift reviewable without inferring free-text meaning | Project-specific structured consistency check | engineering_heuristic | uncalibrated | — |

### Direction caveat (Investment Model)

Rusbult's Investment Model says **investment → commitment**, not
investment → risk. We do not equate the two. LRE uses the model only as a
*warning about path dependence*: as exposure accumulates, the user may find
it harder to update on new evidence (rationalizing sunk investment), which
is exactly what the exposure gate and rationalization detector exist to
counter. This is an indirect, theory-informed use — flagged as such.

## Provenance audit (2026-09-01)

All citations in this document were checked against the primary source.
Audit notes and caveats:

1. **Lord, C. G., Lepper, M. R., & Preston, E. (1984).** *Considering the
   opposite: a corrective strategy for social judgment.* Journal of
   Personality and Social Psychology, 47(6), 1231–1237.
   https://doi.org/10.1037/0022-3514.47.6.1231
   Verified: two experiments; inducing consider-the-opposite reduced biased
   assimilation and biased hypothesis testing more than "be unbiased"
   instructions. **No caveats.**
2. **Bryan, G., Karlan, D., & Nelson, S. (2010).** *Commitment Devices.*
   Annual Review of Economics, 2, 671–698.
   https://doi.org/10.1146/annurev.economics.102308.124324
   Verified: review distinguishing hard and soft commitments, covering
   present bias and self-control. **No caveats.**
3. **Gollwitzer, P. M., & Sheeran, P. (2006).** *Implementation Intentions
   and Goal Achievement: A Meta-analysis of Effects and Processes.*
   Advances in Experimental Social Psychology, 38, 69–119.
   https://doi.org/10.1016/S0065-2601(06)38002-1
   Verified: 94 independent tests, medium-to-large effect on goal attainment
   (d = .65). **Caveat:** goal attainment in general, not relationship
   decisions specifically.
4. **Rempel, J. K., Holmes, J. G., & Zanna, M. P. (1985).** *Trust in close
   relationships.* Journal of Personality and Social Psychology, 49(1),
   95–112. https://doi.org/10.1037/0022-3514.49.1.95
   Verified: 47 dating/cohabiting/married couples; predictability,
   dependability, and faith emerged as distinct, coherent dimensions.
   **Caveats:** small sample, correlational; faith closely tied to love and
   happiness; an additional "intrinsic motives" dimension also emerged. The
   decomposition is a construct anchor, not a scoring recipe.
5. **Rusbult, C. E., Martz, J. M., & Agnew, C. R. (1998).** *The Investment
   Model Scale.* Personal Relationships, 5, 357–391.
   https://doi.org/10.1111/j.1475-6811.1998.tb00177.x
   Verified: three studies, good internal consistency, four-factor
   structure, earlier measures predicted later dyadic adjustment and
   persistence. **Caveat:** direction of use in LRE is indirect (see
   §Direction caveat).
6. **Witteman, H. O., et al. (2021).** *Clarifying Values: An Updated and
   Expanded Systematic Review and Meta-Analysis.* Medical Decision Making.
   https://doi.org/10.1177/0272989X211037946
   Verified: 33 articles, 43 values-clarification methods; explicit methods
   reduced value-incongruent choices (RD −0.04) and decisional conflict
   (SMD −0.20). **Caveat:** medical decision aids, not romantic decisions —
   methodology transferable, findings not assumed to be.
7. **Strutzenberg, C. C., Wiersma-Mosley, J. D., Jozkowski, K. N., & Becnel,
   J. N. (2017).** *Love-bombing: A Narcissistic Approach to Relationship
   Formation.* Discovery, 18(1), 81–89.
   https://doi.org/10.54119/discovery.zxgc9960
   Verified: N = 484 undergraduates; love-bombing correlated with
   narcissistic tendencies and insecure attachment. **Caveats:** published
   in a **student journal**; the authors themselves describe it as the first
   empirical examination, intended as a gateway for further research. This
   is the weakest anchor in the registry and is why
   `love_bombing_pattern` is marked emerging_evidence / hypothesis-generating.
8. **Klein, W., Li, S., & Wood, S. (2023).** *A qualitative analysis of
   gaslighting in romantic relationships.* Personal Relationships.
   https://doi.org/10.1111/pere.12510
   Verified via full-text secondary coverage (the publisher page blocks
   automated access): N = 65 survivors, qualitative; love-bombing reported
   in most trajectories, typically at relationship start; authors
   distinguish normal honeymoon intensity from the exaggerated pattern
   retrospectively reported in gaslighting trajectories. **Caveats:**
   qualitative, retrospective, survivor-only sampling.
9. **Çalışkan Sarı, A. (2026).** *Aşk Bombardımanı Ölçeğinin Beliren
   Yetişkinlik Dönemindeki Bireyler Üzerinde Türkçeye Uyarlama Çalışması.*
   Istanbul Gelisim University Journal of Social Sciences, 13(1).
   https://doi.org/10.17336/igusbd.1651349
   Verified: N = 673 emerging adults; EFA (n = 208) and CFA (n = 465);
   Turkish adaptation of the Strutzenberg Love Bombing Scale with
   acceptable validity/reliability. **Caveat:** adaptation of an instrument
   whose original validation is the student-journal study above; the scale
   exists, the evidence base remains thin.

Constructs named **without** a numbered citation (signaling theory,
motivated reasoning, escalation of commitment, counterfactual reasoning)
were *not* audited in this pass and are marked engineering_heuristic until
a provenance audit covers them. That is deliberate: an unaudited citation is
worse than an honest blank.

## Backlog (explicitly not in the current version)

- **Trust decomposition.** Replace the scalar trust field with
  predictability / dependability / faith sub-scores, each a
  project-defined 0–10 self-rating. Constraints already decided: this is a
  *construct-informed engineering representation*, not a validated
  psychometric scale; the three sub-scores are **never** mechanically
  combined into a composite "scientific trust score"; requires a schema
  migration (`SCHEMA_VERSION` bump) and a full caller audit.
- **Calibration.** Every threshold in this codebase is uncalibrated. Any
  future calibration work must produce its own evidence and update
  `threshold_status` in `core/rulespec.py`; it may not silently borrow
  numbers from the literature (see reading rule above).

## Maintenance contract

- Adding or renaming a detector: register a `RuleSpec` in
  `core/rulespec.py` **and** add the table row here. The build fails if
  either side drifts (`tests/test_docs.py`).
- Citing anything new here requires a provenance check against the primary
  source first; record it in the audit appendix with caveats.
- This document is English-only by decision, consistent with DESIGN.md; the
  bilingual pair convention applies to README / getting-started only.
