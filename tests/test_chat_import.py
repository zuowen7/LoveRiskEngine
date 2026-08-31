import json

import pytest
from love_risk_engine.core.chat_import import (
    ClaimRule,
    extract_claims,
    load_claim_rules,
    parse_delimited,
    parse_file,
    parse_ndjson,
    to_observations,
)

DELMITED = """2026-01-01T10:00:00 | Sam | He said he is single
2026-01-02T11:00:00 | Sam | He said he is married
2026-01-03T12:00:00 | Sam | He works as a barista
"""

# One NDJSON record per line: the parser is line-oriented, so these lines are
# intentionally kept as-is rather than wrapped.
NDJSON = (
    '{"timestamp": "2026-01-01T10:00:00", "speaker": "Sam", "text": "he is single"}\n'
    '{"timestamp": "2026-01-02T11:00:00", "speaker": "Sam", "text": "he is married"}\n'
)


@pytest.fixture
def write_tmp(tmp_path):
    """Write content to a temp file and return its path.

    Replaces the `NamedTemporaryFile(delete=False)` + try/finally pattern:
    pytest owns the directory, so cleanup happens even when a test fails.
    """

    def _write(content: str, suffix: str = ".txt") -> str:
        path = tmp_path / f"input{suffix}"
        path.write_text(content, encoding="utf-8")
        return str(path)

    return _write


def test_parse_delimited(write_tmp):
    msgs = parse_delimited(write_tmp(DELMITED))
    assert len(msgs) == 3
    assert msgs[0].speaker == "Sam"
    assert "single" in msgs[0].text


def test_parse_ndjson(write_tmp):
    msgs = parse_ndjson(write_tmp(NDJSON, suffix=".json"))
    assert len(msgs) == 2
    assert msgs[1].text == "he is married"


def test_parse_file_autodetect(write_tmp):
    assert len(parse_file(write_tmp(DELMITED))) == 3
    assert len(parse_file(write_tmp(NDJSON, suffix=".json"))) == 2


def test_extract_claims():
    rules = [
        ClaimRule(
            "relationship_status", r"\b(?:he|she|they) (?:is|was) (single|married)\b"
        ),
        ClaimRule("job", r"\bworks (?:as|at) (?:a |an )?([A-Za-z]+)\b"),
    ]
    claims = extract_claims("he said he is single and works as a barista", rules)
    attrs = {c.attribute: c.value for c in claims}
    assert attrs.get("relationship_status") == "single"
    assert attrs.get("job") == "barista"


def test_to_observations_attaches_claims(write_tmp):
    msgs = parse_file(write_tmp(DELMITED))
    rules = [
        ClaimRule(
            "relationship_status", r"\b(?:he|she|they) (?:is|was) (single|married)\b"
        )
    ]
    obs = to_observations(msgs, rules, "R001")
    assert len(obs) == 3
    assert all(o.relationship_id == "R001" for o in obs)
    # first two messages assert conflicting relationship_status
    statuses = [
        c.value for o in obs for c in o.claims if c.attribute == "relationship_status"
    ]
    assert "single" in statuses and "married" in statuses


def test_load_claim_rules_skips_bad_entries(write_tmp, tmp_path):
    payload = [
        {"attribute": "job", "pattern": r"works at ([A-Za-z]+)"},
        {"attribute": "", "pattern": r"x"},  # missing attribute -> skipped
        {"pattern": r"y"},  # missing attribute -> skipped
    ]
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    rules = load_claim_rules(str(path))
    assert len(rules) == 1
    assert rules[0].attribute == "job"
