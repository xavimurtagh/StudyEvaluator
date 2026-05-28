"""Tests for retraction detection, S2 adapter, and cross-source dedup."""

from __future__ import annotations

from api.pipeline.extract import detect_retraction, extract
from api.pipeline.ingest import RawRecord
from api.pipeline.semantic_scholar import (
    _normalize_title,
    _to_raw_record,
    dedupe_records,
)


def _rec(**overrides) -> RawRecord:
    defaults = dict(
        pmid="1",
        title="x",
        abstract="",
        journal=None,
        year=None,
        authors=[],
        doi=None,
        mesh_terms=[],
        publication_types=[],
        has_coi_statement=False,
        coi_text=None,
        funding_text=None,
    )
    defaults.update(overrides)
    return RawRecord(**defaults)


def test_retraction_via_pubtype():
    r = _rec(publication_types=["Retracted Publication"])
    assert detect_retraction(r) is True


def test_retraction_via_title_prefix():
    r = _rec(title="Retraction: Some Paper About X")
    assert detect_retraction(r) is True


def test_no_retraction_for_normal_paper():
    r = _rec(publication_types=["Randomized Controlled Trial"], title="A good RCT")
    assert detect_retraction(r) is False


def test_extract_carries_retraction_flag():
    r = _rec(publication_types=["Retracted Publication"], title="Bad study")
    e = extract(r)
    assert e.retracted is True


def test_s2_adapter_handles_normal_paper():
    p = {
        "paperId": "abc123",
        "externalIds": {"PubMed": "9999", "DOI": "10.1/x"},
        "title": "Effects of compound X on outcome Y",
        "abstract": "We randomized 100 adults. Result improved by 10%.",
        "year": 2023,
        "authors": [{"name": "Smith J"}, {"name": "Doe A"}],
        "venue": "Test Journal",
        "publicationTypes": ["RandomizedControlledTrial"],
    }
    rec = _to_raw_record(p)
    assert rec is not None
    assert rec.pmid == "9999"
    assert rec.doi == "10.1/x"
    assert "Randomized Controlled Trial" in rec.publication_types


def test_s2_adapter_falls_back_to_s2_pmid_when_no_pubmed_id():
    p = {
        "paperId": "abc123",
        "externalIds": {},
        "title": "Some paper",
        "abstract": "",
        "authors": [],
    }
    rec = _to_raw_record(p)
    assert rec is not None
    assert rec.pmid.startswith("s2:")


def test_s2_adapter_drops_paper_without_title():
    assert _to_raw_record({"paperId": "x", "title": ""}) is None


def test_normalize_title_strips_punctuation_and_case():
    assert _normalize_title("Effects of X on Y: a RCT!") == "effects of x on y a rct"


def test_dedup_prefers_pubmed_over_s2_with_same_doi():
    pm = _rec(
        pmid="111",
        title="Same paper",
        doi="10.1/same",
        abstract="Long abstract " * 20,
        publication_types=["Randomized Controlled Trial"],
        mesh_terms=["x"],
    )
    s2 = _rec(pmid="s2:abc", title="Same paper", doi="10.1/same", abstract="short")
    out = dedupe_records([s2, pm])
    assert len(out) == 1
    assert out[0].pmid == "111"


def test_dedup_matches_on_normalized_title_when_no_doi():
    a = _rec(pmid="111", title="Effects of X on Y", abstract="Long " * 50)
    b = _rec(pmid="s2:abc", title="Effects of X on Y!", abstract="")
    out = dedupe_records([a, b])
    assert len(out) == 1
    assert out[0].pmid == "111"


def test_dedup_keeps_distinct_papers():
    a = _rec(pmid="1", title="Paper A", doi="10.1/a")
    b = _rec(pmid="2", title="Paper B", doi="10.1/b")
    assert len(dedupe_records([a, b])) == 2
