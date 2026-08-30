import json

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

NDJSON = """{"timestamp": "2026-01-01T10:00:00", "speaker": "Sam", "text": "he is single"}
{"timestamp": "2026-01-02T11:00:00", "speaker": "Sam", "text": "he is married"}
"""


def test_parse_delimited():
    msgs = parse_delimited(__file__)
    # __file__ is python, not delimited; use inline temp via parse_file on a temp file
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(DELMITED)
        path = fh.name
    try:
        msgs = parse_delimited(path)
        assert len(msgs) == 3
        assert msgs[0].speaker == "Sam"
        assert "single" in msgs[0].text
    finally:
        os.unlink(path)


def test_parse_ndjson():
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        fh.write(NDJSON)
        path = fh.name
    try:
        msgs = parse_ndjson(path)
        assert len(msgs) == 2
        assert msgs[1].text == "he is married"
    finally:
        os.unlink(path)


def test_parse_file_autodetect():
    import tempfile, os
    for content, expect in [(DELMITED, 3), (NDJSON, 2)]:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write(content)
            path = fh.name
        try:
            msgs = parse_file(path)
            assert len(msgs) == expect
        finally:
            os.unlink(path)


def test_extract_claims():
    rules = [
        ClaimRule("relationship_status", r"\b(?:he|she|they) (?:is|was) (single|married)\b"),
        ClaimRule("job", r"\bworks (?:as|at) (?:a |an )?([A-Za-z]+)\b"),
    ]
    claims = extract_claims("he said he is single and works as a barista", rules)
    attrs = {c.attribute: c.value for c in claims}
    assert attrs.get("relationship_status") == "single"
    assert attrs.get("job") == "barista"


def test_to_observations_attaches_claims():
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(DELMITED)
        path = fh.name
    try:
        msgs = parse_file(path)
        rules = [ClaimRule("relationship_status", r"\b(?:he|she|they) (?:is|was) (single|married)\b")]
        obs = to_observations(msgs, rules, "R001")
        assert len(obs) == 3
        assert all(o.relationship_id == "R001" for o in obs)
        # first two messages assert conflicting relationship_status
        statuses = [c.value for o in obs for c in o.claims if c.attribute == "relationship_status"]
        assert "single" in statuses and "married" in statuses
    finally:
        os.unlink(path)


def test_load_claim_rules_skips_bad_entries():
    import tempfile, os
    payload = [
        {"attribute": "job", "pattern": r"works at ([A-Za-z]+)"},
        {"attribute": "", "pattern": r"x"},  # missing attribute -> skipped
        {"pattern": r"y"},                   # missing attribute -> skipped
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh)
        path = fh.name
    try:
        rules = load_claim_rules(path)
        assert len(rules) == 1
        assert rules[0].attribute == "job"
    finally:
        os.unlink(path)
