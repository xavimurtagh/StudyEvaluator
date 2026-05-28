"""PubMed ingestion via the public E-utilities API.

No API key is required for low-volume use. The endpoints used:
  - esearch.fcgi -> list of PMIDs matching a query
  - efetch.fcgi  -> XML records (title, abstract, journal, authors, MeSH)

We keep this module thin: it returns raw record dicts. Parsing into our
ExtractedStudy schema lives in extract.py so the two concerns stay separable
and the network layer can be mocked in tests.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Iterable
from xml.etree import ElementTree as ET

import httpx

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "StudyEvaluator/0.1 (research; contact@studyevaluator.local)"


@dataclass
class RawRecord:
    pmid: str
    title: str
    abstract: str
    journal: str | None
    year: int | None
    authors: list[str]
    doi: str | None
    mesh_terms: list[str]
    publication_types: list[str]
    has_coi_statement: bool
    coi_text: str | None
    funding_text: str | None


def build_query(product: str) -> str:
    """Construct a PubMed query string biased toward clinical evidence.

    We don't restrict by publication type here -- we want to see weak evidence
    too, so we can score it as weak rather than pretend it doesn't exist.
    Lay terms are mapped to biomedical equivalents via ``synonyms.expand_query``.
    """
    from api.pipeline.synonyms import expand_query

    return expand_query(product).pubmed_query


async def search_pmids(
    client: httpx.AsyncClient, query: str, max_results: int
) -> list[str]:
    r = await client.get(
        f"{EUTILS}/esearch.fcgi",
        params={
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        },
        timeout=20.0,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])


async def fetch_records(client: httpx.AsyncClient, pmids: list[str]) -> list[RawRecord]:
    if not pmids:
        return []
    r = await client.get(
        f"{EUTILS}/efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
        timeout=30.0,
    )
    r.raise_for_status()
    return parse_pubmed_xml(r.text)


def parse_pubmed_xml(xml_text: str) -> list[RawRecord]:
    out: list[RawRecord] = []
    root = ET.fromstring(xml_text)
    for art in root.findall(".//PubmedArticle"):
        pmid_el = art.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None and pmid_el.text else ""
        if not pmid:
            continue

        title = _text(art.find(".//ArticleTitle")) or "(no title)"
        abstract = _collect_abstract(art)
        journal = _text(art.find(".//Journal/Title"))
        year = _parse_year(art)
        authors = _collect_authors(art)
        doi = _find_doi(art)
        mesh = [
            _text(d.find("DescriptorName")) or ""
            for d in art.findall(".//MeshHeading")
        ]
        mesh = [m for m in mesh if m]
        pubtypes = [
            _text(p) or "" for p in art.findall(".//PublicationTypeList/PublicationType")
        ]
        pubtypes = [p for p in pubtypes if p]

        coi_el = art.find(".//CoiStatement")
        coi_text = _text(coi_el) if coi_el is not None else None
        has_coi = coi_el is not None

        funding_text = " ".join(
            (_text(g.find("Agency")) or "")
            for g in art.findall(".//GrantList/Grant")
        ).strip() or None

        out.append(
            RawRecord(
                pmid=pmid,
                title=title,
                abstract=abstract,
                journal=journal,
                year=year,
                authors=authors,
                doi=doi,
                mesh_terms=mesh,
                publication_types=pubtypes,
                has_coi_statement=has_coi,
                coi_text=coi_text,
                funding_text=funding_text,
            )
        )
    return out


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    return "".join(el.itertext()).strip() or None


def _collect_abstract(art: ET.Element) -> str:
    parts: list[str] = []
    for at in art.findall(".//Abstract/AbstractText"):
        label = at.get("Label")
        body = "".join(at.itertext()).strip()
        if not body:
            continue
        parts.append(f"{label}: {body}" if label else body)
    return "\n".join(parts)


def _parse_year(art: ET.Element) -> int | None:
    for path in (".//PubDate/Year", ".//ArticleDate/Year", ".//PubMedPubDate/Year"):
        el = art.find(path)
        if el is not None and el.text and el.text.isdigit():
            return int(el.text)
    md = art.find(".//PubDate/MedlineDate")
    if md is not None and md.text:
        m = re.search(r"(19|20)\d{2}", md.text)
        if m:
            return int(m.group(0))
    return None


def _collect_authors(art: ET.Element) -> list[str]:
    names: list[str] = []
    for au in art.findall(".//AuthorList/Author"):
        last = _text(au.find("LastName"))
        init = _text(au.find("Initials"))
        coll = _text(au.find("CollectiveName"))
        if coll:
            names.append(coll)
        elif last:
            names.append(f"{last} {init}".strip() if init else last)
    return names


def _find_doi(art: ET.Element) -> str | None:
    for el in art.findall(".//ArticleId"):
        if el.get("IdType", "").lower() == "doi" and el.text:
            return el.text.strip()
    return None


async def ingest(
    product: str,
    max_studies: int = 25,
    client: httpx.AsyncClient | None = None,
) -> list[RawRecord]:
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    try:
        pmids = await search_pmids(client, build_query(product), max_studies)
        # E-utilities is happiest with batches of <=200; we're well under.
        return await fetch_records(client, pmids)
    finally:
        if own_client:
            await client.aclose()


def ingest_sync(product: str, max_studies: int = 25) -> list[RawRecord]:
    return asyncio.run(ingest(product, max_studies))


def chunk(seq: Iterable, n: int):
    buf = []
    for x in seq:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf
