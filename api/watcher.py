"""Background watch poller.

Periodically re-runs the analysis pipeline for each currently-watched
product, compares the new study count to what was last seen, and flips
`Watch.has_new=True` if fresh evidence has shown up.

The interval is configurable via STUDYEVAL_WATCH_INTERVAL_SECONDS
(default 1 hour). For local demos it's reasonable to set this low so the
behavior is observable.

This runs in-process. For a real deployment, swap it for a Celery beat
schedule or a cron-driven external worker.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from sqlmodel import select

from api.db import Watch, session
from api.jobs import _save_verdict
from api.pipeline.run import analyze_product

log = logging.getLogger(__name__)

DEFAULT_INTERVAL = int(os.environ.get("STUDYEVAL_WATCH_INTERVAL_SECONDS", "3600"))
# Don't re-analyze the same slug more often than this even if many users
# are watching it. The Product table acts as the shared cache.
MIN_REANALYZE_GAP = int(os.environ.get("STUDYEVAL_WATCH_MIN_GAP", "1800"))

_task: asyncio.Task | None = None
_stop = asyncio.Event()


async def _loop() -> None:
    log.info("Watch poller started (interval=%ss)", DEFAULT_INTERVAL)
    # Stagger the first run so it doesn't pile onto app startup.
    try:
        await asyncio.wait_for(_stop.wait(), timeout=10)
        return
    except asyncio.TimeoutError:
        pass

    while not _stop.is_set():
        try:
            await _run_once()
        except Exception:
            log.exception("Watch poller iteration failed")
        try:
            await asyncio.wait_for(_stop.wait(), timeout=DEFAULT_INTERVAL)
        except asyncio.TimeoutError:
            continue


async def _run_once() -> None:
    """One sweep of all watched slugs."""
    slugs = _slugs_to_check()
    if not slugs:
        return
    log.info("Watch poller: %d unique slugs to check", len(slugs))
    for slug in slugs:
        try:
            await _check_slug(slug)
        except Exception:
            log.exception("Watch poller: failed to check %s", slug)


def _slugs_to_check() -> list[str]:
    with session() as s:
        rows = s.exec(select(Watch.slug).distinct()).all()
        return [r for r in rows]


async def _check_slug(slug: str) -> None:
    # Resolve the product name from the most-recent verdict.
    from api.db import Product

    with session() as s:
        product = s.get(Product, slug)
        if product is None:
            return
        age = (datetime.utcnow() - product.last_analyzed).total_seconds()
        if age < MIN_REANALYZE_GAP:
            return
        name = product.name
        previous_count = product.study_count

    log.info("Re-analyzing %s (previous study_count=%d)", slug, previous_count)
    verdict = await analyze_product(name, max_studies=25)
    _save_verdict(verdict)

    new_count = len(verdict.studies)
    delta = new_count - previous_count
    if delta <= 0:
        return

    # Flip has_new for every watch on this slug.
    with session() as s:
        watches = s.exec(select(Watch).where(Watch.slug == slug)).all()
        for w in watches:
            w.has_new = True
            w.new_since_seen += delta
            w.last_checked_at = datetime.utcnow()
            s.add(w)
        s.commit()
    log.info("Watch poller: %s gained %d new studies, %d watchers notified",
             slug, delta, len(watches))


def start() -> None:
    """Called from FastAPI startup. Idempotent."""
    global _task
    if _task is not None and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(_loop(), name="studyeval-watcher")


async def stop() -> None:
    """Called from FastAPI shutdown."""
    _stop.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
