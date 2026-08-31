from love_risk_engine.core.signals import SignalType, suggest_signal_type


def test_signal_type_weights_ordering():
    assert SignalType.COSTLY.evidence_weight > SignalType.UNSPECIFIED.evidence_weight
    assert SignalType.UNSPECIFIED.evidence_weight > SignalType.CHEAP.evidence_weight


def test_suggest_costly():
    assert suggest_signal_type("He introduced me to his parents") is SignalType.COSTLY
    assert (
        suggest_signal_type("she showed up on time and paid for dinner")
        is SignalType.COSTLY
    )


def test_suggest_cheap():
    assert suggest_signal_type("he said trust me, I promise") is SignalType.CHEAP
    assert suggest_signal_type("I would never lie to you") is SignalType.CHEAP


def test_suggest_ambiguous_returns_none():
    # both markers present -> user must decide
    assert suggest_signal_type("trust me, he introduced me to his mom") is None


def test_suggest_no_marker_returns_none():
    assert suggest_signal_type("we had coffee") is None


def test_signal_type_roundtrip_through_storage(tmp_path):
    from love_risk_engine.storage.database import Database

    db = Database(str(tmp_path / "t.db"))
    db.init()
    rid = db.add_relationship("Alex")
    oid = db.add_observation(
        rid,
        "x",
        "he paid",
        "i",
        "a",
        "self",
        5.0,
        signal_type=SignalType.COSTLY,
    )
    obs = db.get_observations(rid)
    assert len(obs) == 1
    assert obs[0].signal_type is SignalType.COSTLY
    assert obs[0].id == oid
    db.close()
