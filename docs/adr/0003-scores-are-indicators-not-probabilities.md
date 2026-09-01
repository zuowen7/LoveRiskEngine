# ADR-0003: Scores are evidence indicators, not probabilities

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decides:** All scores are 0–10 evidence indicators. Heuristic
  thresholds are marked `uncalibrated`. No percentage-like or opaque
  composite risk score is produced.

## Context

A relationship decision-support engine is the worst possible place to
fake quantitative rigor. A "73% trust risk" looks like a measurement;
it is not. The inputs are qualitative observations interpreted through
heuristic detectors, none of which have been clinically or empirically
validated against any outcome. Presenting the output as a probability
would be a lie dressed as math, and a lie the user is structurally
inclined to believe because it came from a machine.

The project's own principles encode this: *Attraction != Trust*,
*Observation != Interpretation*, *Exposure must not outrun Evidence*,
*default CONTINUE_OBSERVING*. A composite probability score is the
shape of "exposure outrunning evidence" — it takes a pile of
uncalibrated heuristics and collapses them into a single number that
feels actionable.

The alternatives:

1. **Composite risk score (0–100 or %).** Most "risk engine" products do
   this. It is persuasive and unfalsifiable, which is the problem.
2. **Bayesian probabilities with priors.** Honest about uncertainty in
   principle, but the priors would be invented and the inputs are not
   the kind of data Bayes consumes cleanly. Fake precision with extra
   steps.
3. **0–10 evidence indicators, thresholds marked uncalibrated.** The
   score reflects how much evidence a detector has accumulated, full
   stop. It does not collapse to a verdict. Thresholds are explicitly
   placeholders until (if ever) empirical calibration exists.

## Decision

- Every score in the engine is an integer 0–10 representing evidence
  weight accumulated by a detector, not the probability of any outcome.
- Profile context uses `HIGH/MED/LOW`, not numbers, because the
  granularity of a number is unwarranted.
- Heuristic thresholds (when does a cooldown start, when does a pattern
  fire) are marked `uncalibrated` in the data and in the docs until
  empirical calibration exists — which may be never.
- No composite "risk score", "trust index", or percentage is produced
  by any code path. A review surfaces the individual detector outputs
  and the evidence behind them; the user does the synthesis.
- The README and `docs/SCIENTIFIC_FOUNDATIONS.md` state plainly that
  the detectors have not been clinically or empirically validated.

## Consequences

**We get:** output that does not pretend to be more certain than its
inputs. A user who reads "8/10 evidence of boundary drift" knows they
are reading an evidence weight, not a verdict, and that the threshold
for action is their call. The tool cannot be used to justify a
conclusion the evidence does not support.

**We pay:** the output is less "punchy" than a percentage. Users who
want a verdict have to do the synthesis themselves. Calibration, if it
ever arrives, will be a research project — and until then every
threshold is a placeholder we ship honestly.

## Enforcement

- `core/` dataclasses type every score field as `int` constrained to
  0–10; type checks and unit tests pin the range.
- `AGENTS.md` "Engineering Contracts" section forbids percentage-like
  and opaque composite scores, and mandates `uncalibrated` marking on
  heuristic thresholds.
- `tests/test_docs.py::test_readme_links_scientific_foundations_and_disclaims_validation`
  fails the build if the README drops the "have not been clinically or
  empirically validated" disclaimer.
- `docs/SCIENTIFIC_FOUNDATIONS.md` rule table is pinned to the
  `RULE_SPECS` registry by
  `tests/test_docs.py::test_scientific_foundations_rule_table_matches_registry`,
  so a rule cannot silently change its calibration story.
