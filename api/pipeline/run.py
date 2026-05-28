"""End-to-end orchestrator: query string -> ProductVerdict."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Callable

from slugify import slugify

from api.pipeline import PIPELINE_VERSION
from api.pipeline.aggregate import (
    detect_red_flags,
    grade_claim,
    overall_grade,
    summary_sentence,
)
from api.pipeline.alignment import AlignmentScorer
from api.pipeline.claims import derive_claims
from api.pipeline.extract import extract
from api.pipeline.ingest import RawRecord, ingest
from api.pipeline.quality import default_scorer
from api.pipeline.retraction import find_retracted_dois
from api.pipeline.semantic_scholar import dedupe_records, ingest_s2
from api.pipeline.synonyms import expand_query
from api.schemas import (
    ClaimEvidenceLink,
    ExtractedStudy,
    ProductVerdict,
    ScoredStudy,
)


# Per-source toggles. Useful for tests and for users whose network can
# only reach one provider (sandboxed environments, locked-down corp nets).
USE_S2 = os.environ.get("STUDYEVAL_USE_S2", "1") == "1"
USE_CROSSREF = os.environ.get("STUDYEVAL_USE_CROSSREF", "1") == "1"

ProgressCb = Callable[[float, str], None]


async def analyze_product(
    product: str,
    max_studies: int = 25,
    claims_override: list[str] | None = None,
    on_progress: ProgressCb | None = None,
    records_override: list[RawRecord] | None = None,
) -> ProductVerdict:
    """Run the full pipeline. `records_override` lets tests skip the network."""

    def report(pct: float, msg: str) -> None:
        if on_progress:
            on_progress(pct, msg)

    expanded = expand_query(product)
    search_term = expanded.canonical
    report(0.05, "Fetching studies from PubMed and Semantic Scholar...")
    if records_override is not None:
        records = records_override
    else:
        # Hit both sources in parallel. S2 is a backstop -- if it fails or
        # is disabled we still have PubMed.
        pubmed_task = asyncio.create_task(ingest(search_term, max_studies=max_studies))
        if USE_S2:
            s2_task = asyncio.create_task(
                ingest_s2(search_term, max_studies=max_studies)
            )
            pm_recs, s2_recs = await asyncio.gather(pubmed_task, s2_task)
        else:
            pm_recs = await pubmed_task
            s2_recs = []
        records = dedupe_records(pm_recs + s2_recs)

    report(0.25, f"Extracting features from {len(records)} studies...")
    extracted: list[ExtractedStudy] = [extract(r) for r in records]

    # Cross-check for retractions CrossRef knows about that PubMed may not
    # have flagged via the pubtype yet. Best-effort: failures don't block.
    if USE_CROSSREF and records_override is None:
        report(0.40, "Cross-checking for retractions...")
        dois = [e.doi for e in extracted if e.doi and not e.retracted]
        try:
            retracted_dois = await find_retracted_dois(dois)
        except Exception:
            retracted_dois = set()
        if retracted_dois:
            for e in extracted:
                if e.doi and e.doi.lower() in {d.lower() for d in retracted_dois}:
                    e.retracted = True

    report(0.50, "Scoring study quality...")
    scorer = default_scorer()
    scored: list[ScoredStudy] = [
        ScoredStudy(extracted=e, quality=scorer.score(e)) for e in extracted
    ]
    studies_by_pmid = {s.extracted.pmid: s for s in scored}

    report(0.65, "Identifying marketed claims...")
    claims = claims_override or derive_claims(extracted, top_k=5)

    report(0.75, "Aligning claims to evidence...")
    aligner = AlignmentScorer()
    aligner.fit_corpus(extracted)

    claim_verdicts = []
    for claim in claims:
        links: list[ClaimEvidenceLink] = [
            aligner.classify(claim, e) for e in extracted
        ]
        claim_verdicts.append(grade_claim(claim, links, studies_by_pmid))

    report(0.90, "Aggregating verdict...")
    red_flags = detect_red_flags(scored)

    verdict = ProductVerdict(
        product=product,
        slug=slugify(product),
        summary=summary_sentence(product, claim_verdicts),
        overall_grade=overall_grade(claim_verdicts),
        claims=claim_verdicts,
        studies=scored,
        red_flags=red_flags,
        generated_at=datetime.now(timezone.utc).isoformat(),
        pipeline_version=PIPELINE_VERSION,
        notes=_global_notes(scored, claim_verdicts, expanded.expansions),
    )
    report(1.0, "Done.")
    return verdict


def _global_notes(scored, claim_verdicts, expansions: list[str] | None = None) -> list[str]:
    notes: list[str] = []
    for note in expansions or []:
        notes.append(note)
    if len(scored) < 5:
        notes.append(
            "Small corpus -- the verdict here is preliminary. Treat with caution."
        )
    if not claim_verdicts:
        notes.append(
            "We couldn't derive any marketed claims from the literature. Try "
            "submitting specific claims via the 'check a claim' form."
        )
    notes.append(
        "Always distinguish the ingredient (what studies test) from the product "
        "(what's on the shelf). Doses, forms, and combinations matter."
    )
    return notes
