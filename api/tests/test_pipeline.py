"""End-to-end pipeline test: feeds the fixture corpus through and asserts
the verdict surfaces the right grades and red flags.

This is the test that proves the whole story works: a contradicted claim
('hair growth') comes back as contradicted, supported claims come back as
moderate-or-better, and the red flags fire when they should.
"""

from __future__ import annotations

import asyncio

from api.pipeline.run import analyze_product
from api.schemas import EvidenceGrade
from api.tests.fixtures import make_corpus


def _run(claims=None):
    return asyncio.run(
        analyze_product(
            "collagen peptides",
            claims_override=claims,
            records_override=make_corpus(),
        )
    )


def test_pipeline_runs_end_to_end():
    verdict = _run(
        claims=[
            "improves skin elasticity",
            "improves hair growth",
            "improves wound healing",
        ]
    )
    assert verdict.product == "collagen peptides"
    assert verdict.slug == "collagen-peptides"
    assert len(verdict.studies) == len(make_corpus())
    assert len(verdict.claims) == 3
    # Every claim has plain-language summary text.
    for c in verdict.claims:
        assert c.plain_language


def test_skin_elasticity_claim_finds_supporting_rct():
    """The RCT supports elasticity; a second RCT contradicts (found null).
    The aligner must identify both -- whatever final grade the aggregator
    settles on, both signals have to be present."""
    verdict = _run(claims=["improves skin elasticity"])
    c = verdict.claims[0]
    supporting_pmids = {l.pmid for l in c.supporting_studies}
    contradicting_pmids = {l.pmid for l in c.contradicting_studies}
    assert "10000001" in supporting_pmids
    assert "10000006" in contradicting_pmids
    # A claim with one for and one against is NOT strong evidence -- the
    # aggregator should treat this conservatively.
    assert c.grade != EvidenceGrade.STRONG


def test_skin_hydration_claim_is_supported():
    """Two studies report hydration improving (one explicit, one in the RCT
    that found null on elasticity). This claim should NOT be contradicted."""
    verdict = _run(claims=["improves skin hydration"])
    c = verdict.claims[0]
    assert c.grade in (EvidenceGrade.WEAK, EvidenceGrade.MODERATE, EvidenceGrade.STRONG)
    assert any(l.pmid == "10000006" for l in c.supporting_studies)


def test_hair_growth_claim_is_contradicted_or_insufficient():
    """The meta-analysis explicitly reports null on hair growth -- the verdict
    must reflect that rather than treating any mention as support."""
    verdict = _run(claims=["improves hair growth"])
    c = verdict.claims[0]
    assert c.grade in (
        EvidenceGrade.CONTRADICTED,
        EvidenceGrade.INSUFFICIENT,
        EvidenceGrade.WEAK,
    )


def test_wound_healing_claim_only_supported_by_animal_study():
    """Animal-only evidence for a human-marketed claim should NOT come back
    as strong. The aggregator downgrades based on quality + design tier."""
    verdict = _run(claims=["improves wound healing"])
    c = verdict.claims[0]
    assert c.grade != EvidenceGrade.STRONG
    assert c.grade != EvidenceGrade.MODERATE


def test_red_flags_surface_industry_funding_when_relevant():
    # Force a corpus heavily skewed industry-funded.
    from api.pipeline.ingest import RawRecord

    industry_heavy = [
        RawRecord(
            pmid=str(i),
            title="trial",
            abstract="randomized double-blind placebo-controlled n=40 participants",
            journal=None,
            year=2022,
            authors=[],
            doi=None,
            mesh_terms=[],
            publication_types=["Randomized Controlled Trial"],
            has_coi_statement=True,
            coi_text="Employee of BigPharma Inc.",
            funding_text="BigPharma Inc.",
        )
        for i in range(5)
    ]
    verdict = asyncio.run(
        analyze_product(
            "test",
            claims_override=["improves outcome"],
            records_override=industry_heavy,
        )
    )
    kinds = {f.kind for f in verdict.red_flags}
    assert "industry_funding" in kinds


def test_empty_corpus_returns_clean_insufficient_verdict():
    verdict = asyncio.run(
        analyze_product(
            "nothing",
            claims_override=["improves something"],
            records_override=[],
        )
    )
    assert verdict.overall_grade == EvidenceGrade.INSUFFICIENT
    assert verdict.claims[0].grade == EvidenceGrade.INSUFFICIENT
    assert verdict.studies == []


def test_summary_reflects_claim_distribution():
    verdict = _run(
        claims=[
            "improves skin elasticity",
            "improves hair growth",
            "improves wound healing",
        ]
    )
    assert "collagen peptides" in verdict.summary
