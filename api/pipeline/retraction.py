"""CrossRef-based retraction cross-check.

PubMed flags many retractions via the "Retracted Publication" publication
type, but not all -- especially recent ones. CrossRef hosts the Retraction
Watch database openly and exposes it via the standard /works API: when a
DOI has been retracted, the record's `update-to` field contains an entry
with `type=retraction`.

This module hits CrossRef for a batch of DOIs and returns the subset that
are retracted. The check is best-effort: any network or parse error is
swallowed and treated as 'not retracted', since the PubMed pubtype already
catches the high-confidence cases.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import httpx

log = logging.getLogger(__name__)

CROSSREF = "https://api.crossref.org/works"
USER_AGENT = "StudyEvaluator/0.1 (mailto:contact@studyevaluator.local)"


async def find_retracted_dois(
    dois: Iterable[str], client: httpx.AsyncClient | None = None
) -> set[str]:
    """Return the subset of input DOIs that are flagged as retracted."""
    targets = [d for d in dois if d]
    if not targets:
        return set()

    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=15.0
        )

    out: set[str] = set()
    try:
        # CrossRef recommends batching but doesn't support multi-DOI in one
        # GET. We do parallel single-DOI requests with a small fan-out cap.
        sem = asyncio.Semaphore(5)

        async def check(doi: str) -> None:
            async with sem:
                if await _is_retracted(client, doi):
                    out.add(doi)

        await asyncio.gather(*(check(d) for d in targets), return_exceptions=True)
    finally:
        if own_client:
            await client.aclose()
    return out


async def _is_retracted(client: httpx.AsyncClient, doi: str) -> bool:
    try:
        r = await client.get(f"{CROSSREF}/{doi}")
        if r.status_code != 200:
            return False
        data = r.json().get("message", {})
        updates = data.get("update-to") or []
        for u in updates:
            if (u.get("type") or "").lower() == "retraction":
                return True
        # CrossRef also exposes a top-level "subtype" of "retraction" for
        # the retraction notice itself.
        if (data.get("subtype") or "").lower() == "retraction":
            return True
    except (httpx.HTTPError, ValueError) as exc:
        log.debug("CrossRef retraction check failed for %s: %s", doi, exc)
    return False
