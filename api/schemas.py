"""Shared types for the analysis pipeline.

Every stage of the pipeline reads and writes these. Keeping them in one file
makes the data contract obvious and makes it easy to swap implementations
(e.g. a trained classifier replacing the rubric-based one) without touching
the rest of the system.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class StudyDesign(str, Enum):
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    RCT = "rct"
    COHORT = "cohort"
    CASE_CONTROL = "case_control"
    CROSS_SECTIONAL = "cross_sectional"
    CASE_SERIES = "case_series"
    ANIMAL = "animal"
    IN_VITRO = "in_vitro"
    REVIEW = "narrative_review"
    UNKNOWN = "unknown"


# Ordering used by the aggregator: higher index = stronger design.
DESIGN_TIER: dict[StudyDesign, int] = {
    StudyDesign.IN_VITRO: 1,
    StudyDesign.ANIMAL: 2,
    StudyDesign.CASE_SERIES: 3,
    StudyDesign.CROSS_SECTIONAL: 4,
    StudyDesign.CASE_CONTROL: 5,
    StudyDesign.COHORT: 6,
    StudyDesign.REVIEW: 6,
    StudyDesign.RCT: 8,
    StudyDesign.SYSTEMATIC_REVIEW: 9,
    StudyDesign.META_ANALYSIS: 10,
    StudyDesign.UNKNOWN: 2,
}


class EvidenceGrade(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"


class AlignmentLabel(str, Enum):
    SUPPORTS = "supports"
    PARTIAL = "partially_supports"
    UNRELATED = "unrelated"
    CONTRADICTS = "contradicts"


class QualitySubscores(BaseModel):
    internal_validity: float = Field(ge=0, le=1)
    external_validity: float = Field(ge=0, le=1)
    risk_of_bias: float = Field(ge=0, le=1, description="0 = high risk, 1 = low risk")
    reporting: float = Field(ge=0, le=1)


class QualityAssessment(BaseModel):
    score: float = Field(ge=0, le=1)
    subscores: QualitySubscores
    reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable justifications surfaced in the UI.",
    )
    model_version: str


class ExtractedStudy(BaseModel):
    """Structured features pulled out of a paper's metadata + abstract."""

    pmid: str
    title: str
    abstract: str | None = None
    journal: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    url: str | None = None

    design: StudyDesign = StudyDesign.UNKNOWN
    sample_size: int | None = None
    population: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcomes: list[str] = Field(default_factory=list)
    duration_weeks: float | None = None

    blinded: bool | None = None
    randomized: bool | None = None
    placebo_controlled: bool | None = None
    preregistered: bool | None = None
    industry_funded: bool | None = None
    conflict_of_interest: bool | None = None
    human_subjects: bool | None = None
    retracted: bool = False

    # Free-text claims the abstract makes (positive / null / negative findings).
    findings: list["ExtractedFinding"] = Field(default_factory=list)


class ExtractedFinding(BaseModel):
    text: str
    direction: Literal["positive", "null", "negative", "inconclusive"] = "positive"
    effect_size: str | None = Field(
        default=None,
        description=(
            "Plain-text effect-size snippet pulled from the sentence "
            '(e.g. "improved by 12% (p<0.01)") when one was reported.'
        ),
    )


class ScoredStudy(BaseModel):
    extracted: ExtractedStudy
    quality: QualityAssessment


class ClaimEvidenceLink(BaseModel):
    pmid: str
    alignment: AlignmentLabel
    confidence: float = Field(ge=0, le=1)
    quote: str | None = None


class ClaimVerdict(BaseModel):
    claim: str
    grade: EvidenceGrade
    plain_language: str
    supporting_studies: list[ClaimEvidenceLink]
    contradicting_studies: list[ClaimEvidenceLink]
    notes: list[str] = Field(default_factory=list)


class RedFlag(BaseModel):
    kind: str
    message: str
    severity: Literal["info", "warning", "critical"] = "warning"


class ProductVerdict(BaseModel):
    product: str
    slug: str
    summary: str
    overall_grade: EvidenceGrade
    claims: list[ClaimVerdict]
    studies: list[ScoredStudy]
    red_flags: list[RedFlag]
    generated_at: str
    pipeline_version: str
    notes: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=120)
    claims: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of marketed benefits to evaluate. If omitted, the "
            "pipeline auto-derives candidate claims from the literature."
        ),
    )
    max_studies: int = Field(default=75, ge=5, le=500)


class JobStatus(BaseModel):
    job_id: str
    state: Literal["queued", "running", "complete", "error"]
    progress: float = 0.0
    message: str | None = None
    slug: str | None = None


ExtractedStudy.model_rebuild()
