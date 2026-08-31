"""Hard / soft boundaries and recorded boundary hits.

Design principle #5 (Hard boundaries):
  A boundary is a line the USER pre-commits to. Hitting one can suggest EXIT,
  but only when there is recorded evidence (a BoundaryHit). The engine never
  auto-convicts the other person from a single vague observation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Boundary:
    id: str
    description: str
    severity: str  # "HARD" | "SOFT"
    active: bool = True
    trigger_keywords: str = ""


@dataclass
class BoundaryHit:
    id: str
    boundary_id: str
    relationship_id: str
    evidence: str
    timestamp: str
