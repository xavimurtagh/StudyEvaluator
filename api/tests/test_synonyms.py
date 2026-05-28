"""Tests for lay-term -> biomedical query expansion."""

from __future__ import annotations

from api.pipeline.synonyms import expand_query


def test_unknown_term_passes_through_unchanged():
    r = expand_query("widgetide")
    assert r.canonical == "widgetide"
    assert r.expansions == []
    assert r.was_expanded is False


def test_sun_cream_expands_to_sunscreen():
    r = expand_query("sun cream")
    assert r.canonical == "sunscreen"
    assert r.was_expanded is True
    assert any("sunscreen" in e for e in r.expansions)


def test_expansion_is_case_insensitive():
    assert expand_query("Sun Cream").canonical == "sunscreen"
    assert expand_query("FISH OIL").canonical == "omega-3 fatty acids"


def test_brand_names_map_to_generic():
    assert expand_query("tylenol").canonical == "acetaminophen"
    assert expand_query("ozempic").canonical == "semaglutide"


def test_pubmed_query_format():
    # Single-word expansion: unquoted
    r = expand_query("sun cream")  # -> sunscreen (single word)
    assert r.pubmed_query.startswith("sunscreen[Title/Abstract]")
    assert "[MeSH Terms]" in r.pubmed_query

    # Multi-word expansion: quoted
    r2 = expand_query("aspirin")  # -> acetylsalicylic acid
    assert '"acetylsalicylic acid"' in r2.pubmed_query

    # Unknown single word: passes through unquoted
    r3 = expand_query("widgetide")
    assert r3.pubmed_query.startswith("widgetide[Title/Abstract]")


def test_trailing_punctuation_tolerated():
    r = expand_query("sun cream?")
    assert r.canonical == "sunscreen"
