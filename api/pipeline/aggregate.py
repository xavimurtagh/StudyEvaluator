"""Aggregate per-study scores + per-claim alignments into a product verdict.

GRADE-inspired: start from the strongest design tier supporting the claim,
downgrade for inconsistency, imprecision, indirectness, risk of bias,
and publication-bias signals.

We deliberately surface heterogeneity and funding concentration as separate
RedFlags rather than collapsing them into the headline grade -- the whole
point of this tool is that "fully informed" beats "single number."
"""

from __future__ import annotations

from collections import Counter
from statistics import fmean

from api.schemas import (
    AlignmentLabel,
    ClaimEvidenceLink,
    ClaimVerdict,
    EvidenceGrade,
    ProductVerdict,
    RedFlag,
    ScoredStudy,
    StudyDesign,
    DESIGN_TIER,
)


SUPPORTING = {AlignmentLabel.SUPPORTS, AlignmentLabel.PARTIAL}
CONTRADICTING = {AlignmentLabel.CONTRADICTS}


def grade_claim(
    claim: str,
    links: list[ClaimEvidenceLink],
    studies_by_pmid: dict[str, ScoredStudy],
) -> ClaimVerdict:
    relevant = [l for l in links if l.alignment != AlignmentLabel.UNRELATED]
    supporting = [l for l in relevant if l.alignment in SUPPORTING]
    contradicting = [l for l in relevant if l.alignment in CONTRADICTING]

    if not relevant:
        return ClaimVerdict(
            claim=claim,
            grade=EvidenceGrade.INSUFFICIENT,
            plain_language=(
                f'No studies in the analyzed set address "{claim}" directly. '
                "Absence of evidence is itself the answer here -- treat marketing claims with skepticism."
            ),
            supporting_studies=[],
            contradicting_studies=[],
        )

    sup_weight, sup_max_tier = _weighted_signal(supporting, studies_by_pmid)
    con_weight, con_max_tier = _weighted_signal(contradicting, studies_by_pmid)

    notes: list[str] = []

    # Net signal -> base grade.
    net = sup_weight - con_weight
    max_tier = max(sup_max_tier, con_max_tier)

    if con_weight > sup_weight * 1.5 and con_weight >= 0.5:
        grade = EvidenceGrade.CONTRADICTED
    elif net <= 0.3:
        grade = EvidenceGrade.INSUFFICIENT
    elif max_tier >= DESIGN_TIER[StudyDesign.META_ANALYSIS] and net >= 1.0:
        grade = EvidenceGrade.STRONG
    elif max_tier >= DESIGN_TIER[StudyDesign.RCT] and net >= 0.8:
        grade = EvidenceGrade.MODERATE
    else:
        grade = EvidenceGrade.WEAK

    # Downgrades.
    avg_quality_supporting = (
        fmean(studies_by_pmid[l.pmid].quality.score for l in supporting)
        if supporting
        else 0.0
    )
    if grade in (EvidenceGrade.STRONG, EvidenceGrade.MODERATE) and avg_quality_supporting < 0.55:
        grade = EvidenceGrade.WEAK
        notes.append("Downgraded: average study quality is low.")

    if grade in (EvidenceGrade.STRONG, EvidenceGrade.MODERATE):
        n_studies = len(supporting)
        if n_studies < 2:
            grade = EvidenceGrade.WEAK
            notes.append("Downgraded: only a single supporting study (no replication).")

    plain = _plain_language(claim, grade, supporting, contradicting, studies_by_pmid)

    return ClaimVerdict(
        claim=claim,
        grade=grade,
        plain_language=plain,
        supporting_studies=supporting,
        contradicting_studies=contradicting,
        notes=notes,
    )


def _weighted_signal(
    links: list[ClaimEvidenceLink],
    studies_by_pmid: dict[str, ScoredStudy],
) -> tuple[float, int]:
    total = 0.0
    max_tier = 0
    for l in links:
        s = studies_by_pmid.get(l.pmid)
        if s is None:
            continue
        tier = DESIGN_TIER[s.extracted.design]
        max_tier = max(max_tier, tier)
        # Weight = design tier x quality x confidence in alignment.
        weight = (tier / 10.0) * s.quality.score * l.confidence
        if l.alignment == AlignmentLabel.PARTIAL:
            weight *= 0.5
        total += weight
    return total, max_tier


def _plain_language(
    claim: str,
    grade: EvidenceGrade,
    supporting: list[ClaimEvidenceLink],
    contradicting: list[ClaimEvidenceLink],
    studies_by_pmid: dict[str, ScoredStudy],
) -> str:
    n_sup = len(supporting)
    n_con = len(contradicting)
    designs = Counter(
        studies_by_pmid[l.pmid].extracted.design.value
        for l in supporting + contradicting
        if l.pmid in studies_by_pmid
    )
    design_summary = ", ".join(f"{n} {d.replace('_', ' ')}" for d, n in designs.most_common(3))

    if grade == EvidenceGrade.STRONG:
        return (
            f"Strong evidence that this is true. {n_sup} supporting studies "
            f"({design_summary}) consistently report this effect."
        )
    if grade == EvidenceGrade.MODERATE:
        return (
            f"Moderate evidence. {n_sup} studies support this claim ({design_summary}), "
            f"but more or higher-quality replication is needed for certainty."
        )
    if grade == EvidenceGrade.WEAK:
        return (
            f"Weak evidence. Only {n_sup} study(ies) support this claim, often from "
            f"smaller or lower-tier designs ({design_summary})."
        )
    if grade == EvidenceGrade.CONTRADICTED:
        return (
            f"The literature contradicts this claim: {n_con} studies report null or opposite "
            f"findings, vs. {n_sup} supporting. Marketing claims to the contrary are unsupported."
        )
    return (
        f'Insufficient evidence. {n_sup + n_con} relevant studies in our search '
        f"can't settle this either way -- and that itself is informative."
    )


def detect_red_flags(scored: list[ScoredStudy]) -> list[RedFlag]:
    flags: list[RedFlag] = []
    if not scored:
        return flags

    n = len(scored)
    industry = sum(1 for s in scored if s.extracted.industry_funded is True)
    if industry / n >= 0.4:
        flags.append(
            RedFlag(
                kind="industry_funding",
                message=(
                    f"{industry}/{n} studies declare industry funding. Sponsorship bias "
                    "is a known driver of inflated effect sizes."
                ),
                severity="warning",
            )
        )

    small = sum(
        1
        for s in scored
        if s.extracted.sample_size is not None and s.extracted.sample_size < 50
    )
    if small / n >= 0.5:
        flags.append(
            RedFlag(
                kind="small_n",
                message=(
                    f"{small}/{n} studies have fewer than 50 participants. Small studies "
                    "overestimate effects and often don't replicate."
                ),
                severity="warning",
            )
        )

    non_human = sum(
        1
        for s in scored
        if s.extracted.design in (StudyDesign.ANIMAL, StudyDesign.IN_VITRO)
    )
    if non_human / n >= 0.5:
        flags.append(
            RedFlag(
                kind="non_human_dominant",
                message=(
                    f"{non_human}/{n} studies are animal or in-vitro. Effects in mice or "
                    "cells often don't translate to humans at realistic doses."
                ),
                severity="critical",
            )
        )

    retracted = sum(1 for s in scored if s.extracted.retracted)
    if retracted:
        flags.append(
            RedFlag(
                kind="retracted",
                message=f"{retracted} study(ies) in this set have been retracted.",
                severity="critical",
            )
        )

    no_rct = not any(s.extracted.design == StudyDesign.RCT for s in scored)
    if no_rct and n >= 5:
        flags.append(
            RedFlag(
                kind="no_rcts",
                message=(
                    "No randomized controlled trials in the set. Without RCTs, causal "
                    "claims (e.g. 'X causes Y') are not well supported."
                ),
                severity="warning",
            )
        )

    avg_q = fmean(s.quality.score for s in scored)
    if avg_q < 0.4:
        flags.append(
            RedFlag(
                kind="low_overall_quality",
                message=f"Average study quality is low ({avg_q:.2f}). Interpret all claims cautiously.",
                severity="warning",
            )
        )
    return flags


def overall_grade(claims: list[ClaimVerdict]) -> EvidenceGrade:
    if not claims:
        return EvidenceGrade.INSUFFICIENT
    rank = {
        EvidenceGrade.CONTRADICTED: 0,
        EvidenceGrade.INSUFFICIENT: 1,
        EvidenceGrade.WEAK: 2,
        EvidenceGrade.MODERATE: 3,
        EvidenceGrade.STRONG: 4,
    }
    best = max(claims, key=lambda c: rank[c.grade])
    return best.grade


def summary_sentence(product: str, claims: list[ClaimVerdict]) -> str:
    if not claims:
        return f"No analyzable evidence was found for {product}."
    by_grade = Counter(c.grade for c in claims)

    def n(g: EvidenceGrade) -> int:
        return by_grade.get(g, 0)

    parts: list[str] = []
    if n(EvidenceGrade.STRONG):
        parts.append(f"{n(EvidenceGrade.STRONG)} claim(s) backed by strong evidence")
    if n(EvidenceGrade.MODERATE):
        parts.append(f"{n(EvidenceGrade.MODERATE)} with moderate evidence")
    if n(EvidenceGrade.WEAK):
        parts.append(f"{n(EvidenceGrade.WEAK)} with only weak evidence")
    if n(EvidenceGrade.INSUFFICIENT):
        parts.append(f"{n(EvidenceGrade.INSUFFICIENT)} with insufficient evidence")
    if n(EvidenceGrade.CONTRADICTED):
        parts.append(f"{n(EvidenceGrade.CONTRADICTED)} contradicted by the literature")

    return f"For {product}: " + "; ".join(parts) + "."
