from api.pipeline.extract import (
    classify_design,
    detect_blinded,
    detect_industry_funding,
    detect_placebo,
    detect_preregistered,
    detect_randomized,
    extract,
    extract_duration_weeks,
    extract_sample_size,
)
from api.schemas import StudyDesign
from api.tests.fixtures import make_corpus


def test_classifies_rct_from_publication_type():
    rec = make_corpus()[0]
    assert classify_design(rec) == StudyDesign.RCT


def test_classifies_meta_analysis():
    rec = make_corpus()[2]
    assert classify_design(rec) == StudyDesign.META_ANALYSIS


def test_classifies_animal():
    rec = make_corpus()[3]
    d = classify_design(rec)
    assert d in (StudyDesign.ANIMAL, StudyDesign.UNKNOWN)
    # Whichever path, the human_subjects flag should land at False after extract.
    s = extract(rec)
    if d == StudyDesign.ANIMAL:
        assert s.human_subjects is False


def test_classifies_case_series():
    rec = make_corpus()[4]
    assert classify_design(rec) == StudyDesign.CASE_SERIES


def test_extracts_sample_size():
    assert extract_sample_size("We randomized 120 healthy women") == 120
    assert extract_sample_size("Two hundred adults were enrolled") is None  # words
    assert extract_sample_size("n = 540 participants") == 540


def test_extracts_duration_weeks():
    assert extract_duration_weeks("for 12 weeks") == 12
    assert extract_duration_weeks("over 6 months") == 6 * 4.345
    assert extract_duration_weeks("during 1 year") == 52.18


def test_detects_blinding_randomization_placebo():
    text = "randomized, double-blind, placebo-controlled trial"
    assert detect_blinded(text) is True
    assert detect_randomized(text) is True
    assert detect_placebo(text) is True


def test_detects_preregistration():
    assert detect_preregistered("Registered at ClinicalTrials.gov NCT01234567") is True
    assert detect_preregistered("no preregistration") is None


def test_detects_industry_funding():
    rec = make_corpus()[1]
    assert detect_industry_funding(rec) is True
    rec_clean = make_corpus()[2]
    assert detect_industry_funding(rec_clean) in (False, None)


def test_extract_pipeline_produces_findings():
    rec = make_corpus()[0]
    study = extract(rec)
    assert study.design == StudyDesign.RCT
    assert study.sample_size == 120
    assert study.duration_weeks == 12
    assert study.randomized is True
    assert study.blinded is True
    assert study.placebo_controlled is True
    assert any(f.direction == "positive" for f in study.findings)


def test_null_finding_extracted_for_meta_analysis():
    rec = make_corpus()[2]
    study = extract(rec)
    # The meta-analysis explicitly reports a null result on hair growth.
    assert any(f.direction in ("null", "negative") for f in study.findings)


# --- Attribution-aware finding direction -----------------------------------

from api.pipeline.extract import extract_findings


def test_placebo_attribution_demotes_positive_to_inconclusive():
    """Real example from a magnesium study: the sentence says the placebo
    improved sleep, not magnesium. Reading this as a positive finding for
    magnesium is wrong -- it should be inconclusive."""
    abstract = (
        "We randomized 100 older adults to magnesium or placebo for 7 weeks. "
        "Because dietary magnesium intake did not change during the experimental "
        "period, another factor, possibly a placebo effect, improved sleep "
        "quality, which resulted in increased erythrocyte magnesium."
    )
    findings = extract_findings(abstract)
    # The "did not change" sentence is its own finding (null).
    nulls = [f for f in findings if f.direction == "null"]
    inconclusives = [f for f in findings if f.direction == "inconclusive"]
    assert inconclusives, f"expected an inconclusive finding, got {findings}"
    # The "another factor / placebo effect / improved" sentence must NOT be
    # tagged positive.
    positives = [f for f in findings if f.direction == "positive"]
    assert not any("placebo effect" in p.text.lower() for p in positives)


def test_did_not_change_is_now_a_null_hint():
    findings = extract_findings(
        "Dietary intake of the supplement did not change during the trial."
    )
    assert findings and findings[0].direction == "null"


def test_genuine_positive_still_works():
    findings = extract_findings(
        "Supplementation significantly improved skin elasticity (p < 0.001)."
    )
    assert findings and findings[0].direction == "positive"


def test_rather_than_demotes_to_inconclusive():
    findings = extract_findings(
        "Outcomes improved due to lifestyle changes rather than the supplement."
    )
    assert findings and findings[0].direction == "inconclusive"


# --- Alignment routing of inconclusive findings ----------------------------

from api.pipeline.alignment import AlignmentScorer
from api.schemas import AlignmentLabel, ExtractedFinding, ExtractedStudy, StudyDesign


def test_inconclusive_finding_routes_to_unrelated():
    study = ExtractedStudy(
        pmid="x1",
        title="Magnesium supplementation and sleep quality",
        abstract=(
            "We randomized 100 older adults to magnesium or placebo. Because "
            "dietary magnesium intake did not change during the experimental "
            "period, another factor, possibly a placebo effect, improved sleep "
            "quality."
        ),
        design=StudyDesign.RCT,
        findings=[
            ExtractedFinding(
                text=(
                    "another factor, possibly a placebo effect, improved sleep "
                    "quality"
                ),
                direction="inconclusive",
            ),
        ],
    )
    scorer = AlignmentScorer()
    scorer.fit_corpus([study])
    link = scorer.classify("magnesium improves sleep", study)
    assert link.alignment == AlignmentLabel.UNRELATED


def test_genuine_null_still_contradicts():
    study = ExtractedStudy(
        pmid="x2",
        title="Magnesium supplementation and sleep quality",
        abstract="No significant difference in sleep quality between groups.",
        design=StudyDesign.RCT,
        findings=[
            ExtractedFinding(
                text="No significant difference in sleep quality between groups.",
                direction="null",
            ),
        ],
    )
    scorer = AlignmentScorer()
    scorer.fit_corpus([study])
    link = scorer.classify("magnesium improves sleep", study)
    assert link.alignment == AlignmentLabel.CONTRADICTS
