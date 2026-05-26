"""Pull structured features out of a PubMed record.

This is parsing, not judgment. The goal: turn an abstract into a typed
ExtractedStudy that downstream stages can score deterministically.

Designed so an LLM-based extractor could be dropped in behind the same
function signature later -- but keeping it rule-based today means the
demo runs without API keys and the features stay debuggable.
"""

from __future__ import annotations

import re

from api.pipeline.ingest import RawRecord
from api.schemas import ExtractedFinding, ExtractedStudy, StudyDesign


# --- Study design classification --------------------------------------------

DESIGN_PATTERNS: list[tuple[StudyDesign, list[str]]] = [
    (StudyDesign.META_ANALYSIS, [r"meta[- ]analy[sz]is", r"individual patient data meta"]),
    (
        StudyDesign.SYSTEMATIC_REVIEW,
        [r"systematic review", r"prisma", r"cochrane review"],
    ),
    (
        StudyDesign.RCT,
        [
            r"\brandomi[sz]ed\b.{0,40}\btrial\b",
            r"\brct\b",
            r"double[- ]blind",
            r"placebo[- ]controlled",
        ],
    ),
    (StudyDesign.COHORT, [r"\bcohort\b", r"prospective cohort", r"longitudinal study"]),
    (StudyDesign.CASE_CONTROL, [r"case[- ]control"]),
    (StudyDesign.CROSS_SECTIONAL, [r"cross[- ]sectional"]),
    (StudyDesign.CASE_SERIES, [r"case series", r"case report"]),
    (StudyDesign.ANIMAL, [r"\bin mice\b", r"\bin rats\b", r"murine", r"rodent", r"zebrafish"]),
    (StudyDesign.IN_VITRO, [r"\bin vitro\b", r"cell line", r"cultured cells"]),
    (StudyDesign.REVIEW, [r"narrative review", r"\breview\b"]),
]

PUBTYPE_TO_DESIGN: dict[str, StudyDesign] = {
    "Meta-Analysis": StudyDesign.META_ANALYSIS,
    "Systematic Review": StudyDesign.SYSTEMATIC_REVIEW,
    "Randomized Controlled Trial": StudyDesign.RCT,
    "Clinical Trial": StudyDesign.RCT,
    "Observational Study": StudyDesign.COHORT,
    "Review": StudyDesign.REVIEW,
    "Case Reports": StudyDesign.CASE_SERIES,
}


def classify_design(record: RawRecord) -> StudyDesign:
    # PubMed's PublicationType is authoritative when available.
    for pt in record.publication_types:
        if pt in PUBTYPE_TO_DESIGN:
            return PUBTYPE_TO_DESIGN[pt]

    text = f"{record.title}\n{record.abstract}".lower()
    for design, patterns in DESIGN_PATTERNS:
        for pat in patterns:
            if re.search(pat, text):
                return design
    return StudyDesign.UNKNOWN


# --- Population / sample size / duration ------------------------------------

# Avoid matching CIs ("95% CI"), p-values, or doses ("100 mg").
SAMPLE_PATTERNS = [
    r"\bn\s*=\s*([0-9]{2,6})\b",
    r"\b([0-9]{2,6})\s+(?:participants?|patients?|subjects?|adults?|women|men|volunteers?)\b",
    r"\benrolled\s+([0-9]{2,6})\b",
    r"\brandomi[sz]ed\s+([0-9]{2,6})\b",
]


def extract_sample_size(text: str) -> int | None:
    candidates: list[int] = []
    for pat in SAMPLE_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            try:
                n = int(m.group(1))
            except (ValueError, IndexError):
                continue
            if 5 <= n <= 1_000_000:
                candidates.append(n)
    if not candidates:
        return None
    # Take the largest plausible -- abstracts often mention a subgroup first
    # and the total cohort after. The full N is what we want for power.
    return max(candidates)


DURATION_PATTERN = re.compile(
    r"\b(?:for|over|during)\s+([0-9]{1,3})\s*(?:-?\s*)(week|weeks|month|months|year|years|day|days)\b",
    flags=re.IGNORECASE,
)


def extract_duration_weeks(text: str) -> float | None:
    m = DURATION_PATTERN.search(text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("day"):
        return value / 7
    if unit.startswith("week"):
        return value
    if unit.startswith("month"):
        return value * 4.345
    if unit.startswith("year"):
        return value * 52.18
    return None


def extract_population(text: str) -> str | None:
    # Heuristic: take the first descriptive noun phrase about subjects.
    m = re.search(
        r"(healthy (?:adults?|men|women|volunteers?)"
        r"|(?:adults?|men|women|patients?|children|adolescents?|elderly)"
        r"(?:\s+with\s+[a-z][a-z\s-]{2,40})?)",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    pop = m.group(0).strip()
    return pop[:120]


# --- Methodology flags ------------------------------------------------------


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def detect_blinded(text: str) -> bool | None:
    if _has(text, r"double[- ]blind", r"triple[- ]blind", r"single[- ]blind"):
        return True
    if _has(text, r"open[- ]label", r"unblinded"):
        return False
    return None


def detect_randomized(text: str) -> bool | None:
    if _has(text, r"\brandomi[sz]ed\b", r"\brct\b"):
        return True
    if _has(text, r"non[- ]randomi[sz]ed"):
        return False
    return None


def detect_placebo(text: str) -> bool | None:
    if _has(text, r"placebo[- ]controlled", r"\bvs\.?\s+placebo\b", r"compared to placebo"):
        return True
    return None


def detect_preregistered(text: str) -> bool | None:
    if _has(text, r"clinicaltrials\.gov", r"NCT0?[0-9]{6,}", r"pre[- ]registered"):
        return True
    return None


def detect_human(text: str, design: StudyDesign) -> bool | None:
    if design in (StudyDesign.ANIMAL, StudyDesign.IN_VITRO):
        return False
    if _has(
        text,
        r"\bin humans?\b",
        r"\bparticipants?\b",
        r"\bpatients?\b",
        r"\bsubjects?\b",
        r"\bvolunteers?\b",
    ):
        return True
    return None


INDUSTRY_KEYWORDS = (
    "pharma",
    "pharmaceutical",
    "inc.",
    "ltd",
    "gmbh",
    "corp",
    "industries",
    "supplements",
    "nutraceutical",
    "cosmetic",
    "beauty",
)


def detect_industry_funding(record: RawRecord) -> bool | None:
    blob = " ".join(
        filter(None, [record.funding_text, record.coi_text, record.abstract])
    ).lower()
    if not blob:
        return None
    if any(k in blob for k in INDUSTRY_KEYWORDS):
        return True
    if "no funding" in blob or "no external funding" in blob:
        return False
    return None


def detect_conflict_of_interest(record: RawRecord) -> bool | None:
    if not record.has_coi_statement:
        return None
    text = (record.coi_text or "").lower()
    if not text:
        return None
    if re.search(r"no (?:conflicts?|competing interests?)|nothing to declare", text):
        return False
    if re.search(
        r"employee of|consultant for|honorari|speakers? bureau|shareholder|funded by|grants? from",
        text,
    ):
        return True
    return None


# --- Findings extraction ----------------------------------------------------

POSITIVE_HINTS = (
    "significantly improved",
    "significantly increased",
    "significantly reduced",
    "significantly decreased",
    "associated with improvement",
    "effective in",
    "beneficial",
    "improved",
)
NULL_HINTS = (
    "no significant",
    "no statistically significant",
    "did not differ",
    "no effect",
    "not associated",
    "non-significant",
)
NEGATIVE_HINTS = (
    "worsened",
    "increased risk",
    "adverse",
    "harmful",
    "deteriorat",
)


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    # Naive but predictable -- avoids adding nltk just for this.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def extract_findings(abstract: str) -> list[ExtractedFinding]:
    out: list[ExtractedFinding] = []
    for sent in split_sentences(abstract):
        low = sent.lower()
        if any(h in low for h in NEGATIVE_HINTS):
            out.append(ExtractedFinding(text=sent, direction="negative"))
        elif any(h in low for h in NULL_HINTS):
            out.append(ExtractedFinding(text=sent, direction="null"))
        elif any(h in low for h in POSITIVE_HINTS):
            out.append(ExtractedFinding(text=sent, direction="positive"))
    return out[:8]


# --- Orchestrator -----------------------------------------------------------


def extract(record: RawRecord) -> ExtractedStudy:
    text = f"{record.title}\n{record.abstract}"
    design = classify_design(record)
    return ExtractedStudy(
        pmid=record.pmid,
        title=record.title,
        abstract=record.abstract,
        journal=record.journal,
        year=record.year,
        authors=record.authors,
        doi=record.doi,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{record.pmid}/" if record.pmid else None,
        design=design,
        sample_size=extract_sample_size(text),
        duration_weeks=extract_duration_weeks(text),
        population=extract_population(text),
        blinded=detect_blinded(text),
        randomized=detect_randomized(text),
        placebo_controlled=detect_placebo(text),
        preregistered=detect_preregistered(text),
        industry_funded=detect_industry_funding(record),
        conflict_of_interest=detect_conflict_of_interest(record),
        human_subjects=detect_human(text, design),
        findings=extract_findings(record.abstract),
    )
