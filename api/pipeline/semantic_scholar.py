"""Semantic Scholar ingestion adapter.

Semantic Scholar's Graph API is free for low-volume use and indexes a much
wider set of venues than PubMed alone (preprints, conference papers,
fields outside biomedicine). We use it as a *second* source: its results
are merged into the PubMed set, deduped by DOI then by normalized title.

The adapter returns RawRecord objects shaped like the PubMed adapter's
output so the rest of the pipeline doesn't need to know where a study
came from.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

import httpx

from api.pipeline.ingest import RawRecord

log = logging.getLogger(__name__)

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
USER_AGENT = "StudyEvaluator/0.1 (research; contact@studyevaluator.local)"

# Fields we care about. Restricting these keeps the response small and the
# request cheap per S2's quota system.
FIELDS = ",".join(
    [
        "externalIds",
        "title",
        "abstract",
        "year",
        "authors",
        "venue",
        "publicationTypes",
    ]
)


async def ingest_s2(
    product: str,
    max_studies: int = 25,
    client: httpx.AsyncClient | None = None,
) -> list[RawRecord]:
    """Search Semantic Scholar and adapt the results to RawRecord."""
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=20.0
        )
    try:
        r = await client.get(
            S2_SEARCH,
            params={"query": product, "limit": max_studies, "fields": FIELDS},
        )
        if r.status_code != 200:
            log.warning("Semantic Scholar returned %s for %r", r.status_code, product)
            return []
        data = r.json().get("data") or []
        return [rec for rec in (_to_raw_record(p) for p in data) if rec is not None]
    except httpx.HTTPError as exc:
        log.warning("Semantic Scholar ingest failed for %r: %s", product, exc)
        return []
    finally:
        if own_client:
            await client.aclose()


def _to_raw_record(p: dict) -> RawRecord | None:
    title = (p.get("title") or "").strip()
    if not title:
        return None
    ext = p.get("externalIds") or {}
    pmid = str(ext.get("PubMed") or "") or f"s2:{p.get('paperId', '')}"
    doi = ext.get("DOI") or None
    abstract = (p.get("abstract") or "").strip()
    year = p.get("year") if isinstance(p.get("year"), int) else None
    authors = [
        (a.get("name") or "").strip()
        for a in (p.get("authors") or [])
        if a.get("name")
    ]
    pubtypes: list[str] = []
    for pt in p.get("publicationTypes") or []:
        # S2 publication types are looser strings; pass through so our
        # design classifier can use them or fall back to abstract scanning.
        if isinstance(pt, str):
            pubtypes.append(_s2_pubtype_to_pubmed(pt))
    venue = (p.get("venue") or "").strip() or None
    return RawRecord(
        pmid=pmid,
        title=title,
        abstract=abstract,
        journal=venue,
        year=year,
        authors=authors,
        doi=doi,
        mesh_terms=[],
        publication_types=pubtypes,
        has_coi_statement=False,
        coi_text=None,
        funding_text=None,
    )


# Map S2's publication-type vocabulary to the PubMed names our classifier
# already understands. Anything we don't recognize is passed through
# verbatim and falls back to the abstract-pattern path.
_S2_TO_PUBMED = {
    "MetaAnalysis": "Meta-Analysis",
    "Meta-Analysis": "Meta-Analysis",
    "Review": "Review",
    "JournalArticle": "Journal Article",
    "CaseReport": "Case Reports",
    "ClinicalTrial": "Clinical Trial",
    "RandomizedControlledTrial": "Randomized Controlled Trial",
    "Editorial": "Editorial",
    "Letter": "Letter",
    "Conference": "Conference",
}


def _s2_pubtype_to_pubmed(s2: str) -> str:
    return _S2_TO_PUBMED.get(s2, s2)


# --- Dedup ------------------------------------------------------------------


def _normalize_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def dedupe_records(records: Iterable[RawRecord]) -> list[RawRecord]:
    """Dedupe across sources. Prefer entries with the richer abstract and
    PubMed-style metadata, since the downstream extractor relies on it.

    Match keys, in order: DOI (case-insensitive), then PMID, then a
    normalized title."""
    seen_doi: dict[str, RawRecord] = {}
    seen_pmid: dict[str, RawRecord] = {}
    seen_title: dict[str, RawRecord] = {}
    out: list[RawRecord] = []

    for rec in records:
        key_doi = (rec.doi or "").strip().lower() or None
        key_pmid = rec.pmid if not rec.pmid.startswith("s2:") else None
        key_title = _normalize_title(rec.title)

        existing = (
            (seen_doi.get(key_doi) if key_doi else None)
            or (seen_pmid.get(key_pmid) if key_pmid else None)
            or seen_title.get(key_title)
        )
        if existing is not None:
            # Keep the richer record.
            if _score_record(rec) > _score_record(existing):
                _replace_in(out, existing, rec)
                _index(seen_doi, key_doi, rec)
                _index(seen_pmid, key_pmid, rec)
                _index(seen_title, key_title, rec)
            continue

        out.append(rec)
        _index(seen_doi, key_doi, rec)
        _index(seen_pmid, key_pmid, rec)
        _index(seen_title, key_title, rec)
    return out


def _index(d: dict, key: str | None, rec: RawRecord) -> None:
    if key:
        d[key] = rec


def _replace_in(lst: list[RawRecord], old: RawRecord, new: RawRecord) -> None:
    for i, x in enumerate(lst):
        if x is old:
            lst[i] = new
            return


def _score_record(r: RawRecord) -> int:
    """Higher = richer. Prefer abstracts, MeSH terms, publication types."""
    s = 0
    if r.abstract:
        s += min(len(r.abstract), 2000) // 100
    s += len(r.mesh_terms)
    s += len(r.publication_types)
    if r.has_coi_statement:
        s += 2
    if r.funding_text:
        s += 1
    if not r.pmid.startswith("s2:"):
        # Real PubMed IDs beat synthetic Semantic Scholar IDs.
        s += 3
    return s
