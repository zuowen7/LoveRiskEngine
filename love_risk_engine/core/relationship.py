"""Relationship domain model.

A relationship is the entity a user is evaluating — `get_relationship` /
`list_relationships` return these, not raw rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    """What kind of relationship is being evaluated.

    `kind` selects a `RelationshipProfile` (core/profiles.py): display context,
    warning phrasing, and — from later slices — which hooks run and how
    sensitively. The kind is a label, never a numeric score.
    """

    LOVER = "LOVER"
    FRIEND = "FRIEND"
    PARENT = "PARENT"
    BOSS = "BOSS"
    MENTOR = "MENTOR"
    COLLEAGUE = "COLLEAGUE"
    STRANGER = "STRANGER"


@dataclass
class Relationship:
    id: str
    alias: str
    status: str
    created_at: str
    kind: str = Kind.LOVER.value
