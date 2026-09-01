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
  lre counterfactual <relationship> [--review ID] # audit a past review
  lre verify add <relationship> --item "..."     # mutual verification checklist
  lre verify list <relationship>                #   (check/fail change an item's state)
  lre completion <shell>                        # print a shell completion script
  lre chat import <relationship> --file chat.txt [--rules claim_rules.json]
  lre timeline <relationship>                    # chronological event stream
  lre cooldown <relationship> [list|clear]       # precommitment guardrails
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

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
from .core.i18n import localize_finding, t
from .core.inconsistency import Inconsistency
from .core.observation import Claim
from .core.profiles import RelationshipProfile, get_profile
from .core.promises import PromiseReport, collect_promises
from .core.relationship import Kind, Relationship
from .core.signals import SignalType, suggest_signal_type
from .core.state import EmotionalState, RelationshipState
from .core.timeline import build_timeline, format_timeline
from .core.timeutil import utc_now_iso
from .services.counterfactual import run_counterfactual
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
        sys.exit(t("error_relationship_not_found", token=repr(token)))
    return rel


def _profile_context(profile: RelationshipProfile) -> str | None:
    """One-line ordinal context for non-default kinds; None for LOVER.

    Shown by both `status` and `review`: the band values are context for the
    user's judgement, never input to a formula.
    """
    if profile.kind is Kind.LOVER:
        return None
    parts = [
        t("context_power", v=profile.power_asymmetry.value),
        t("context_exit", v=profile.exit_cost.value),
    ]
    if profile.voice:
        parts.append(t(profile.voice))
    return " | ".join(parts)


# --- shell completion (architecture phase 3, E3) ---
# The glue scripts are static; the candidates are computed by the *installed*
# parser at runtime (`lre _complete`), so command drift is impossible.

_BASH_COMPLETION = """\
# lre bash completion — install: eval "$(lre completion bash)"
_lre_completion() {
    local IFS=$'\\n'
    COMPREPLY=($(lre _complete "${COMP_WORDS[@]:1}" 2>/dev/null))
}
complete -F _lre_completion lre
"""

_ZSH_COMPLETION = """\
#compdef lre
# lre zsh completion — install: lre completion zsh > "${fpath[1]}/_lre"
_lre() {
  local -a candidates
  candidates=("${(@f)$(lre _complete ${words[2,-1]} 2>/dev/null)}")
  _describe 'lre' candidates
}
_lre "$@"
"""

_FISH_COMPLETION = """\
# lre fish completion — install:
#   lre completion fish > ~/.config/fish/completions/lre.fish
function __lre_complete
    lre _complete (commandline -opc)[2..-1] (commandline -ct) 2>/dev/null
end
complete -c lre -f -a '(__lre_complete)'
"""

_POWERSHELL_COMPLETION = """\
# lre PowerShell completion — install:
#   lre completion powershell | Out-String | Invoke-Expression
Register-ArgumentCompleter -Native -CommandName lre -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $elems = $commandAst.CommandElements | Select-Object -Skip 1
    $tokens = @($elems | ForEach-Object { $_.Extent.Text })
    $tokens += $wordToComplete
    lre _complete $tokens 2>$null | ForEach-Object {
        [CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}
"""

COMPLETION_SCRIPTS = {
    "bash": _BASH_COMPLETION,
    "zsh": _ZSH_COMPLETION,
    "fish": _FISH_COMPLETION,
    "powershell": _POWERSHELL_COMPLETION,
}


def _subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _completion_parser_for(
    parser: argparse.ArgumentParser, tokens: list[str]
) -> argparse.ArgumentParser:
    """Walk the argparse tree along `tokens`; options consume their value."""
    current = parser
    i = 0
    while i < len(tokens):
        token = tokens[i]
        subs = _subparsers_action(current)
        if subs is not None and token in subs.choices:
            current = subs.choices[token]
            i += 1
            continue
        for action in current._actions:
            if token in action.option_strings and action.nargs != 0:
                i += 1  # the option consumes the following token
                break
        i += 1
    return current


def completion_candidates(words: list[str]) -> list[str]:
    """Candidates for the given command line; the last word is the partial.

    Best-effort by contract: completion is a convenience, never authoritative.
    No DB lookups in v1 (relationship names/ids are not completed).
    """
    prefix = words[-1] if words else ""
    tokens = words[:-1]
    parser = build_parser()

    # A trailing option with declared choices completes ITS values.
    if tokens:
        last = tokens[-1]
        trailing_parser = _completion_parser_for(parser, tokens[:-1])
        for action in trailing_parser._actions:
            if last in action.option_strings:
                choices = getattr(action, "choices", None)
                if choices:
                    return sorted(
                        str(choice)
                        for choice in choices
                        if str(choice).startswith(prefix)
                    )
                break

    current = _completion_parser_for(parser, tokens)
    candidates: set[str] = set()
    for action in current._actions:
        if isinstance(action, argparse._SubParsersAction):
            candidates.update(
                name for name in action.choices if not name.startswith("_")
            )
        elif action.option_strings:
            candidates.update(action.option_strings)
        else:
            choices = getattr(action, "choices", None)
            if choices:
                candidates.update(str(choice) for choice in choices)
    return sorted(c for c in candidates if c.startswith(prefix))


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
    print(t("init_done", path=db.path))


def cmd_relationship_add(args: argparse.Namespace, db: Database) -> None:
    rid = db.add_relationship(args.alias, kind=args.kind)
    print(t("relationship_created", id=rid, alias=args.alias, kind=args.kind))
    seeds = get_profile(args.kind).boundary_seeds
    if seeds:
        print(t("seed_boundaries_header"))
        for seed in seeds:
            print(f"  - {seed}")


def cmd_relationship_set(args: argparse.Namespace, db: Database) -> None:
    if not db.set_relationship_kind(args.id, args.kind):
        sys.exit(t("error_relationship_not_found", token=repr(args.id)))
    print(t("kind_set", kind=args.kind, id=args.id))


def cmd_observe(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    claims: list[Claim] = []
    for item in args.claim:
        if "=" not in item:
            sys.exit(t("error_claim_equals", item=repr(item)))
        k, v = item.split("=", 1)
        if not k.strip():
            sys.exit(t("error_claim_empty", item=repr(item)))
        claims.append(Claim(attribute=k.strip(), value=v.strip()))

    if args.signal_type:
        signal_type = SignalType[args.signal_type]
    else:
        hint = suggest_signal_type(args.observation)
        signal_type = SignalType.UNSPECIFIED
        if hint is not None:
            print(t("signal_hint", type=hint.value))

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
    print(t("observation_recorded", id=oid, rel=rel.id, extra=extra))


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
    items = db.list_verification_items(rid)
    verified = sum(1 for i in items if i.status == "verified")
    verification = (verified, len(items)) if items else None
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
            verification=verification,
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
    verification: tuple[int, int] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(t("relationship_header", rid=rid))
    if kind is not None and profile is not None:
        lines.append(t("kind_line", kind=kind))
        context = _profile_context(profile)
        if context:
            lines.append(t("context_line", context=context))
    lines.append("")
    lines.append(t("attraction_metric", v=f"{state.attraction:.1f}"))
    lines.append(t("trust_metric", v=f"{state.trust:.1f}"))
    lines.append(t("uncertainty_metric", v=f"{state.uncertainty:.1f}"))
    lines.append(t("emotional_metric", v=state.emotional_state.value))
    lines.append("")
    lines.append(t("exposure_header"))
    lines.append(t("exposure_time", v=f"{exposure.time:.1f}"))
    lines.append(t("exposure_emotional", v=f"{exposure.emotional:.1f}"))
    lines.append(t("exposure_privacy", v=f"{exposure.privacy:.1f}"))
    lines.append(t("exposure_financial", v=f"{exposure.financial:.1f}"))
    lines.append(t("exposure_life", v=f"{exposure.life_decision:.1f}"))
    lines.append("")
    lines.append(t("evidence_header"))
    lines.append(t("evidence_observations", n=evidence_support.observation_count))
    lines.append(t("evidence_sources", n=evidence_support.distinct_sources))
    lines.append(t("evidence_alt", n=evidence_support.with_alternative))
    lines.append(t("evidence_claims", n=evidence_support.with_claims))
    lines.append(t("evidence_costly", n=evidence_support.costly_count))
    lines.append(t("evidence_cheap", n=evidence_support.cheap_count))
    lines.append(t("evidence_units", v=f"{evidence_support.support_units:.1f}"))
    lines.append("")
    lines.append(t("warnings_header"))
    if findings:
        for f in findings:
            lines.append(f"- {localize_finding(f)}")
    else:
        lines.append(t("none_dash"))
    lines.append("")
    lines.append(t("unresolved_count", n=inconsistency_count))
    if acknowledged:
        # breakdown by resolution type — keeps acknowledged items visible
        buckets: dict = {}
        for it in acknowledged:
            res = it.resolution or "resolved"
            buckets[res] = buckets.get(res, 0) + 1
        parts = ", ".join(f"{v} {k}" for k, v in sorted(buckets.items()))
        lines.append(t("acknowledged_line", n=len(acknowledged), parts=parts))
    if verification is not None:
        verified, total = verification
        lines.append(t("verified_facts", v=verified, t=total))
    if contradictions:
        lines.append("")
        lines.append(t("conflicts_header"))
        for c in contradictions:
            lines.append(
                f"- [{c.attribute}] {c.value_a!r} vs {c.value_b!r} "
                f"({c.obs_a_id}, {c.obs_b_id})"
            )
        if more_conflicts:
            lines.append(t("conflicts_more"))
    if promises is not None and (promises.within or promises.expired):
        lines.append("")
        lines.append(t("promises_header", w=promises.window_days))
        for p in promises.within:
            lines.append(
                f"  {p.attribute}={p.value!r} ({p.observation_id}, "
                f"{p.timestamp[:10]}, {p.age_days}d)"
            )
        if promises.expired:
            lines.append(t("older_promises", n=len(promises.expired)))
    lines.append("")
    lines.append(t("recommendation_label"))
    lines.append(decision.value)
    return "\n".join(lines)


def cmd_review(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    profile = get_profile(rel.kind)
    ctx = build_context(db, rel.id)
    findings, _decision = analyze(ctx)
    review = run_review(db, rel.id, ctx=ctx)
    print(t("review_header", id=review.id, rid=rel.id))
    context = _profile_context(profile)
    if context:
        print(t("context_label", context=context))
    print(f"{t('recommendation_label')} {review.recommendation}")
    print(t("review_unresolved", n=review.unresolved_inconsistencies))
    print(t("review_hooks_header"))
    if review.triggered_hooks:
        for hook in review.triggered_hooks:
            print(f"  - {hook}")
    else:
        print(t("review_none"))
    print(t("review_warnings_header"))
    for f in findings:
        print(f"- {localize_finding(f)}")
    if review.cooldown_id:
        print(t("review_cooldown", id=review.cooldown_id, rel=args.relationship))


def cmd_boundary_add(args: argparse.Namespace, db: Database) -> None:
    bid = db.add_boundary(args.description, args.severity, args.keywords)
    print(t("boundary_added", id=bid, desc=args.description, sev=args.severity))


def cmd_boundary_hit(args: argparse.Namespace, db: Database) -> None:
    if db.get_boundary(args.boundary_id) is None:
        sys.exit(t("error_boundary_not_found", id=repr(args.boundary_id)))
    rel = resolve_relationship(db, args.relationship)
    hid = db.add_boundary_hit(args.boundary_id, rel.id, args.evidence)
    print(t("boundary_hit_recorded", id=hid, bid=args.boundary_id, rid=rel.id))


def cmd_boundary_retire(args: argparse.Namespace, db: Database) -> None:
    if not db.deactivate_boundary(args.boundary_id):
        sys.exit(t("error_boundary_not_found", id=repr(args.boundary_id)))
    print(t("boundary_retired", id=args.boundary_id))


def cmd_list(_args: argparse.Namespace, db: Database) -> None:
    rels = db.list_relationships()
    print(t("list_relationships"))
    if not rels:
        print(t("list_none"))
    for r in rels:
        print(f"  {r.id}  {r.alias}  [{r.status}]  {r.kind}")
    print("")
    print(t("list_boundaries"))
    bounds = db.list_boundaries(active_only=False)
    if not bounds:
        print(t("list_none"))
    for b in bounds:
        flag = t("list_active") if b.active else t("list_inactive")
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
    print(t("state_updated", rid=rid))


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
            print(t("cooldown_blocked"))
            for cd in active:
                print(
                    t(
                        "cooldown_line",
                        id=cd.id,
                        decision=cd.decision,
                        remaining=format_remaining(cd),
                        reason=cd.reason or "n/a",
                    )
                )
            print(t("cooldown_override_hint", rel=args.relationship))
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
            t(
                "override_logged",
                old=f"{old_total:.1f}",
                new=f"{new_total:.1f}",
            )
        )

    db.upsert_exposure(existing)
    print(
        t(
            "exposure_updated",
            rid=rid,
            old=f"{old_total:.1f}",
            new=f"{new_total:.1f}",
        )
    )


def cmd_inconsistency_add(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    iid = db.add_inconsistency(rel.id, args.description)
    print(t("inconsistency_recorded", id=iid, rid=rel.id))


def cmd_inconsistency_resolve(args: argparse.Namespace, db: Database) -> None:
    ok = db.resolve_inconsistency(args.id, args.resolution, args.note)
    if not ok:
        sys.exit(t("error_inconsistency_not_found", id=repr(args.id)))
    print(t("inconsistency_resolve_done", id=args.id, res=args.resolution))


def cmd_inconsistency_list(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    items = db.list_inconsistencies(rid, resolved=args.resolved)
    label = t("inconsistency_resolved") if args.resolved else t("inconsistency_open")
    print(t("inconsistency_list_header", label=label, rid=rid))
    if not items:
        print(t("inconsistency_none"))
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
        print(t("no_contradictions", rid=rid))
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
        print(t("contradictions_saved", n=saved))


def cmd_promises(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    profile = get_profile(rel.kind)
    if profile.promise_window_days is None:
        print(t("promises_no_window", kind=rel.kind))
        return
    observations = db.get_observations(rel.id)
    report = collect_promises(observations, profile.promise_window_days)
    if not report.within and not report.expired:
        print(t("promises_none"))
        return
    print(t("promises_cmd_header", rid=rel.id, w=report.window_days))
    if report.within:
        print(t("promises_within"))
        for p in report.within:
            print(
                f"  - {p.attribute}={p.value!r} ({p.observation_id}, "
                f"{p.timestamp[:10]}, {p.age_days}d)"
            )
    if report.expired:
        print(t("promises_expired", n=len(report.expired)))
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
        sys.exit(t("chat_file_missing", file=repr(args.file)))
    except ValueError as exc:
        sys.exit(t("chat_parse_error", file=repr(args.file), err=exc))
    if not messages:
        print(t("chat_no_messages", file=repr(args.file)))
        return
    rules = load_claim_rules(args.rules) if args.rules else []
    observations = to_observations(messages, rules, rid, category=args.category)
    n = db.import_observations(rid, observations)
    claim_total = sum(len(o.claims) for o in observations)
    print(t("chat_imported", n=n, file=repr(args.file), rid=rid))
    print(t("chat_claims", n=claim_total, m=len(rules)))
    # post-analysis: surface contradictions for the user to arbitrate
    all_obs = db.get_observations(rid)
    cands = detect_contradictions(all_obs)
    if cands:
        print(t("chat_conflicts", n=len(cands), rel=args.relationship))
    else:
        print(t("chat_clean"))


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
    print(t("timeline_header", rid=rid, n=len(events)))
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
        print(t("history_empty"))
        return
    merged.sort(key=lambda entry: (entry[0], entry[1]))
    print(t("history_header", rid=rid))
    for ts, _id, line in merged:
        print(f"{ts[:16]}  {line}")


def cmd_export(args: argparse.Namespace, db: Database) -> None:
    if Path(args.file).exists():
        sys.exit(t("export_exists", file=repr(args.file)))
    bundle, rows, n_tables = save_bundle(db, args.file)
    print(
        t(
            "export_done",
            n=rows,
            m=n_tables,
            file=args.file,
            sha=bundle["sha256"],
        )
    )


def cmd_restore(args: argparse.Namespace, db: Database) -> None:
    try:
        rows = restore_bundle(db, args.file)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(t("restore_error", file=repr(args.file), err=exc))
    print(t("restore_done", n=rows, file=args.file))


def cmd_db_check(_args: argparse.Namespace, db: Database) -> None:
    ok, detail, violations = db.integrity_check()
    if ok:
        print(t("db_ok", path=db.path))
        return
    print(t("db_problem", detail=detail))
    for v in violations:
        print(
            t(
                "db_fk_violation",
                table=v.get("table"),
                rowid=v.get("rowid"),
                parent=v.get("parent"),
            )
        )
    sys.exit(t("db_check_failed"))


def cmd_verify_add(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    vid = db.add_verification_item(rel.id, args.item)
    print(t("verify_added", id=vid, rid=rel.id, item=args.item))


def cmd_verify_list(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    items = db.list_verification_items(rel.id)
    if not items:
        print(t("verify_none", rid=rel.id))
        return
    print(t("verify_header", rid=rel.id))
    for it in items:
        line = f"  {it.id} [{it.status}] {it.item}"
        if it.note:
            line += f" | {it.note}"
        print(line)


def cmd_verify_check(args: argparse.Namespace, db: Database) -> None:
    if not db.set_verification_status(args.id, "verified"):
        sys.exit(t("error_verification_not_found", id=repr(args.id)))
    print(t("verify_checked", id=args.id))


def cmd_verify_fail(args: argparse.Namespace, db: Database) -> None:
    if not db.set_verification_status(args.id, "failed", note=args.note):
        sys.exit(t("error_verification_not_found", id=repr(args.id)))
    print(t("verify_failed", id=args.id))


def cmd_counterfactual(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    reviews = db.list_reviews(rel.id)
    if not args.review:
        if not reviews:
            print(t("counterfactual_none", rid=rel.id))
            return
        print(t("counterfactual_list_header", rid=rel.id))
        for r in reviews:
            print(f"  {r.id}  {r.timestamp[:16]}  -> {r.recommendation}")
        print(t("counterfactual_hint"))
        return
    try:
        result = run_counterfactual(db, rel.id, args.review)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
    ev = result.evidence
    print(
        t(
            "counterfactual_header",
            id=result.review_id,
            ts=result.as_of[:16],
            rec=result.original_recommendation,
        )
    )
    print(
        t(
            "counterfactual_evidence",
            obs=ev.observation_count,
            hits=ev.boundary_hit_count,
            inc=ev.unresolved_inconsistency_count,
        )
    )
    print(
        t(
            "counterfactual_state",
            e=f"{ev.exposure_total:.1f}",
            a=f"{ev.attraction:.1f}",
            t=f"{ev.trust:.1f}",
            u=f"{ev.uncertainty:.1f}",
            em=ev.emotional_state,
        )
    )
    print(t("counterfactual_recomputed", rec=result.recomputed_recommendation))
    if result.fired_rule_ids:
        print(t("counterfactual_findings", list=", ".join(result.fired_rule_ids)))
    print(
        t(
            "counterfactual_verdict",
            verdict="MATCHED" if result.matched else "DIFFERENT",
        )
    )
    print(t("counterfactual_note"))


def cmd_completion(args: argparse.Namespace, _db: Database) -> None:
    print(COMPLETION_SCRIPTS[args.shell], end="")


def cmd_internal_complete(args: argparse.Namespace, _db: Database) -> None:
    for candidate in completion_candidates(args.tokens):
        print(candidate)


def cmd_cooldown(args: argparse.Namespace, db: Database) -> None:
    rel = resolve_relationship(db, args.relationship)
    rid = rel.id
    if args.sub == "clear":
        n = db.clear_cooldowns(rid)
        print(t("cooldowns_cleared", n=n, rid=rid))
        return
    # default: list
    now = utc_now_iso()
    active = _active_cooldowns(db, rid)
    print(t("cooldowns_header", rid=rid))
    if not active:
        print(t("list_none"))
    for cd in active:
        print(
            t(
                "cooldown_line",
                id=cd.id,
                decision=cd.decision,
                remaining=format_remaining(cd, now=now),
                reason=cd.reason or "n/a",
            )
        )
    overrides = db.list_overrides(rid)
    if overrides:
        print(t("overrides_header", n=len(overrides)))
        for ov in overrides:
            print(f"  {ov.id} {ov.timestamp} | {ov.reason or '(no reason)'}")


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
class _LocalizedHelpFormatter(argparse.HelpFormatter):
    """argparse hardcodes the 'usage:' label — localize it (i18n phase)."""

    def add_usage(
        self,
        usage: str | None,
        actions: Any,
        groups: Any,
        prefix: str | None = None,
    ) -> None:
        if prefix is None:
            prefix = t("help_usage") + ": "
        super().add_usage(usage, actions, groups, prefix)


class LocalizedArgumentParser(argparse.ArgumentParser):
    """argparse with a localizable 'usage:' label (i18n phase)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", _LocalizedHelpFormatter)
        super().__init__(*args, **kwargs)


def build_parser() -> argparse.ArgumentParser:
    p = LocalizedArgumentParser(
        prog="lre",
        description=t("help_description"),
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

    pcf = sub.add_parser(
        "counterfactual",
        help="Re-run a past review against the evidence available at that time",
    )
    pcf.add_argument("relationship")
    pcf.add_argument(
        "--review",
        default=None,
        help="Review id to re-run (default: list reviews)",
    )

    pv = sub.add_parser("verify", help="Mutual verification checklist")
    pv_sub = pv.add_subparsers(dest="sub", required=True)
    pv_add = pv_sub.add_parser("add", help="Add a verifiable fact to confirm")
    pv_add.add_argument("relationship")
    pv_add.add_argument("--item", required=True, help="The verifiable fact")
    pv_list = pv_sub.add_parser("list", help="List verification items")
    pv_list.add_argument("relationship")
    pv_check = pv_sub.add_parser("check", help="Mark an item as verified")
    pv_check.add_argument("id")
    pv_fail = pv_sub.add_parser("fail", help="Mark an item as failed")
    pv_fail.add_argument("id")
    pv_fail.add_argument("--note", default="")

    pcomp = sub.add_parser("completion", help="Print a shell completion script")
    pcomp.add_argument("shell", choices=sorted(COMPLETION_SCRIPTS))
    pc_internal = sub.add_parser("_complete", help=argparse.SUPPRESS)
    pc_internal.add_argument("tokens", nargs=argparse.REMAINDER)

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
    "counterfactual": cmd_counterfactual,
    "verify": {
        "add": cmd_verify_add,
        "list": cmd_verify_list,
        "check": cmd_verify_check,
        "fail": cmd_verify_fail,
    },
    "completion": cmd_completion,
    "_complete": cmd_internal_complete,
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
