# LoveRiskEngine v0.1 — Implementation Overview

A personal relationship **decision-support framework** (evidence-first, bias-auditing,
exposure-aware). Local SQLite + CLI only. No scoring, no surveillance.

## What was built

- **Domain model** (dataclasses, `core/`): `RelationshipState` (attraction/trust/uncertainty
  kept strictly separate), `Exposure` (5 independent axes), `Observation`
  (observation / interpretation / alternative_explanation / source / confidence),
  `Boundary` + `BoundaryHit`, `Inconsistency`.
- **Bias detectors** (`core/bias_detector.py`): the 5 v0.1 rules, each returning a
  `BiasFinding(rule_id, message, severity, proposed_decision)`. Thresholds are
  explicitly documented as **uncalibrated placeholders**.
- **Hook runner** (`core/hooks.py`) + **decision engine** (`core/decision.py`):
  priority order `EXIT > PAUSE > DECREASE_EXPOSURE > WAIT > CONTINUE_OBSERVING`.
  Default is `CONTINUE_OBSERVING`. `EXIT` only when a hard boundary has a
  recorded hit with evidence.
- **Storage** (`storage/`): pure-stdlib SQLite, readable sequential IDs
  (`R001`, `O001`, `B001`, …), CRUD returns domain objects.
- **Review service** (`services/review.py`): `run_review()` assembles context,
  runs hooks, decides, persists a `Review`.
- **CLI** (`cli.py`, command `lre`): init, relationship add, observe (with `--claim`
  and `--signal-type`), status, review, boundary add/hit, list, state set, exposure set
  (cooldown-gated, `--override`), inconsistency add/resolve (three-state `--as`)/list,
  contradictions (auto-detect), chat import, timeline, cooldown list/clear.
- **Contradiction tracker** (`core/contradiction.py` + storage): observations can
  carry structured `claims` (`attribute=value`); `detect_contradictions()` surfaces
  any same-attribute / different-value conflict deterministically (no model, no score).
  `lre contradictions <rel> [--save]` detects and optionally persists candidates as
  unresolved inconsistencies, which then flow into `status` / `review`.
- **Evidence support** (`core/evidence.py`): replaces the raw observation-count proxy
  for the `exposure_outpaces_evidence` rule with a transparent composite of
  observation breadth, source triangulation, rigor (alternative explanations recorded),
  and concreteness (structured claims captured). Not a probability — `status` prints the
  component counts so the basis is fully auditable.
- **Local chat import & analysis** (`core/chat_import.py` + `lre chat import`):
  offline, stdlib-only import of a local NDJSON or `TIMESTAMP | SPEAKER | TEXT` export
  into observations; optional regex `--rules` (`examples/claim_rules.json`) extract
  structured `claims`. After import it auto-runs contradiction detection and reports.
  Never deletes/overwrites existing data, no network, no PII fields.
- **Top conflicts in `status`**: `cmd_status` now runs `detect_contradictions` and prints
  a "Conflicting claims (top)" block (attribute + two values + observation IDs) directly,
  so conflicts are visible without a separate command.
- **Cheap-talk / costly-signal classification** (`core/signals.py`): each observation
  can be tagged `--signal-type {CHEAP,COSTLY,UNSPECIFIED}`. Costly signals weigh 4×
  cheap talk in the evidence-support model. A crude keyword heuristic
  (`suggest_signal_type`) prints a *hint* when no type is given — it never auto-sets;
  the user always decides. Honest about being a keyword match, not a classifier.
- **Quality-calibrated evidence support** (`core/evidence.py` v0.2): the v0.1 raw
  observation-count proxy is replaced by a transparent per-observation contribution
  `base * confidence_weight * signal_weight` (conf_weight = 0.5 + conf/10; signal_weight
  from SignalType). Triangulation, rigor, and concreteness bonuses are kept. Still NOT
  a probability — coefficients are uncalibrated placeholders, but they now respond to
  quality dimensions the user controls. `status` prints costly_count / cheap_count.
- **Contradiction resolution UX** (three-state): `inconsistencies` gained `resolution`
  + `resolution_note` columns (backward-compatible migrate). `lre inconsistency resolve
  <id> --as {sequential_change,genuine_inconsistency,dismissed} [--note ...]` closes a
  conflict with an auditable type; underlying observations are never deleted.
  `lre inconsistency list <rel> [--resolved]` shows the audit trail; `status` prints
  an `Acknowledged (closed): N (x sequential, y genuine, z dismissed)` line so closed
  items stay visible rather than vanishing silently.
- **Love-bombing pattern detector** (`core/patterns.py`): flags the classic manipulation
  precursor — a burst of cheap affection talk **paired with** costly gestures compressed
  into the early window (first 10 observations). Requires ≥3 CHEAP + ≥1 COSTLY + ≥5 total
  signals so the *pairing* is what fires (cheap talk alone = enthusiasm). Proposes PAUSE,
  not a conviction. Thresholds are uncalibrated placeholders. Wired into `run_hooks`.
- **Cooldown / precommitment guardrails** (`core/cooldown.py` + storage): when `run_review`
  returns PAUSE/DECREASE_EXPOSURE/EXIT, a cooldown record is auto-written (default 24/48/72h,
  configurable via `LRE_COOLDOWN_HOURS`). `exposure set` raising total exposure is **blocked**
  during an active cooldown unless `--override --reason` is given (logged in `override_log`
  for audit). `lre cooldown <rel> [list|clear]`. Override is always possible — the cooldown
  imposes a deliberate pause, never a trap. Only exposure-*raising* actions are gated;
  observing / reviewing / resolving remain allowed.
- **Timeline view** (`core/timeline.py` + `lre timeline <rel>`): merges observations,
  boundary hits, inconsistencies (with resolution), and reviews into one chronological
  stream grouped by day. Honest about scope: state/exposure are upserted (no history), so
  the timeline shows only timestamped events, not a continuous score trace.

## Test results

`pytest` → **81 passed** (26 original + 10 contradiction + 6 evidence + 6 chat-import
+ 6 signals + 6 resolution + 6 patterns + 6 timeline + 9 cooldown). Plus an end-to-end
CLI smoke run confirming: love-bombing pattern fires on 3 CHEAP + 2 COSTLY early;
review returns PAUSE and auto-creates a cooldown; `exposure set` raising total is
blocked; `--override` is logged; timeline shows all events grouped by day.

## Design problems / open questions found

1. **Attraction-exceeds-trust uses observation *count* as a proxy for "evidence
   supporting trust"** — crude. It should eventually check whether observations
   actually corroborate trust, not just that observations exist.
2. ~~**Exposure-vs-evidence was a linear placeholder**~~ — **further improved** via
   quality-weighting (confidence × signal-type) on top of breadth/triangulation/rigor/
   concreteness. True calibration (real likelihood data, Bayesian posterior) is still
   on the roadmap; current coefficients remain transparent placeholders.
3. **Boundary hits are recorded manually** (`boundary hit --evidence …`). There is no
   automated trigger yet (deliberate, to honor "no single vague observation convicts").
4. ~~**No real "inconsistency" detection / no resolution UX**~~ — **resolved**: detection
   via structured claims, three-state resolution (sequential / genuine / dismissed),
   audit trail via `inconsistency list`, acknowledged breakdown in `status`.
5. **Emotional-state is self-reported** and affects only the high-emotion+major-decision
   rule. That is intended (principle #4 is about the user's own state).
6. ~~**Contradiction tracker relied on structured claims; chat import was the lever**~~ —
   chat import + signal classification both implemented. Coverage still depends on the
   user's claim-rules and tagging discipline.
7. **Signal classification is keyword-based** — `suggest_signal_type` is an obvious
   lexicon, not a model. It will miss paraphrases and is intentionally conservative
   (returns None on ambiguity). A real classifier would need labeled data we don't have.
8. **Chat import ordering** uses insertion time (`_now()`); same-second messages
   collapse. Acceptable for v0.2.
9. **Acknowledged-as-genuine_inconsistency still leaves the active count** — by design,
   resolving closes the item. A user acknowledging a real red flag should separately
   lower `trust` / raise `uncertainty` via `state set`. Documented but not enforced.

## Next 3 most valuable steps

1. **State / exposure change history** — currently upserted (last-write-wins), so the
   timeline can't show score deltas. An event log would make the timeline a true
   continuous trace and enable "exposure grew 3 points in 2 days while evidence grew 0"
   detection.
2. **Counterfactual review / RedTeamMe** — re-run a past decision against only the
   evidence available at that time, to audit whether you would have decided differently
   (and whether your current self is rationalizing the past).
3. **Mutual verification checklist** — a structured, user-configurable checklist of
   verifiable facts (introduced to friends, met at workplace, etc.) whose costly-signal
   status can be confirmed, sharpening the boundary between cheap talk and verified
   costly signals.
