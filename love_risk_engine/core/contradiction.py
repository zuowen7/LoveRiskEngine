"""Contradiction tracker (roadmap feature).

Detects conflicting observations within a single relationship by comparing
*structured claims* (attribute=value) rather than free text.

Design choices (honest, privacy-first, no pseudoscience):
  - A contradiction is surfaced, never auto-judged. The tool only says
    "observation A claims X, observation B claims Y — these conflict, review
    needed." The user confirms or dismisses.
  - Detection is deterministic: same normalized attribute asserted with two
    different values => conflict. No model, no confidence score.
  - Sequential-but-true changes (e.g. job switched from barista to engineer)
    are exactly the kind of thing the user must arbitrate, so surfacing them
    is correct behavior, not a false positive to be hidden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

from .observation import Observation


@dataclass
class ContradictionCandidate:
    attribute: str
    value_a: str
    value_b: str
    obs_a_id: str
    obs_b_id: str
    explanation: str


def normalize_attribute(attr: str) -> str:
    return re.sub(r"[\s_-]+", "_", attr.strip().lower())


def detect_contradictions(
    observations: List[Observation],
) -> List[ContradictionCandidate]:
    """Return every conflicting claim pair across the given observations."""
    # attribute -> value -> [observation ids]
    by_attr: Dict[str, Dict[str, List[str]]] = {}
    for o in observations:
        for c in o.claims:
            attr = normalize_attribute(c.attribute)
            val = c.value.strip()
            if not attr or not val:
                continue
            by_attr.setdefault(attr, {}).setdefault(val, []).append(o.id)

    candidates: List[ContradictionCandidate] = []
    for attr, val_map in by_attr.items():
        vals = sorted(val_map.keys())
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                va, vb = vals[i], vals[j]
                for oa in val_map[va]:
                    for ob in val_map[vb]:
                        if oa == ob:
                            continue
                        candidates.append(
                            ContradictionCandidate(
                                attribute=attr,
                                value_a=va,
                                value_b=vb,
                                obs_a_id=oa,
                                obs_b_id=ob,
                                explanation=(
                                    f"Obs {oa} claims {attr}={va!r}; "
                                    f"obs {ob} claims {attr}={vb!r}. "
                                    f"Conflicting — review needed."
                                ),
                            )
                        )
    return candidates


def contradiction_key(attribute: str, obs_a: str, obs_b: str) -> str:
    """Order-independent dedup key for a (attribute, obs-pair) conflict."""
    pair = tuple(sorted((obs_a, obs_b)))
    return f"{normalize_attribute(attribute)}|{pair[0]}|{pair[1]}"
