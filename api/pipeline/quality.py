"""Study quality classifier.

Two implementations behind one interface:

  RubricQualityScorer  -- interpretable, ships today, no training data needed.
                          Encodes the Cochrane Risk of Bias 2 categories as
                          weighted rules. Every score comes with reasons.

  MLQualityScorer      -- gradient-boosted classifier over the same feature
                          vector. Trains on labeled examples (Cochrane RoB +
                          Retraction Watch). Falls back to the rubric if no
                          model artifact is present.

Both produce a QualityAssessment, so callers don't care which is in use.

The shared feature vector is the contract: if you train a model, you train
on the output of `featurize`. That keeps training and inference in sync.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from api.schemas import (
    ExtractedStudy,
    QualityAssessment,
    QualitySubscores,
    StudyDesign,
)

MODEL_DIR = Path(os.environ.get("STUDYEVAL_MODEL_DIR", "./models"))
MODEL_PATH = MODEL_DIR / "quality_v1.joblib"


# --- Shared feature vector --------------------------------------------------

FEATURE_NAMES = [
    "is_meta_analysis",
    "is_systematic_review",
    "is_rct",
    "is_cohort",
    "is_case_control",
    "is_animal_or_in_vitro",
    "is_review",
    "log_sample_size",
    "duration_weeks_capped",
    "randomized",
    "blinded",
    "placebo_controlled",
    "preregistered",
    "industry_funded",
    "conflict_of_interest",
    "human_subjects",
    "retracted",
    "has_year",
    "recency_years",
]


def featurize(s: ExtractedStudy, now_year: int = 2026) -> np.ndarray:
    log_n = float(np.log1p(s.sample_size or 0))
    duration = min(s.duration_weeks or 0.0, 260.0)  # cap at ~5y for stability
    recency = float(now_year - s.year) if s.year else 30.0
    return np.array(
        [
            1.0 if s.design == StudyDesign.META_ANALYSIS else 0.0,
            1.0 if s.design == StudyDesign.SYSTEMATIC_REVIEW else 0.0,
            1.0 if s.design == StudyDesign.RCT else 0.0,
            1.0 if s.design == StudyDesign.COHORT else 0.0,
            1.0 if s.design == StudyDesign.CASE_CONTROL else 0.0,
            1.0 if s.design in (StudyDesign.ANIMAL, StudyDesign.IN_VITRO) else 0.0,
            1.0 if s.design == StudyDesign.REVIEW else 0.0,
            log_n,
            duration,
            _trinary(s.randomized),
            _trinary(s.blinded),
            _trinary(s.placebo_controlled),
            _trinary(s.preregistered),
            _trinary(s.industry_funded),
            _trinary(s.conflict_of_interest),
            _trinary(s.human_subjects),
            1.0 if s.retracted else 0.0,
            1.0 if s.year else 0.0,
            recency,
        ],
        dtype=np.float32,
    )


def _trinary(v: bool | None) -> float:
    # Unknowns sit at 0; positives at +1, negatives at -1. Lets the model and
    # rubric both treat "we don't know" differently from "we know it's false."
    if v is None:
        return 0.0
    return 1.0 if v else -1.0


# --- Interface --------------------------------------------------------------


class QualityScorer(Protocol):
    version: str

    def score(self, study: ExtractedStudy) -> QualityAssessment: ...


# --- Rubric implementation --------------------------------------------------


@dataclass
class _Adjustment:
    delta: float
    reason: str


class RubricQualityScorer:
    """Interpretable rubric based on Cochrane RoB 2 + GRADE intuitions.

    Subscores are mapped to a 0-1 range. The final score is a weighted
    average; weights are exposed below so they're auditable.
    """

    version = "rubric-v1"

    DESIGN_BASE = {
        StudyDesign.META_ANALYSIS: 0.85,
        StudyDesign.SYSTEMATIC_REVIEW: 0.80,
        StudyDesign.RCT: 0.70,
        StudyDesign.COHORT: 0.55,
        StudyDesign.CASE_CONTROL: 0.45,
        StudyDesign.CROSS_SECTIONAL: 0.35,
        StudyDesign.CASE_SERIES: 0.20,
        StudyDesign.REVIEW: 0.40,
        StudyDesign.ANIMAL: 0.25,
        StudyDesign.IN_VITRO: 0.20,
        StudyDesign.UNKNOWN: 0.35,
    }

    def score(self, s: ExtractedStudy) -> QualityAssessment:
        reasons: list[str] = []

        # Internal validity: study design + execution rigor.
        iv = self.DESIGN_BASE[s.design]
        reasons.append(f"Design baseline: {s.design.value} ({iv:.2f})")

        for adj in self._internal_validity_adjustments(s):
            iv = _clip(iv + adj.delta)
            reasons.append(adj.reason)

        # External validity: generalizability.
        ev, ev_reasons = self._external_validity(s)
        reasons.extend(ev_reasons)

        # Risk of bias: 1.0 = low risk.
        rob, rob_reasons = self._risk_of_bias(s)
        reasons.extend(rob_reasons)

        # Reporting: do we even have the basics?
        rep, rep_reasons = self._reporting(s)
        reasons.extend(rep_reasons)

        sub = QualitySubscores(
            internal_validity=_clip(iv),
            external_validity=_clip(ev),
            risk_of_bias=_clip(rob),
            reporting=_clip(rep),
        )
        score = _clip(
            0.45 * sub.internal_validity
            + 0.25 * sub.risk_of_bias
            + 0.20 * sub.external_validity
            + 0.10 * sub.reporting
        )

        if s.retracted:
            score = 0.0
            reasons.append("RETRACTED -- score forced to 0.")

        return QualityAssessment(
            score=score,
            subscores=sub,
            reasons=reasons,
            model_version=self.version,
        )

    def _internal_validity_adjustments(self, s: ExtractedStudy) -> list[_Adjustment]:
        adjs: list[_Adjustment] = []
        if s.randomized is True:
            adjs.append(_Adjustment(+0.05, "Randomized allocation reported."))
        elif s.randomized is False:
            adjs.append(_Adjustment(-0.10, "Non-randomized allocation."))

        if s.blinded is True:
            adjs.append(_Adjustment(+0.05, "Blinding reported (single/double/triple)."))
        elif s.blinded is False:
            adjs.append(_Adjustment(-0.05, "Open-label / unblinded."))

        if s.placebo_controlled:
            adjs.append(_Adjustment(+0.03, "Placebo-controlled comparator."))

        if s.sample_size is not None:
            if s.sample_size < 30:
                adjs.append(_Adjustment(-0.10, f"Very small sample (n={s.sample_size})."))
            elif s.sample_size < 100:
                adjs.append(_Adjustment(-0.04, f"Small sample (n={s.sample_size})."))
            elif s.sample_size >= 500:
                adjs.append(_Adjustment(+0.04, f"Large sample (n={s.sample_size})."))

        if s.duration_weeks is not None and s.duration_weeks < 4:
            adjs.append(
                _Adjustment(-0.05, f"Short duration ({s.duration_weeks:.0f} weeks).")
            )
        return adjs

    def _external_validity(self, s: ExtractedStudy) -> tuple[float, list[str]]:
        reasons: list[str] = []
        ev = 0.6
        if s.human_subjects is False:
            ev = 0.15
            reasons.append("Non-human study -- limited applicability to people.")
        elif s.human_subjects is True:
            ev += 0.1
            reasons.append("Human subjects.")
        if s.population:
            ev += 0.05
            reasons.append(f"Population specified: {s.population}.")
        else:
            ev -= 0.05
            reasons.append("Population not clearly specified.")
        if s.design in (StudyDesign.ANIMAL, StudyDesign.IN_VITRO):
            reasons.append(
                "Marketers often extrapolate animal/in-vitro findings to humans -- treat with caution."
            )
        return _clip(ev), reasons

    def _risk_of_bias(self, s: ExtractedStudy) -> tuple[float, list[str]]:
        reasons: list[str] = []
        rob = 0.7
        if s.industry_funded is True:
            rob -= 0.15
            reasons.append("Industry funding declared -- elevated risk of sponsorship bias.")
        if s.conflict_of_interest is True:
            rob -= 0.10
            reasons.append("Author conflicts of interest declared.")
        if s.preregistered:
            rob += 0.10
            reasons.append("Pre-registered protocol -- lower risk of outcome switching.")
        if s.blinded is True:
            rob += 0.05
        if s.randomized is True:
            rob += 0.05
        if s.design in (
            StudyDesign.CASE_SERIES,
            StudyDesign.CROSS_SECTIONAL,
            StudyDesign.REVIEW,
        ):
            rob -= 0.05
            reasons.append("Design type carries higher inherent risk of bias.")
        return _clip(rob), reasons

    def _reporting(self, s: ExtractedStudy) -> tuple[float, list[str]]:
        reasons: list[str] = []
        rep = 0.5
        if s.abstract and len(s.abstract) > 300:
            rep += 0.2
        else:
            reasons.append("Sparse abstract -- could not verify methods in detail.")
        if s.sample_size is not None:
            rep += 0.1
        else:
            reasons.append("Sample size not stated in abstract.")
        if s.duration_weeks is not None:
            rep += 0.05
        if s.findings:
            rep += 0.05
        return _clip(rep), reasons


def _clip(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


# --- ML implementation ------------------------------------------------------


class MLQualityScorer:
    """Gradient-boosted classifier over the shared feature vector.

    Training script: scripts/train_quality.py.

    If no artifact is on disk we silently fall back to the rubric -- the
    classifier is the upgrade path, not a hard dependency for the demo.
    """

    version = "ml-v1"

    def __init__(self, fallback: QualityScorer | None = None):
        self.fallback = fallback or RubricQualityScorer()
        self.model = self._load()

    def _load(self):
        if not MODEL_PATH.exists():
            return None
        try:
            import joblib

            return joblib.load(MODEL_PATH)
        except Exception:
            return None

    def score(self, s: ExtractedStudy) -> QualityAssessment:
        if self.model is None:
            return self.fallback.score(s)
        x = featurize(s).reshape(1, -1)
        # The model is a regressor returning a 0-1 quality score. Older
        # classifier artifacts (predict_proba) are auto-detected and
        # converted to the same shape for back-compat.
        if hasattr(self.model, "predict_proba"):
            pred = float(self.model.predict_proba(x)[0, 1])
        else:
            pred = float(self.model.predict(x)[0])
        pred = max(0.0, min(1.0, pred))
        # We still get subscores from the rubric so the UI has reasons -- the
        # ML model only overrides the headline number.
        base = self.fallback.score(s)
        if s.retracted:
            pred = 0.0
        return QualityAssessment(
            score=pred,
            subscores=base.subscores,
            reasons=base.reasons + [f"ML model headline score: {pred:.2f}"],
            model_version=self.version,
        )


def default_scorer() -> QualityScorer:
    if MODEL_PATH.exists():
        return MLQualityScorer()
    return RubricQualityScorer()
