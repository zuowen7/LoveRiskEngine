"""LoveRiskEngine command-line interface (`lre`).

Usage:
  lre init
  lre relationship add <alias> [--kind KIND]
  lre relationship set <id> --kind KIND
  lre observe <relationship> --observation "..." [--interpretation ...]
  lre observe <relationship> [--alternative ...] [--source ...]
  lre status <relationship>
  lre review <relationship>
  lre boundary add --description "..." [--severity HARD|SOFT]
  lre boundary hit <boundary_id> --relationship <rel> --evidence "..."
  lre boundary retire <boundary_id>              # stop enforcing, keep audit trail
  lre list
  lre state set <relationship> [--attraction N] [--trust N] [--uncertainty N]
  lre state set <relationship> [--emotional STATE]
  lre exposure set <relationship> [--time N] [--emotional N] [--privacy N]
  lre exposure set <relationship> [--financial N] [--life-decision N]
  lre inconsistency add <relationship> --description "..."
  lre inconsistency resolve <id> [--note "..."]
  lre inconsistency resolve <id> [--as sequential_change|dismissed|genuine]
  lre inconsistency list <relationship> [--resolved]
  lre observe <relationship> --claim "relationship_status=single"
  lre observe <relationship> --signal-type COSTLY
  lre contradictions <relationship> [--save]    # auto-detect conflicting observations
  lre promises <relationship>                    # promise claims and their ages
  lre history <relationship>                     # state/exposure change log
  lre export <file>                             # lossless backup bundle
  lre restore <file>                            # restore (replaces all data)
  lre db check                                  # integrity checks
  lre chat import <relationship> --file chat.txt [--rules claim_rules.json]
  lre timeline <relationship>                    # chronological event stream
  lre cooldown <relationship> [list|clear]       # precommitment guardrails
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .core.bias_detector import BiasFinding
from .core.chat_import import (
    load_claim_rules,
    parse_file,
    to_observations,
)
from .core.contradiction import ContradictionCandidate, detect_contradictions
from .core.cooldown import Cooldown, format_remaining, is_active
from .core.decision import Decision
from .core.evidence import EvidenceSupport
from .core.exposure import Exposure
from .core.history import describe_exposure_change, describe_state_change
from .core.hooks import ReviewContext
from .core.inconsistency import Inconsistency
from .core.observation import Claim
from .core.profiles import RelationshipProfile, get_profile
from .core.promises import PromiseReport, collect_promises
from .core.relationship import Kind, Relationship
from .core.signals import SignalType, suggest_signal_type
from .core.state import EmotionalState, RelationshipState
from .core.timeline import build_timeline, format_timeline
from .core.timeutil import utc_now_iso
from .services.export import restore_bundle, save_bundle
from .services.review import analyze, build_context, run_review
from .storage.database import Database
from .storage.paths import resolve_db_path


def get_db() -> Database:
    path = resolve_db_path(os.environ.get("LRE_DB_PATH"))
    db = Database(path)
    db.init()
    return db


def resolve_relationship(db: Database, token: str) -> Relationship:
    rel = db.get_relationship(token)
    if rel is None:
        sys.exit(f"Error: relationship not found: {token!r}")
    return rel


def _profile_context(profile: RelationshipProfile) -> str | None:
    """One-line ordinal context for non-default kinds; None for LOVER.

    Shown by both `status` and `review`: the band values are context for the
    user's judgement, never input to a formula.
    """
    if profile.kind is Kind.LOVER:
        return None
    parts = [
        f"power asymmetry: {profile.power_asymmetry.value}",
        f"exit cost: {profile.exit_cost.value}",
    ]
    if profile.voice:
        parts.append(profile.voice)
    return " | ".join(parts)


def _active_cooldowns(db: Database, rid: str) -> list[Cooldown]:
    """Return cooldowns that are both flagged active AND not yet expired."""
    now = utc_now_iso()
    return [
        c for c in db.list_cooldowns(rid, active_only=True) if is_active(c, now=now)
    ]


# ---------------------------------------------------------------------------
# command handlers
# ---------------------------------------------------------------------------
def cmd_init(_args: argparse.Namespace, db: Database) -> None:
    db.init()
    print(f"Initialized LoveRiskEngine database at {db.path}")


def cmd_relationship_add(args: argparse.Namespace, db: Database) -> None:
    rid = db.add_relationship(args.alias, kind=args.kind)
    print(f"Created relationship {rid} (alias: {args.alias}, kind: {args.kind})")
    seeds = get_profile(args.kind).boundary_seeds
    if seeds:
        print("Suggested boundaries for this kind (add only what matches you):")
        for seed in seeds:
            print(f"  - {seed}")


def cmd_relationship_set(args: argparse.Namespace, db: Database) -> None:
    if not db.set_relationship_kind(args.id, args.kind):
        sys.exit(f"Error: relationship not found: {args.id!r}")
    print(f"Set kind {args.kind} for {args.id}")


def cmd_observe(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    claims: list[Claim] = []
    for item in args.claim:
        if "=" not in item:
            sys.exit(f"Error: --claim must be attribute=value, got {item!r}")
        k, v = item.split("=", 1)
        if not k.strip():
            sys.exit(f"Error: --claim attribute is empty in {item!r}")
        claims.append(Claim(attribute=k.strip(), value=v.strip()))

    if args.signal_type:
        signal_type = SignalType[args.signal_type]
    else:
        hint = suggest_signal_type(args.observation)
        signal_type = SignalType.UNSPECIFIED
        if hint is not None:
            print(
                f"(hint) observation text suggests signal type "
                f"{hint.value}. Use --signal-type to confirm or override."
            )

    oid = db.add_observation(
        rel.id,
        args.category,
        args.observation,
        args.interpretation,
        args.alternative,
        args.source,
        args.confidence,
        args.rationalize,
        args.inconsistent,
        claims=claims,
        signal_type=signal_type,
    )
    extra = f" with {len(claims)} claim(s)" if claims else ""
    if signal_type is not SignalType.UNSPECIFIED:
        extra += f" [{signal_type.value}]"
    print(f"Recorded observation {oid} for {rel.id}{extra}")


def _compute_status(
    db: Database, relationship_id: str
) -> tuple[ReviewContext, list[BiasFinding], Decision]:
    ctx = build_context(db, relationship_id)
    findings, decision = analyze(ctx)
    return ctx, findings, decision


def cmd_status(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    ctx, findings, decision = _compute_status(db, rid)
    candidates = detect_contradictions(ctx.observations)
    candidates.sort(key=lambda c: (c.attribute, c.obs_a_id, c.obs_b_id))
    top = candidates[:3]
    acknowledged = db.acknowledged_inconsistencies(rid)
    promises = None
    if ctx.profile.promise_window_days is not None:
        promises = collect_promises(ctx.observations, ctx.profile.promise_window_days)
    print(
        format_status(
            rid,
            ctx.state,
            ctx.exposure,
            findings,
            decision,
            ctx.inconsistency_count,
            ctx.evidence_support,
            top,
            more_conflicts=len(candidates) > len(top),
            acknowledged=acknowledged,
            kind=rel.kind,
            profile=ctx.profile,
            promises=promises,
        )
    )


def format_status(
    rid: str,
    state: RelationshipState,
    exposure: Exposure,
    findings: list[BiasFinding],
    decision: Decision,
    inconsistency_count: int,
    evidence_support: EvidenceSupport,
    contradictions: list[ContradictionCandidate] | None = None,
    more_conflicts: bool = False,
    acknowledged: list[Inconsistency] | None = None,
    kind: str | None = None,
    profile: RelationshipProfile | None = None,
    promises: PromiseReport | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"Relationship: {rid}")
    if kind is not None and profile is not None:
        lines.append(f"Kind             {kind}")
        context = _profile_context(profile)
        if context:
            lines.append("Context          " + context)
    lines.append("")
    lines.append(f"Attraction       {state.attraction:.1f} / 10")
    lines.append(f"Trust            {state.trust:.1f} / 10")
    lines.append(f"Uncertainty      {state.uncertainty:.1f} / 10")
    lines.append(f"Emotional        {state.emotional_state.value}")
    lines.append("")
    lines.append("Exposure")
    lines.append(f"  Time           {exposure.time:.1f}")
    lines.append(f"  Emotional      {exposure.emotional:.1f}")
    lines.append(f"  Privacy        {exposure.privacy:.1f}")
    lines.append(f"  Financial      {exposure.financial:.1f}")
    lines.append(f"  Life decision  {exposure.life_decision:.1f}")
    lines.append("")
    lines.append("Evidence support")
    lines.append(f"  Observations   {evidence_support.observation_count}")
    lines.append(f"  Sources        {evidence_support.distinct_sources}")
    lines.append(f"  w/ Alt expl.   {evidence_support.with_alternative}")
    lines.append(f"  w/ Claims      {evidence_support.with_claims}")
    lines.append(f"  Costly signals {evidence_support.costly_count}")
    lines.append(f"  Cheap talk     {evidence_support.cheap_count}")
    lines.append(f"  Support units  {evidence_support.support_units:.1f}")
    lines.append("")
    lines.append("Warnings:")
    if findings:
        for f in findings:
            lines.append(f"- {f.message}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append(f"Unresolved inconsistencies: {inconsistency_count}")
    if acknowledged:
        # breakdown by resolution type — keeps acknowledged items visible
        buckets: dict = {}
        for it in acknowledged:
            res = it.resolution or "resolved"
            buckets[res] = buckets.get(res, 0) + 1
        parts = ", ".join(f"{v} {k}" for k, v in sorted(buckets.items()))
        lines.append(f"Acknowledged (closed): {len(acknowledged)} ({parts})")
    if contradictions:
        lines.append("")
        lines.append("Conflicting claims (top):")
        for c in contradictions:
            lines.append(
                f"- [{c.attribute}] {c.value_a!r} vs {c.value_b!r} "
                f"({c.obs_a_id}, {c.obs_b_id})"
            )
        if more_conflicts:
            lines.append("  ...run `lre contradictions <rel> --save` to persist all.")
    if promises is not None and (promises.within or promises.expired):
        lines.append("")
        lines.append(f"Promises (window: {promises.window_days}d)")
        for p in promises.within:
            lines.append(
                f"  {p.attribute}={p.value!r} ({p.observation_id}, "
                f"{p.timestamp[:10]}, {p.age_days}d)"
            )
        if promises.expired:
            lines.append(
                f"Older promises ({len(promises.expired)}): "
                "run `lre promises <rel>` for details."
            )
    lines.append("")
    lines.append("Recommendation:")
    lines.append(decision.value)
    return "\n".join(lines)


def cmd_review(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    profile = get_profile(rel.kind)
    review = run_review(db, rel.id)
    print(f"Review {review.id} for {rel.id}")
    context = _profile_context(profile)
    if context:
        print(f"Context: {context}")
    print(f"Recommendation: {review.recommendation}")
    print(f"Unresolved inconsistencies: {review.unresolved_inconsistencies}")
    print("Triggered hooks:")
    if review.triggered_hooks:
        for hook in review.triggered_hooks:
            print(f"  - {hook}")
    else:
        print("  - none")
    if review.notes:
        print(f"Notes: {review.notes}")
    if review.cooldown_id:
        print(
            f"Cooldown {review.cooldown_id} started — exposure-raising actions "
            f"are gated until it expires. See: lre cooldown {args.relationship}"
        )


def cmd_boundary_add(args: argparse.Namespace, db: Database) -> None:
    bid = db.add_boundary(args.description, args.severity, args.keywords)
    print(f"Added boundary {bid}: {args.description} [{args.severity}]")


def cmd_boundary_hit(args: argparse.Namespace, db: Database) -> None:
    if db.get_boundary(args.boundary_id) is None:
        sys.exit(f"Error: boundary not found: {args.boundary_id!r}")
    rel = resolve_relationship(db, args.relationship)
    hid = db.add_boundary_hit(args.boundary_id, rel.id, args.evidence)
    print(
        f"Recorded boundary hit {hid} "
        f"(boundary {args.boundary_id}, relationship {rel.id})"
    )


def cmd_boundary_retire(args: argparse.Namespace, db: Database) -> None:
    if not db.deactivate_boundary(args.boundary_id):
        sys.exit(f"Error: boundary not found: {args.boundary_id!r}")
    print(
        f"Retired boundary {args.boundary_id}. Past hits remain in the audit "
        f"trail; `lre list` still shows it as inactive."
    )


def cmd_list(_args: argparse.Namespace, db: Database) -> None:
    rels = db.list_relationships()
    print("Relationships:")
    if not rels:
        print("  (none)")
    for r in rels:
        print(f"  {r.id}  {r.alias}  [{r.status}]  {r.kind}")
    print("")
    print("Boundaries:")
    bounds = db.list_boundaries(active_only=False)
    if not bounds:
        print("  (none)")
    for b in bounds:
        flag = "ACTIVE" if b.active else "inactive"
        print(f"  {b.id}  [{b.severity}] {b.description} ({flag})")


def cmd_state_set(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    existing = db.get_state(rid) or RelationshipState(rid)
    if args.attraction is not None:
        existing.attraction = args.attraction
    if args.trust is not None:
        existing.trust = args.trust
    if args.uncertainty is not None:
        existing.uncertainty = args.uncertainty
    if args.emotional is not None:
        existing.emotional_state = EmotionalState[args.emotional]
    db.upsert_state(existing)
    print(f"Updated state for {rid}")


def cmd_exposure_set(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    existing = db.get_exposure(rid) or Exposure(rid)
    old_total = existing.total
    updates = {
        "time": args.time,
        "emotional": args.emotional,
        "privacy": args.privacy,
        "financial": args.financial,
        "life_decision": args.life_decision,
    }
    for field_name, value in updates.items():
        if value is not None:
            setattr(existing, field_name, value)
    new_total = existing.total

    # Cooldown gate: block exposure-raising actions during an active cooldown
    # unless the user explicitly overrides. Override is logged for audit.
    if new_total > old_total and not args.override:
        active = _active_cooldowns(db, rid)
        if active:
            print("BLOCKED: an active cooldown prevents raising exposure.")
            for cd in active:
                print(
                    f"  - {cd.id} [{cd.decision}] {format_remaining(cd)} "
                    f"(reason: {cd.reason or 'n/a'})"
                )
            print(
                "To override (logged for audit): "
                f'lre exposure set {args.relationship} ... --override --reason "..."'
            )
            return
    if args.override and new_total > old_total:
        active = _active_cooldowns(db, rid)
        cd_id = active[0].id if active else None
        db.log_override(
            relationship_id=rid,
            cooldown_id=cd_id,
            reason=args.reason or "",
            timestamp=utc_now_iso(),
        )
        print(
            f"OVERRIDE logged: raising exposure {old_total:.1f} -> {new_total:.1f} "
            f"during cooldown. This is recorded in your audit log."
        )

    db.upsert_exposure(existing)
    print(f"Updated exposure for {rid} (total {old_total:.1f} -> {new_total:.1f})")


def cmd_inconsistency_add(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    iid = db.add_inconsistency(rel.id, args.description)
    print(f"Recorded inconsistency {iid} for {rel.id}")


def cmd_inconsistency_resolve(args: argparse.Namespace, db: Database) -> None:
    ok = db.resolve_inconsistency(args.id, args.resolution, args.note)
    if not ok:
        sys.exit(f"Error: inconsistency not found: {args.id!r}")
    print(f"Resolved inconsistency {args.id} as {args.resolution}")


def cmd_inconsistency_list(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    items = db.list_inconsistencies(rid, resolved=args.resolved)
    label = "resolved" if args.resolved else "open"
    print(f"{label.capitalize()} inconsistencies for {rid}:")
    if not items:
        print("  (none)")
    for it in items:
        head = f"  {it.id} [{it.kind}] {it.description}"
        if args.resolved:
            tail = f" -> {it.resolution}" if it.resolution else ""
            if it.resolution_note:
                tail += f" | {it.resolution_note}"
            print(head + tail)
        else:
            print(head)


def cmd_contradictions(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    observations = db.get_observations(rid)
    candidates = detect_contradictions(observations)
    if not candidates:
        print(f"No contradictions detected for {rid}.")
        return
    saved = 0
    for idx, c in enumerate(candidates, 1):
        already = db.find_contradiction(rid, c.attribute, c.obs_a_id, c.obs_b_id)
        if args.save and not already:
            db.save_contradiction_candidate(
                rid, c.attribute, c.value_a, c.value_b, c.obs_a_id, c.obs_b_id
            )
            saved += 1
            mark = "saved"
        elif already:
            mark = "saved"
        else:
            mark = "new"
        print(f"{idx}. [{mark}] {c.explanation}")
    if args.save:
        print(
            f"\nSaved {saved} new contradiction(s) as inconsistencies. "
            f"Resolve with: lre inconsistency resolve <id>"
        )


def cmd_promises(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    profile = get_profile(rel.kind)
    if profile.promise_window_days is None:
        print(f"Kind {rel.kind} does not track a promise window.")
        return
    observations = db.get_observations(rel.id)
    report = collect_promises(observations, profile.promise_window_days)
    if not report.within and not report.expired:
        print("No promise claims recorded.")
        return
    print(f"Promises for {rel.id} (window: {report.window_days}d):")
    if report.within:
        print("Within window:")
        for p in report.within:
            print(
                f"  - {p.attribute}={p.value!r} ({p.observation_id}, "
                f"{p.timestamp[:10]}, {p.age_days}d)"
            )
    if report.expired:
        print(f"Expired ({len(report.expired)}):")
        for p in report.expired:
            print(
                f"  - {p.attribute}={p.value!r} ({p.observation_id}, "
                f"{p.timestamp[:10]}, {p.age_days}d)"
            )


def cmd_chat_import(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    try:
        messages = parse_file(args.file)
    except FileNotFoundError:
        sys.exit(f"Error: chat file not found: {args.file!r}")
    except ValueError as exc:
        sys.exit(f"Error: could not parse {args.file!r}: {exc}")
    if not messages:
        print(f"No messages parsed from {args.file!r}.")
        return
    rules = load_claim_rules(args.rules) if args.rules else []
    observations = to_observations(messages, rules, rid, category=args.category)
    n = db.import_observations(rid, observations)
    claim_total = sum(len(o.claims) for o in observations)
    print(f"Imported {n} observation(s) from {args.file!r} into {rid}.")
    print(f"Extracted {claim_total} structured claim(s) via {len(rules)} rule(s).")
    # post-analysis: surface contradictions for the user to arbitrate
    all_obs = db.get_observations(rid)
    cands = detect_contradictions(all_obs)
    if cands:
        print(
            f"Detected {len(cands)} potential contradiction(s). "
            f"Review with: lre contradictions {args.relationship} --save"
        )
    else:
        print("No contradictions detected in imported claims.")


def cmd_timeline(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    observations = db.get_observations(rid)
    boundary_hits = db.list_boundary_hits(rid, only_hard=False)
    inconsistencies = db.list_all_inconsistencies(rid)
    reviews = db.list_reviews(rid)
    events = build_timeline(
        observations,
        boundary_hits,
        inconsistencies,
        reviews,
        state_changes=db.list_state_history(rid),
        exposure_changes=db.list_exposure_history(rid),
    )
    print(f"Timeline for {rid} ({len(events)} event(s)):")
    print(format_timeline(events))


def cmd_history(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    merged: list[tuple[str, str, str]] = []  # (timestamp, id, line)

    prev_state = None
    for sc in db.list_state_history(rid):
        merged.append(
            (
                sc.timestamp,
                sc.id,
                f"[STATE]    {sc.id} {describe_state_change(prev_state, sc)}",
            )
        )
        prev_state = sc

    prev_exposure = None
    for ec in db.list_exposure_history(rid):
        merged.append(
            (
                ec.timestamp,
                ec.id,
                f"[EXPOSURE] {ec.id} {describe_exposure_change(prev_exposure, ec)}",
            )
        )
        prev_exposure = ec

    if not merged:
        print("No state or exposure changes recorded yet.")
        return
    merged.sort(key=lambda entry: (entry[0], entry[1]))
    print(f"History for {rid}:")
    for ts, _id, line in merged:
        print(f"{ts[:16]}  {line}")


def cmd_export(args: argparse.Namespace, db: Database) -> None:
    if Path(args.file).exists():
        sys.exit(f"Error: {args.file!r} already exists — refusing to overwrite.")
    bundle, rows, n_tables = save_bundle(db, args.file)
    print(
        f"Exported {rows} row(s) from {n_tables} table(s) "
        f"to {args.file} (sha256 {bundle['sha256']})."
    )


def cmd_restore(args: argparse.Namespace, db: Database) -> None:
    try:
        rows = restore_bundle(db, args.file)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"Error: cannot restore from {args.file!r}: {exc}")
    print(f"Restored {rows} row(s) from {args.file}.")


def cmd_db_check(_args: argparse.Namespace, db: Database) -> None:
    ok, detail, violations = db.integrity_check()
    if ok:
        print(f"Database OK ({db.path})")
        return
    print(f"Database problem: {detail}")
    for v in violations:
        print(
            f"  foreign-key violation: table={v.get('table')} "
            f"rowid={v.get('rowid')} parent={v.get('parent')}"
        )
    sys.exit("Database integrity check failed.")


def cmd_cooldown(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    if args.sub == "clear":
        n = db.clear_cooldowns(rid)
        print(f"Cleared {n} active cooldown(s) for {rid}.")
        return
    # default: list
    now = utc_now_iso()
    active = _active_cooldowns(db, rid)
    print(f"Active cooldowns for {rid}:")
    if not active:
        print("  (none)")
    for cd in active:
        print(
            f"  {cd.id} [{cd.decision}] {format_remaining(cd, now=now)} "
            f"(reason: {cd.reason or 'n/a'})"
        )
    overrides = db.list_overrides(rid)
    if overrides:
        print(f"Override history ({len(overrides)}):")
        for ov in overrides:
            print(f"  {ov.id} {ov.timestamp} | {ov.reason or '(no reason)'}")


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lre",
        description="LoveRiskEngine - personal relationship decision-support CLI",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize the local database")

    pa = sub.add_parser("relationship", help="Manage relationships")
    pa_sub = pa.add_subparsers(dest="sub", required=True)
    pa_add = pa_sub.add_parser("add", help="Add a relationship")
    pa_add.add_argument("alias")
    pa_add.add_argument(
        "--kind",
        choices=[k.name for k in Kind],
        default=Kind.LOVER.name,
        help="Relationship kind; selects the evaluation profile (default: LOVER)",
    )
    pa_set = pa_sub.add_parser("set", help="Change a relationship's kind")
    pa_set.add_argument("id")
    pa_set.add_argument(
        "--kind",
        required=True,
        choices=[k.name for k in Kind],
        help="Relationship kind; selects the evaluation profile",
    )

    po = sub.add_parser("observe", help="Record an observation")
    po.add_argument("relationship")
    po.add_argument("--category", default="general")
    po.add_argument("--observation", required=True)
    po.add_argument("--interpretation", default="")
    po.add_argument("--alternative", default="")
    po.add_argument("--source", default="self")
    po.add_argument("--confidence", type=float, default=5.0)
    po.add_argument("--rationalize", action="store_true")
    po.add_argument("--inconsistent", action="store_true")
    po.add_argument(
        "--signal-type",
        choices=[s.name for s in SignalType],
        default=None,
        help="Classify as CHEAP talk / COSTLY signal / UNSPECIFIED. "
        "If omitted, a keyword hint is printed when the text matches.",
    )
    po.add_argument(
        "--claim",
        action="append",
        default=[],
        help="Structured factual claim as attribute=value (repeatable). "
        "Used by the contradiction tracker.",
    )

    ps = sub.add_parser("status", help="Show relationship status")
    ps.add_argument("relationship")

    pr = sub.add_parser("review", help="Run a full review")
    pr.add_argument("relationship")

    pb = sub.add_parser("boundary", help="Manage boundaries")
    pb_sub = pb.add_subparsers(dest="sub", required=True)
    pb_add = pb_sub.add_parser("add", help="Add a boundary")
    pb_add.add_argument("--description", required=True)
    pb_add.add_argument("--severity", choices=["HARD", "SOFT"], default="HARD")
    pb_add.add_argument("--keywords", default="")
    pb_hit = pb_sub.add_parser("hit", help="Record a boundary hit (with evidence)")
    pb_hit.add_argument("boundary_id")
    pb_hit.add_argument("--relationship", required=True)
    pb_hit.add_argument("--evidence", required=True)
    pb_retire = pb_sub.add_parser(
        "retire", help="Retire a boundary (kept for audit, no longer enforced)"
    )
    pb_retire.add_argument("boundary_id")

    sub.add_parser("list", help="List relationships and boundaries")

    pst = sub.add_parser("state", help="Set relationship state")
    pst_sub = pst.add_subparsers(dest="sub", required=True)
    pst_set = pst_sub.add_parser("set")
    pst_set.add_argument("relationship")
    pst_set.add_argument("--attraction", type=float)
    pst_set.add_argument("--trust", type=float)
    pst_set.add_argument("--uncertainty", type=float)
    pst_set.add_argument("--emotional", choices=[e.name for e in EmotionalState])

    pe = sub.add_parser("exposure", help="Set exposure")
    pe_sub = pe.add_subparsers(dest="sub", required=True)
    pe_set = pe_sub.add_parser("set")
    pe_set.add_argument("relationship")
    pe_set.add_argument("--time", type=float)
    pe_set.add_argument("--emotional", type=float)
    pe_set.add_argument("--privacy", type=float)
    pe_set.add_argument("--financial", type=float)
    pe_set.add_argument("--life-decision", type=float, dest="life_decision")
    pe_set.add_argument(
        "--override",
        action="store_true",
        help="Override an active cooldown to raise exposure (logged for audit)",
    )
    pe_set.add_argument(
        "--reason",
        default="",
        help="Reason for overriding a cooldown (recorded in audit log)",
    )

    pi = sub.add_parser("inconsistency", help="Manage inconsistencies")
    pi_sub = pi.add_subparsers(dest="sub", required=True)
    pi_add = pi_sub.add_parser("add")
    pi_add.add_argument("relationship")
    pi_add.add_argument("--description", required=True)
    pi_res = pi_sub.add_parser("resolve")
    pi_res.add_argument("id")
    pi_res.add_argument(
        "--as",
        dest="resolution",
        choices=["sequential_change", "genuine_inconsistency", "dismissed"],
        default="sequential_change",
        help="How to resolve (default: sequential_change)",
    )
    pi_res.add_argument("--note", default="")
    pi_lst = pi_sub.add_parser("list")
    pi_lst.add_argument("relationship")
    pi_lst.add_argument(
        "--resolved", action="store_true", help="show resolved items instead of open"
    )

    pc = sub.add_parser(
        "contradictions",
        help="Detect conflicting structured claims across observations",
    )
    pc.add_argument("relationship")
    pc.add_argument(
        "--save",
        action="store_true",
        help="Persist new contradictions as inconsistencies (idempotent)",
    )

    pp = sub.add_parser(
        "promises", help="List promise claims and their ages for a relationship"
    )
    pp.add_argument("relationship")

    ph = sub.add_parser("history", help="State/exposure change log for a relationship")
    ph.add_argument("relationship")

    pe = sub.add_parser(
        "export", help="Export the database to a lossless backup bundle"
    )
    pe.add_argument("file")

    pr = sub.add_parser(
        "restore", help="Restore the database from a backup bundle (replaces all data)"
    )
    pr.add_argument("file")

    pdb = sub.add_parser("db", help="Database maintenance")
    pdb_sub = pdb.add_subparsers(dest="sub", required=True)
    pdb_sub.add_parser("check", help="Run integrity checks")

    pchat = sub.add_parser("chat", help="Local chat import & analysis (offline)")
    pchat_sub = pchat.add_subparsers(dest="sub", required=True)
    pimp = pchat_sub.add_parser("import", help="Import a local chat export")
    pimp.add_argument("relationship")
    pimp.add_argument(
        "--file", required=True, help="Path to NDJSON or delimited chat file"
    )
    pimp.add_argument(
        "--rules",
        default=None,
        help="Path to a JSON claim-rules file (see examples/claim_rules.json)",
    )
    pimp.add_argument("--category", default="chat")

    ptl = sub.add_parser(
        "timeline", help="Chronological event stream for a relationship"
    )
    ptl.add_argument("relationship")

    pcd = sub.add_parser("cooldown", help="Manage cooldowns / precommitment guardrails")
    pcd.add_argument("relationship")
    pcd.add_argument(
        "sub",
        nargs="?",
        default="list",
        choices=["list", "clear"],
        help="list (default) or clear active cooldowns",
    )

    return p


DISPATCH = {
    "init": cmd_init,
    "relationship": {"add": cmd_relationship_add, "set": cmd_relationship_set},
    "observe": cmd_observe,
    "status": cmd_status,
    "review": cmd_review,
    "boundary": {
        "add": cmd_boundary_add,
        "hit": cmd_boundary_hit,
        "retire": cmd_boundary_retire,
    },
    "list": cmd_list,
    "state": {"set": cmd_state_set},
    "exposure": {"set": cmd_exposure_set},
    "inconsistency": {
        "add": cmd_inconsistency_add,
        "resolve": cmd_inconsistency_resolve,
        "list": cmd_inconsistency_list,
    },
    "contradictions": cmd_contradictions,
    "promises": cmd_promises,
    "history": cmd_history,
    "export": cmd_export,
    "restore": cmd_restore,
    "db": {"check": cmd_db_check},
    "chat": {"import": cmd_chat_import},
    "timeline": cmd_timeline,
    "cooldown": cmd_cooldown,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db = get_db()
    try:
        handler = DISPATCH[args.command]
        if isinstance(handler, dict):
            handler = handler[args.sub]
        else:
            assert callable(handler)
        handler(args, db)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
