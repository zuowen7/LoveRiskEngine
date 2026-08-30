"""Local chat import & analysis (roadmap feature, v0.2).

Turns a *local* chat export into structured Observations, optionally extracting
structured Claims via user-supplied regex rules.

Design constraints (privacy-first, honest, no pseudoscience):
  - Pure stdlib, runs fully offline. No network, no PII fields, no scraping.
  - Never deletes or overwrites existing observations.
  - Claim extraction is deterministic regex over user-provided rules. It does
    NOT judge truth; it only pulls out (attribute, value) pairs the user can
    later compare with the contradiction tracker.
  - The import does not auto-flag anything as a lie; conflicts are surfaced by
    the contradiction tracker for the user to arbitrate.

Accepted file formats:
  * NDJSON:        one JSON object per line, fields {timestamp, speaker, text}
  * Delimited:     "TIMESTAMP | SPEAKER | TEXT" per line

Claim rules file (JSON list):
  [{"attribute": "relationship_status",
    "pattern": "\\b(?:he|she|they) (?:is|was) (single|married|in a relationship)\\b"}]
The `pattern` must contain exactly one capturing group, which yields the value.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List

from .observation import Claim, Observation

_DELIM_RE = re.compile(
    r"^(?P<ts>[^|]+)\s*\|\s*(?P<sp>[^|]+)\s*\|\s*(?P<tx>.*)$"
)


@dataclass
class ChatMessage:
    timestamp: str
    speaker: str
    text: str


@dataclass
class ClaimRule:
    attribute: str
    pattern: str

    def compiled(self) -> "re.Pattern[str]":
        return re.compile(self.pattern, re.IGNORECASE)


def parse_ndjson(path: str) -> List[ChatMessage]:
    messages: List[ChatMessage] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            messages.append(
                ChatMessage(
                    timestamp=str(obj.get("timestamp", "")),
                    speaker=str(obj.get("speaker", "")),
                    text=str(obj.get("text", "")),
                )
            )
    return messages


def parse_delimited(path: str) -> List[ChatMessage]:
    messages: List[ChatMessage] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = _DELIM_RE.match(line)
            if not m:
                continue  # skip malformed lines
            messages.append(
                ChatMessage(
                    timestamp=m.group("ts").strip(),
                    speaker=m.group("sp").strip(),
                    text=m.group("tx").strip(),
                )
            )
    return messages


def parse_file(path: str) -> List[ChatMessage]:
    """Auto-detect NDJSON vs delimited format from the first non-empty line."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if s.startswith("{"):
                return parse_ndjson(path)
            return parse_delimited(path)
    return []


def load_claim_rules(path: str) -> List[ClaimRule]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    rules: List[ClaimRule] = []
    for item in raw:
        attr = item.get("attribute")
        pat = item.get("pattern")
        if not attr or not pat:
            continue
        rules.append(ClaimRule(attribute=attr, pattern=pat))
    return rules


def extract_claims(text: str, rules: List[ClaimRule]) -> List[Claim]:
    claims: List[Claim] = []
    for rule in rules:
        m = rule.compiled().search(text)
        if m and m.lastindex and m.lastindex >= 1:
            value = m.group(1).strip()
            if value:
                claims.append(Claim(attribute=rule.attribute.strip(), value=value))
    return claims


def to_observations(
    messages: List[ChatMessage],
    rules: List[ClaimRule],
    relationship_id: str,
    category: str = "chat",
) -> List[Observation]:
    observations: List[Observation] = []
    for msg in messages:
        claims = extract_claims(msg.text, rules)
        observations.append(
            Observation(
                id="",  # assigned by the database layer
                relationship_id=relationship_id,
                timestamp=msg.timestamp,
                category=category,
                observation=msg.text,
                interpretation="",
                alternative_explanation="",
                source=f"chat:{msg.speaker}" if msg.speaker else "chat",
                confidence=5.0,
                claims=claims,
            )
        )
    return observations
