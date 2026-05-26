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
