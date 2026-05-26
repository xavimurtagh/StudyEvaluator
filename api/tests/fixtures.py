"""Test fixtures: hand-crafted RawRecords for the pipeline tests.

These look like the kind of studies PubMed actually returns for a typical
wellness ingredient query. The set is deliberately mixed: an RCT, a small
industry-funded trial, an animal study, a null finding, a meta-analysis,
and one obviously-weak case series.
"""

from __future__ import annotations

from api.pipeline.ingest import RawRecord


def make_corpus() -> list[RawRecord]:
    return [
        RawRecord(
            pmid="10000001",
            title=(
                "Effects of oral collagen peptides on skin elasticity: "
                "a randomized, double-blind, placebo-controlled trial"
            ),
            abstract=(
                "Background: Collagen supplementation has gained popularity. "
                "Methods: We randomized 120 healthy women to 10 g/day collagen "
                "peptides or placebo for 12 weeks. Outcomes were skin elasticity "
                "and hydration. Results: Collagen significantly improved skin "
                "elasticity compared to placebo (p<0.01). Hydration also "
                "increased significantly in the treatment group. Conclusions: "
                "Daily collagen peptides improved skin elasticity in healthy women. "
                "Registered at ClinicalTrials.gov NCT01234567."
            ),
            journal="Journal of Cosmetic Dermatology",
            year=2022,
            authors=["Smith J", "Doe A"],
            doi="10.1000/example.1",
            mesh_terms=["Collagen", "Skin", "Randomized Controlled Trial"],
            publication_types=["Randomized Controlled Trial"],
            has_coi_statement=True,
            coi_text="No competing interests declared.",
            funding_text="University of Example research grant.",
        ),
        RawRecord(
            pmid="10000002",
            title="Collagen peptides reduce joint pain in athletes: a pilot study",
            abstract=(
                "Twenty-two athletes received 5 g/day collagen for 24 weeks. "
                "Joint pain scores improved significantly. Funded by HealthCorp "
                "Pharmaceuticals Inc."
            ),
            journal="Open Sports Nutrition",
            year=2021,
            authors=["Brown K"],
            doi=None,
            mesh_terms=["Collagen"],
            publication_types=["Clinical Trial"],
            has_coi_statement=True,
            coi_text="Authors are employees of HealthCorp Pharmaceuticals.",
            funding_text="HealthCorp Pharmaceuticals Inc.",
        ),
        RawRecord(
            pmid="10000003",
            title="Collagen supplementation and hair growth: a meta-analysis",
            abstract=(
                "We performed a systematic review and meta-analysis of "
                "randomized trials evaluating collagen for hair growth. Six "
                "trials (n=540) met inclusion criteria. The pooled effect on "
                "hair density was non-significant; there was no statistically "
                "significant benefit on hair growth compared to placebo. "
                "We conclude there is no evidence collagen improves hair growth."
            ),
            journal="Cochrane Database",
            year=2023,
            authors=["Lee C", "Patel R", "Garcia M"],
            doi="10.1000/example.3",
            mesh_terms=["Hair", "Collagen", "Meta-Analysis"],
            publication_types=["Meta-Analysis", "Systematic Review"],
            has_coi_statement=True,
            coi_text="No conflicts to declare.",
            funding_text=None,
        ),
        RawRecord(
            pmid="10000004",
            title="Collagen peptides accelerate wound healing in mice",
            abstract=(
                "In a murine wound-healing model, topical collagen peptides "
                "significantly improved wound closure rates over 14 days. "
                "These results suggest collagen may promote healing in vivo."
            ),
            journal="Experimental Dermatology",
            year=2019,
            authors=["Tanaka Y"],
            doi=None,
            mesh_terms=["Mice", "Wound Healing"],
            publication_types=["Journal Article"],
            has_coi_statement=False,
            coi_text=None,
            funding_text=None,
        ),
        RawRecord(
            pmid="10000005",
            title="Collagen peptides for nail brittleness: case series",
            abstract=(
                "We report on 8 patients with brittle nails who received "
                "collagen for 8 weeks. Nail strength scores improved in 6/8. "
                "Limitations include lack of controls and small sample size."
            ),
            journal="Dermatology Reports",
            year=2018,
            authors=["Garcia M"],
            doi=None,
            mesh_terms=["Nails"],
            publication_types=["Case Reports"],
            has_coi_statement=False,
            coi_text=None,
            funding_text=None,
        ),
        RawRecord(
            pmid="10000006",
            title=(
                "Hydrolyzed collagen vs placebo for skin hydration: "
                "a randomized controlled trial in 200 adults"
            ),
            abstract=(
                "Two hundred adults were randomized to collagen or placebo for "
                "8 weeks. Skin hydration improved significantly in the treatment "
                "group. No significant difference was observed in elasticity. "
                "Pre-registered on ClinicalTrials.gov."
            ),
            journal="Nutrients",
            year=2024,
            authors=["Nguyen T", "Olsen P"],
            doi="10.1000/example.6",
            mesh_terms=["Skin", "Hydration"],
            publication_types=["Randomized Controlled Trial"],
            has_coi_statement=True,
            coi_text="No competing interests.",
            funding_text="National research grant.",
        ),
    ]
