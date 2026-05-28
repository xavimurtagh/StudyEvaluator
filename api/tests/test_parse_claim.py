from api.pipeline.parse_claim import parse_claim


def test_regrow_claim():
    p = parse_claim("Collagen supplements regrow hair")
    assert p is not None
    assert p.subject == "collagen supplements"
    assert p.predicate == "regrows hair"


def test_reduce_claim():
    p = parse_claim("Ashwagandha reduces stress and anxiety")
    assert p is not None
    assert p.subject == "ashwagandha"
    assert p.predicate.startswith("reduces ")
    assert "stress" in p.predicate


def test_helps_with_normalizes_to_improves():
    p = parse_claim("Magnesium helps with sleep")
    assert p is not None
    assert p.subject == "magnesium"
    assert p.predicate == "improves sleep"


def test_strips_marketing_fluff():
    p = parse_claim("This amazing new natural collagen improves skin")
    assert p is not None
    assert "amazing" not in p.subject
    assert "natural" not in p.subject
    assert "collagen" in p.subject


def test_no_verb_falls_back_to_subject_only():
    p = parse_claim("ashwagandha")
    assert p is not None
    assert p.subject == "ashwagandha"
    assert p.predicate == ""


def test_empty_input_returns_none():
    assert parse_claim("") is None
    assert parse_claim("   ") is None


def test_boost_and_increase_normalize_to_improves():
    a = parse_claim("Vitamin D boosts immunity")
    b = parse_claim("Vitamin D increases immunity")
    assert a and b
    assert a.predicate == "improves immunity"
    assert b.predicate == "improves immunity"
