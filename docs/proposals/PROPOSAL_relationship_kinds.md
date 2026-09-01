# Proposal: Relationship Kinds & Per-Kind Profiles

> Status: **Draft — reviewed with the user; S1–S3 implemented (2026-08-31).**
> Origin: an external pitch proposed "relationship modes" (mentor / boss / parent …)
> with numeric power-asymmetry indices, exit-cost mechanics, and a rebrand to
> "Humanity Firewall". This document evaluates that pitch against this repo's
> written principles and keeps only what survives the collision.

---

## 1. Problem

`relationships` has no notion of *what kind* of relationship is being evaluated.
The domain model (`core/relationship.py`) carries only `id / alias / status /
created_at`, and every v0.1 detector in `core/bias_detector.py` + `core/patterns.py`
implicitly assumes romantic-love dynamics (attraction vs trust, love-bombing).

A user who wants to evaluate a mentor's unkept promises, or a parent's boundary
violations, has no honest place in the engine. This gap is real. The pitch's
instinct — make relationship type a first-class dimension — is correct.

Everything else in the pitch is judged below.

## 2. The pitch, evaluated point by point

| Pitch element | Verdict |
|---|---|
| Relationship type as a first-class dimension; a "mode" CLI | **Adopt, rewritten.** A `kind` field on the relationship + a per-kind profile table. No "mode factory". |
| Power-asymmetry index (0.9 boss / 0.6 parent / 0.2 lover) driving "buffer reply" advice | **Reject.** Violates DESIGN.md Don't #1 (no pseudo-precise scores) *and* turns the engine into a compliance coach — see §3.6. |
| Exit cost (+∞ blood / high mentor / low stranger); high ⇒ more sensitive PUA detection | **Adopt in part.** Ordinal HIGH/MED/LOW, earlier warnings for high exit cost. Reject the "+∞" framing and the flip side ("low ⇒ don't bother recording"). |
| Memory decay (PERMANENT for lovers, 3-month promise window for boss/mentor) | **Adopt as display windowing.** Never delete data; window only what `status`/`review` surface. |
| "画饼检测" (mentor promise detection) | **Already ~80% built.** `--claim` + contradiction tracker + cheap/costly signals + three-state resolution. What's genuinely missing is promise *ageing* — see §4.3. |
| "没法 DROP，只能 ARCHIVE" for blood relations | **Already the repo's data philosophy.** Boundaries are retired, observations are never deleted. Nothing to build. |
| Rebrand to "Humanity Firewall" / 赛博观世音 | **Reject.** Conflicts with the "calm instrument" positioning (DESIGN.md §1, Don't #3). The tool is decision support, not a firewall. |
| "Mode factory" / plugin architecture | **Reject.** The decision core is a priority walk over ~6 hooks (`core/decision.py`, 44 lines). A registry dict suffices. |

## 3. What gets adopted, rewritten to fit the house rules

### 3.1 `Kind` and the schema

- `core/relationship.py`: add `Kind` (`StrEnum`), initial vocabulary
  `LOVER / FRIEND / PARENT / BOSS / MENTOR / COLLEAGUE / STRANGER`.
  `Relationship` gains `kind: str`.
- `storage/schema.py`: schema v2 — `relationships.kind TEXT NOT NULL DEFAULT
  'LOVER'` (enum-aligned). Bump `SCHEMA_VERSION` to 2; add `_migrate_v1_to_v2` in
  `storage/database.py` (following the existing versioned-migration pattern,
  upgrade path tested).
- **Backward-compat promise:** every existing row defaults to `LOVER`, and the
  `LOVER` profile equals today's behavior exactly — zero change for current users.

### 3.2 The profile table (`core/profiles.py`)

A dataclass registry, not a factory:

```python
@dataclass(frozen=True)
class RelationshipProfile:
    kind: Kind
    enabled_hooks: tuple[str, ...]  # which detectors run for this kind
    promise_window_days: int | None  # display window for promise claims
    power_asymmetry: Ordinal  # HIGH / MED / LOW — context only
    exit_cost: Ordinal  # HIGH / MED / LOW — sensitivity direction
    boundary_seeds: tuple[str, ...]  # suggested default boundaries at creation
    voice: str  # phrasing guidance for warnings


PROFILES: dict[Kind, RelationshipProfile] = {...}
```

Hard rules for the registry:

- **Ordinals, never numbers.** No 0.9/0.6/0.2, no +∞. Three bands, and every
  band's effect is documented as an **uncalibrated editorial default**, in the
  same voice as the existing `THRESHOLDS ARE PLACEHOLDERS` header in
  `core/bias_detector.py`.
- **`power_asymmetry` is context, not computation.** It affects what `status`
  prints and how warnings are phrased ("high power asymmetry: verify before
  escalating" — information for the user). It never feeds a formula, and it
  **never produces reply advice**. No reply generation exists in this product,
  period.
- **`exit_cost` affects only sensitivity *direction*.** HIGH ⇒ earlier warnings
  (the user who cannot easily leave needs to know sooner, not later). LOW ⇒
  exactly today's behavior — recording continues in full. "Low exit cost ⇒ stop
  recording" is rejected: low exit cost is not low harm.
- **No inescapability language.** The engine must never phrase any warning as
  "you cannot leave". High exit cost is phrased as "plan the exit path
  separately", per §4.4.
- **Profiles are code-frozen in v1** (a dict under test coverage). User-editable
  profiles are a later, separate proposal — it drags in schema, validation and
  footguns the v1 does not need.

### 3.3 Engine changes

1. **Kind-aware hook selection.** `run_hooks(ctx)` reads the relationship's
   profile and runs `profile.enabled_hooks`. `LOVER` enables exactly today's six
   hooks — no behavior change.
2. **New hook: `promise_expiry` (BOSS / MENTOR).** The genuinely new detector.
   Complements the contradiction tracker (which needs *two* conflicting
   observations): it flags future-directed `--claim` values (e.g. `will
   recommend`, `will fund`) that remain uncontradicted after
   `promise_window_days`. Output is a `BiasFinding` proposing `WAIT`, never a
   conviction; the message states the window and the claim, so the basis stays
   auditable. Future-tense matching is a conservative lexicon (same honesty
   contract as `suggest_signal_type`: keyword hints, misses paraphrases, never
   auto-sets).
3. **Display windowing, not deletion.** For windowed kinds, `status`/`review`
   surface promise claims inside the window; older unfulfilled claims collapse
   into an "older promises (N)" block, still one command away. Rows are never
   removed — same rule as boundary retirement.
4. **Exit-cost sensitivity direction.** `exit_cost == HIGH` may shift the
   uncalibrated thresholds of existing detectors toward earlier warning (e.g.
   `attraction_exceeds_trust` gap 3.0 → 2.0 for that kind). Constraint from
   DESIGN.md Do's #3: **any shifted threshold must be printed in the finding
   message**, so the basis stays fully auditable and nobody mistakes an
   editorial offset for calibration.

### 3.4 CLI

- `lre relationship add <alias> --kind MENTOR` (default `LOVER`).
- `lre relationship set <id> --kind <kind>` — kinds are an attribute of the
  relationship, not a global switch.
- *(Decided 2026-08-31: no `lre mode` alias — the command surface stays minimal.)*
- `lre status <rel>` prints the kind and, when the profile is not the default,
  the ordinal context line ("power asymmetry: HIGH — verify before escalating",
  "exit cost: HIGH — warnings are brought forward").

### 3.5 Storage

- `add_relationship(alias, kind=...)`, `set_relationship_kind(rid, kind)`;
  `get_relationship` / `list_relationships` return `kind` on the domain object
  (house rule: no raw `sqlite3.Row` leaves `storage/`).
- Migration path v1→v2 tested like the existing v0→v1 path.

### 3.6 Explicit non-goals (what the pitch wanted and we refuse to build)

1. **No reply coaching.** "Higher power asymmetry ⇒ suggest a buffer reply" is a
   different product, and a self-defeating one: an engine that detects
   manipulation while advising compliance with it. Power asymmetry is *shown* to
   the user; it is never *obeyed* by the engine.
2. **No numeric indices.** No 0.9/0.6/0.2, no +∞, no weighted formula over
   power/exit/decay. Three ordinal bands, documented as uncalibrated editorial
   defaults.
3. **No data cleanup.** Windowing changes what is displayed, never what is
   stored. No "历史垃圾" labeling — warning voice stays calm and evidence-based
   (DESIGN.md Don't #3).
4. **No rebrand, no new name.** LoveRiskEngine stays. No "Humanity Firewall", no
   赛博观世音. Marketing hype is not a design input.
5. **No factory/plugin architecture.** One frozen registry dict. If this ever
   needs to become pluggable, that is a separate proposal with its own
   justification.

## 4. Sequencing (three slices, three PRs — house rule: one concern, < ~400 lines)

| Slice | Scope | Size guess |
|---|---|---|
| **S1 — the field** | `Kind` + schema v2 + migration + domain object + `--kind` on `relationship add`/`set` + `PROFILES` registry (frozen, `LOVER` = today) + kind/context line in `status`. No hook behavior change. | ~150–200 lines + tests |
| **S2 — promise expiry** | `promise_expiry` hook for BOSS/MENTOR, future-claim lexicon, display windowing in `status`/`review`. | ~150–200 lines + tests |
| **S3 — sensitivity direction** | `exit_cost` HIGH threshold offsets, surfaced in finding messages; `boundary_seeds` at relationship creation; `voice` polish. | ~100–150 lines + tests |

Every slice passes the four-gate (`ruff check` / `ruff format --check` /
`mypy love_risk_engine` / `pytest`), coverage floor 95%, `cli.py` 100%.

S1 is independently valuable and reviewable without S2/S3. Nothing lands
unreviewed; this document is the review artifact.

**S1–S3 are implemented** (2026-08-31), test-first per `PLAN_S2_S3.md`.
S1: schema v2, `Kind`, `core/profiles.py`, CLI surface, migration path.
S2: `core/promises.py` (`promise_expiry` + display windowing + `lre promises`).
S3: exit-cost sensitivity for the two thresholded rules, boundary-seed
suggestions, review context line. Four-gate green, coverage 98.3%,
`cli.py` 100%.

## 5. Decisions (recorded with the user before S1)

1. **Kind vocabulary.** The proposed seven kinds; 相亲对象 maps to `STRANGER`.
2. **CLI surface.** `relationship set --kind` only. No `lre mode` alias.
3. **Promise window.** 90 days for BOSS / MENTOR / COLLEAGUE; none elsewhere.
4. **Default ordinals.** The table below, approved as-is. In S1 these values
   affect the `status` context line only; they touch detector thresholds in S3.
5. **Future-tense claim matching.** Deferred to S2 (recommendation: keyword
   lexicon as hint + user claim rules, the `signals.py` contract).

   | Kind | power_asymmetry | exit_cost | promise_window_days |
   |---|---|---|---|
   | LOVER | LOW | MED | — |
   | FRIEND | LOW | LOW | — |
   | PARENT | MED | HIGH | — |
   | BOSS | HIGH | HIGH | 90 |
   | MENTOR | HIGH | HIGH | 90 |
   | COLLEAGUE | MED | MED | 90 |
   | STRANGER | LOW | LOW | — |

## 6. Guardrail checklist (checked before this leaves draft)

- [x] No pseudo-precise numbers — ordinals only (DESIGN.md Don't #1)
- [x] No 鉴渣/judgemental tone, no "garbage" labels (Don't #3)
- [x] Every shifted threshold is printed in the warning (Do's #3)
- [x] Nothing auto-sets; the user always decides (house precedent: `signals.py`)
- [x] No deletion; windowing affects display only (precedent: boundary retirement)
- [x] No reply generation of any kind
- [x] Migration versioned and tested (schema.py header rules)
- [x] No new runtime dependency (registry is a plain dataclass dict; `dependencies` stays `[]`)
- [x] No PII fields added
- [x] Backward compatible: existing rows default to `LOVER` = today's behavior

---

*This document supersedes the external pitch. The pitch's insight (relationship
type is a missing dimension) is kept; its mechanics (numeric indices, compliance
coaching, rebranding) are not.*
