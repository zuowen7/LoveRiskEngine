"""Relationship domain model.

A relationship is the entity a user is evaluating — `get_relationship` /
`list_relationships` return these, not raw rows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Relationship:
    id: str
    alias: str
    status: str
    created_at: str
