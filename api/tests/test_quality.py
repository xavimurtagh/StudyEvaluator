from api.pipeline.extract import extract
from api.pipeline.quality import RubricQualityScorer
from api.schemas import StudyDesign
from api.tests.fixtures import make_corpus


def test_meta_analysis_scores_higher_than_case_series():
    scorer = RubricQualityScorer()
    corpus = [extract(r) for r in make_corpus()]
    meta = next(s for s in corpus if s.design == StudyDesign.META_ANALYSIS)
    case = next(s for s in corpus if s.design == StudyDesign.CASE_SERIES)
    assert scorer.score(meta).score > scorer.score(case).score


def test_industry_funded_penalizes_risk_of_bias():
    scorer = RubricQualityScorer()
    corpus = [extract(r) for r in make_corpus()]
    industry = next(s for s in corpus if s.pmid == "10000002")
    clean = next(s for s in corpus if s.pmid == "10000006")
    assert (
        scorer.score(industry).subscores.risk_of_bias
        < scorer.score(clean).subscores.risk_of_bias
    )


def test_animal_study_external_validity_low():
    scorer = RubricQualityScorer()
    corpus = [extract(r) for r in make_corpus()]
    animal = next(s for s in corpus if s.pmid == "10000004")
    assessment = scorer.score(animal)
    assert assessment.subscores.external_validity < 0.5
    assert any("Non-human" in r or "extrapolate" in r for r in assessment.reasons)


def test_score_is_bounded_and_reasoned():
    scorer = RubricQualityScorer()
    for rec in make_corpus():
        s = extract(rec)
        a = scorer.score(s)
        assert 0.0 <= a.score <= 1.0
        assert a.reasons, "every score should be accompanied by reasons"
        assert a.model_version


def test_pre_registered_rct_rewarded():
    scorer = RubricQualityScorer()
    corpus = [extract(r) for r in make_corpus()]
    prereg_rct = next(s for s in corpus if s.pmid == "10000006")
    a = scorer.score(prereg_rct)
    assert any("Pre-registered" in r for r in a.reasons)
    assert a.subscores.risk_of_bias > 0.6


def test_default_scorer_uses_ml_when_artifact_present(tmp_path, monkeypatch):
    """When models/quality_v1.joblib exists, the pipeline picks the ML scorer."""
    import joblib
    import numpy as np
    from sklearn.ensemble import GradientBoostingClassifier

    from api.pipeline import quality as q

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    artifact = model_dir / "quality_v1.joblib"

    # Train a trivial 1-tree model so loading succeeds.
    X = np.random.RandomState(0).randn(50, len(q.FEATURE_NAMES))
    y = (X[:, 0] > 0).astype(int)
    m = GradientBoostingClassifier(n_estimators=5, max_depth=1, random_state=0)
    m.fit(X, y)
    joblib.dump(m, artifact)

    monkeypatch.setattr(q, "MODEL_PATH", artifact)
    scorer = q.default_scorer()
    assert isinstance(scorer, q.MLQualityScorer)
    assert scorer.model is not None
