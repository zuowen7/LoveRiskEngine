# LoveRiskEngine (v0.1)

A **personal relationship decision-support framework**. It helps you record
observations, audit your own cognitive biases, track risk exposure, and trigger
a structured review before major relationship decisions — under conditions of
incomplete information.

## What it is NOT

- Not a "rate / judge the person" or "detect cheaters" system.
- Not a surveillance, tracking, or secret-investigation tool.
- Not a social-engineering database, PII scraper, or black/grey-market lookup.
- Not an AI that unilaterally declares someone "good" or "bad".

## Core design principles

1. **Attraction != Trust** — how much you like someone is tracked separately
   from how much *evidence* supports trusting them. Attraction changes never
   auto-modify trust.
2. **Observation != Interpretation** — every record stores the objective
   observation, your interpretation, and at least one alternative explanation,
   plus source and confidence.
3. **Exposure must not outrun Evidence** — time / emotional / privacy /
   financial / life-decision exposure are tracked separately; when exposure
   grows faster than evidence, a warning fires.
4. **Default action is CONTINUE_OBSERVING** — the system never defaults to
   TRUST or REJECT. Outputs: `CONTINUE_OBSERVING`, `WAIT`, `PAUSE`,
   `DECREASE_EXPOSURE`, `EXIT`.
5. **Hard boundaries** — you pre-commit your own lines. A hit can suggest
   `EXIT` **only when backed by recorded evidence**; a single vague observation
   never auto-convicts.
6. **Bias auditing** — v0.1 ships 5 detectors (see below).
7. **Privacy first** — local SQLite only, no unnecessary PII, no scraping or
   locating interfaces.

## Install (dev)

```bash
python -m venv .venv && .venv/Scripts/activate   # or: source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
lre init
lre relationship add "Alex"
lre observe Alex --category honesty \
    --observation "Cancelled our plans twice this week" \
    --interpretation "They are losing interest" \
    --alternative "They had a heavy work deadline" \
    --source self --confidence 4 --signal-type COSTLY
lre state set Alex --attraction 8.5 --trust 4.0 --uncertainty 7.0 --emotional ANXIOUS
lre exposure set Alex --time 3 --emotional 4 --privacy 1
lre boundary add --description "Never disrespects my stated boundaries" --severity HARD
lre inconsistency add Alex --description "Story about Tuesday differs from Wednesday"
# Structured claims enable the contradiction tracker:
lre observe Alex --observation "He said he is single" --claim "relationship_status=single"
lre observe Alex --observation "He mentioned his wife" --claim "relationship_status=married"
lre contradictions Alex --save     # auto-flag conflicting claims
lre status Alex
lre review Alex
lre list
```

### `status` example output

```
Relationship: R001

Attraction       8.5 / 10
Trust            4.0 / 10
Uncertainty      7.0 / 10
Emotional        ANXIOUS

Exposure
  Time           3.0
  Emotional      4.0
  Privacy        1.0
  Financial      0.0
  Life decision  0.0

Evidence support
  Observations   5
  Sources        2
  w/ Alt expl.   5
  w/ Claims      3
  Support units  16.5

Warnings:
- Attraction (8.5) significantly exceeds supported trust (4.0).
- 1 unresolved inconsistencies.
- Exposure remains within evidence support (16.5 units; 5/5 with alternative explanations, 3/5 with claims).

Unresolved inconsistencies: 1

Conflicting claims (top):
- [relationship_status] 'married' vs 'single' (O002, O001)

Recommendation:
CONTINUE_OBSERVING
```

## v0.1 bias detectors (deliberately uncalibrated heuristics)

| Rule | Trigger |
|------|---------|
| `attraction_exceeds_trust` | attraction − trust ≥ 3 **and** < 3 observations |
| `repeated_rationalization` | ≥ 3 consecutive self-flagged rationalizations |
| `exposure_outpaces_evidence` | exposure total > **evidence support units** (see below) |
| `high_emotion_major_decision` | emotional state is high **and** life-decision exposure > 0 |
| `unresolved_inconsistencies` | ≥ 1 unresolved inconsistency recorded |
| `love_bombing_pattern` | early window: ≥3 CHEAP + ≥1 COSTLY + ≥5 total signals |

> These thresholds are **placeholders**, not calibrated likelihoods. v0.1 does
> **not** produce pseudo-precise scores like "trustworthiness 87.34%".

## Evidence support (quality-calibrated, replaces the raw observation count)

The `exposure_outpaces_evidence` rule no longer compares exposure against a bare
observation count. Instead it uses a transparent, **quality-weighted** evidence
support composite. Each observation contributes a base unit scaled by:

- **confidence_weight** — `0.5 + confidence/10` (confidence=5 is neutral,
  confidence=10 contributes 1.5×, confidence=0 contributes 0.5×)
- **signal_weight** — from the cheap-talk/costly-signal classification below:
  COSTLY=2.0 (hard to fake), CHEAP=0.5 (easy to fake), UNSPECIFIED=1.0

Plus structural bonuses that reward good evidence hygiene:
- **breadth** — number of observations (the base unit)
- **triangulation** — 0.5 per distinct source beyond the first
- **rigor** — 1.0 per observation that also records an alternative explanation
- **concreteness** — 1.0 per observation carrying ≥1 structured claim

This rewards intellectual honesty (you wrote an alternative reading),
falsifiability (you captured a concrete claim), and signal cost (you noted
whether the assertion was easy or hard to fake) — instead of treating every
observation as interchangeable. It is **not** a probability and coefficients
remain uncalibrated placeholders; `status` prints every component so the basis
is fully auditable.

```bash
lre status Alex
# ...
# Evidence support
#   Observations   5
#   Sources        2
#   w/ Alt expl.   5
#   w/ Claims      3
#   Costly signals 2
#   Cheap talk     1
#   Support units  21.0
```

## Cheap-talk / costly-signal classification

Not all assertions weigh equally. Signaling theory distinguishes:

- **Cheap talk** — assertions that cost the sender nothing and are easy to fake
  ("trust me", "I promise", "I would never"). Low evidentiary weight.
- **Costly signals** — actions or claims that impose real cost and are hard to
  fake ("introduced me to his parents", "paid back the loan", "showed up on
  time", "co-signed"). High evidentiary weight.

Set the type at observe time; if you omit it, a crude keyword heuristic prints a
**hint** (never auto-sets — you decide):

```bash
lre observe Alex --observation "he introduced me to his parents" --signal-type COSTLY
lre observe Alex --observation "he said trust me, I promise"          # hint: CHEAP
```

Costly signals weigh 4× cheap talk in the evidence-support model
(`2.0 / 0.5`), so the exposure-outpaces-evidence warning now reflects *what
kind* of evidence you have, not just how many rows.

## Love-bombing pattern detector

Flags the classic manipulation precursor: a burst of cheap affection talk
("I love you", "trust me", promises) **paired with** intense costly gestures
(introducing to family very early, big gifts, moving fast) compressed into the
opening phase of the relationship. The *pairing* matters — cheap talk alone is
just enthusiasm; cheap talk + costly gestures early is the signature.

```bash
lre observe Alex --observation "he said trust me, I promise" --signal-type CHEAP
lre observe Alex --observation "he introduced me to his parents" --signal-type COSTLY
# ...after a few such observations in the early window, `status`/`review` fires:
#   love_bombing_pattern -> PAUSE
```

Thresholds (first 10 observations; ≥3 CHEAP + ≥1 COSTLY + ≥5 total signals) are
uncalibrated placeholders. The rule proposes **PAUSE**, not a conviction — it
exists to slow you down, not to label anyone.

## Contradiction tracker

The tracker auto-detects conflicting observations so you no longer have to
manually flag every inconsistency.

- Each `observe` can carry one or more **structured claims** as
  `attribute=value` (`--claim`, repeatable).
- `lre contradictions <rel>` compares claims across the relationship. The same
  normalized attribute asserted with **two different values** is surfaced as a
  conflict candidate — deterministically, with no model and no confidence score.
- `--save` persists new candidates as unresolved inconsistencies (idempotent).
  They then flow into `status` / `review` like manually added ones.
- The tool only **surfaces** conflicts for your review; it never auto-judges
  "they lied". Sequential-but-true changes (e.g. job switched) are exactly the
  kind of thing you must arbitrate, so surfacing them is correct behavior.

```bash
lre observe Alex --claim "relationship_status=single"
lre observe Alex --claim "relationship_status=married"
lre contradictions Alex --save
```

### Resolving contradictions (without deleting observations)

Not every detected conflict is a lie — some are sequential changes (they
switched jobs) or false positives (different attributes that looked alike).
You can close a conflict with a **resolution type** so the audit trail is
honest, and the underlying observations are never deleted:

```bash
lre inconsistency list Alex                 # open conflicts
lre inconsistency resolve I001 \
    --as sequential_change --note "switched jobs in March"
lre inconsistency resolve I002 \
    --as genuine_inconsistency --note "single vs married — real red flag"
lre inconsistency resolve I003 \
    --as dismissed --note "different attributes, not a real conflict"
lre inconsistency list Alex --resolved      # audit trail
```

Resolution types:
- `sequential_change` — values changed over time, not a lie
- `genuine_inconsistency` — real contradiction, acknowledged as a yellow flag
- `dismissed` — reviewed, not a real conflict

All three close the item (it no longer counts toward "unresolved"). Resolved
items stay visible in `status` as `Acknowledged (closed): N (x sequential, y
genuine, z dismissed)` so they are never silently forgotten.

## Cooldown / precommitment guardrails

Turns the engine's recommendation into a real guardrail. When a `review`
returns **PAUSE / DECREASE_EXPOSURE / EXIT**, a cooldown is automatically
written. While active, any `exposure set` that would *raise* total exposure is
**blocked** unless you explicitly override (which is logged for audit).

```bash
lre review Alex
# Recommendation: PAUSE
# Cooldown C001 started — exposure-raising actions are gated until it expires.

lre exposure set Alex --emotional 5
# BLOCKED: an active cooldown prevents raising exposure.
#   - C001 [PAUSE] 23h59m remaining (reason: love_bombing_pattern)
# To override (logged for audit): lre exposure set Alex ... --override --reason "..."

lre exposure set Alex --emotional 5 --override --reason "deliberate, after reflection"
# OVERRIDE logged: raising exposure 0.0 -> 5.0 during cooldown.

lre cooldown Alex          # list active cooldowns + override history
lre cooldown Alex clear    # manually clear (e.g. after the situation genuinely resolved)
```

Default durations: PAUSE=24h, DECREASE_EXPOSURE=48h, EXIT=72h. Override
uniformly with `LRE_COOLDOWN_HOURS=6`. Override is **always possible** — the
cooldown imposes a deliberate pause, never a trap. Recording observations,
running reviews, and resolving inconsistencies remain allowed throughout,
because those are exactly what you should do during a cooldown.

## Timeline view

A chronological merge of every timestamped event — observations (with signal
type + claims), boundary hits, inconsistencies (with resolution), and reviews —
grouped by day. Useful for spotting whether a conflict is a sequential change
or a genuine inconsistency, and for reviewing your own override pattern.

```bash
lre timeline Alex
# --- 2026-08-30 ---
#   [observation] O001 general [CHEAP]: he said trust me, I promise
#   [observation] O004 general [COSTLY]: he introduced me to his parents
#         | claims: met_family=yes
#   [review] RV001 REVIEW -> PAUSE
#         love_bombing_pattern; ...
```

> Honesty note: `relationship_state` and `exposure` are upserted
> (last-write-wins), so the timeline shows only events with an explicit
> timestamp — not a continuous trace of every score change. Tracking
> state/exposure deltas is a separate roadmap item.

## Local chat import & analysis

Turn a **local** chat export into structured observations offline — no network,
no PII fields, no scraping. Two formats are accepted:

- **NDJSON**: one JSON object per line — `{"timestamp": "...", "speaker": "...", "text": "..."}`
- **Delimited**: `TIMESTAMP | SPEAKER | TEXT` per line

Optional `--rules` points at a JSON claim-rules file (see
`examples/claim_rules.json`) so the importer extracts structured `Claim`s via
your own regex. After import, contradictions are auto-detected and reported.

```bash
lre chat import Alex --file chat.txt --rules examples/claim_rules.json
# Imported 3 observation(s) from 'chat.txt' into R001.
# Extracted 5 structured claim(s) via 3 rule(s).
# Detected 2 potential contradiction(s). Review with: lre contradictions Alex --save
```

`status` also prints the **top conflicting claims** directly, so you don't have
to run `contradictions` separately:

```
Conflicting claims (top):
- [relationship_status] 'married' vs 'single' (O002, O001)
- [job] 'barista' vs 'office' (O001, O003)
```

## Tests

```bash
pytest
```

## Project layout

```
love_risk_engine/
  core/          domain model + bias detectors + decision engine + contradiction
                 tracker + evidence support (quality-calibrated) + cheap/costly
                 signal classification + love-bombing pattern detector +
                 cooldown/precommitment + timeline + offline chat import
  storage/       SQLite schema + database access
  services/      review workflow (auto-creates cooldowns on blocking decisions)
  cli.py         command-line interface
examples/        sample claim-rules.json for chat import
tests/
```

## Future roadmap (NOT in v0.1)

Implemented: ✅ contradiction tracker, ✅ evidence-support (quality-calibrated),
✅ cheap-talk/costly-signal classification, ✅ love-bombing pattern detector,
✅ contradiction resolution UX, ✅ cooldown/precommitment guardrails,
✅ timeline view, ✅ local chat import & analysis, ✅ top-conflicts in `status`.

Still pending: counterfactual review, RedTeamMe, LLM Devil's Advocate, model
calibration report, relationship backtesting, Bayesian updater, value of
information, real-option / optimal stopping model, mutual verification
checklist, public-information consistency check (legal public sources only),
state/exposure change history (for a continuous timeline trace).
