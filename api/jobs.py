"""In-process job runner.

For a real deployment swap this for Celery/Arq behind the same interface --
the route handlers only call `submit` and `get_status`. Keeping it in-process
means the demo runs with one command and no broker.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Awaitable, Callable

from sqlmodel import select

from api.db import Job, session
from api.pipeline.run import analyze_product
from api.schemas import JobStatus

logger = logging.getLogger(__name__)


_RUNNING: set[str] = set()
# Per-job notify events. SSE subscribers wait on these so they wake up
# immediately when the worker calls _update, instead of polling the DB.
_EVENTS: dict[str, asyncio.Event] = {}


def _notify(job_id: str) -> None:
    ev = _EVENTS.get(job_id)
    if ev is not None:
        ev.set()


def event_for(job_id: str) -> asyncio.Event:
    """Return (creating if needed) the per-job asyncio.Event used to wake
    SSE subscribers when the job's state changes."""
    ev = _EVENTS.get(job_id)
    if ev is None:
        ev = asyncio.Event()
        _EVENTS[job_id] = ev
    return ev


def submit(query: str, max_studies: int, claims: list[str] | None) -> str:
    """Submit a job. Must be called from inside the running event loop
    (i.e. from an async route handler) so asyncio.create_task can attach
    to it."""
    job_id = uuid.uuid4().hex
    with session() as s:
        s.add(Job(job_id=job_id, query=query, state="queued"))
        s.commit()
    asyncio.create_task(_run_job(job_id, query, max_studies, claims))
    return job_id


def get_status(job_id: str) -> JobStatus | None:
    with session() as s:
        job = s.get(Job, job_id)
        if job is None:
            return None
        return JobStatus(
            job_id=job.job_id,
            state=job.state,  # type: ignore[arg-type]
            progress=job.progress,
            message=job.message,
            slug=job.slug,
        )


async def _run_job(
    job_id: str, query: str, max_studies: int, claims: list[str] | None
) -> None:
    if job_id in _RUNNING:
        return
    _RUNNING.add(job_id)

    def on_progress(pct: float, msg: str) -> None:
        _update(job_id, state="running", progress=pct, message=msg)

    try:
        _update(job_id, state="running", progress=0.0, message="Starting...")
        verdict = await analyze_product(
            query,
            max_studies=max_studies,
            claims_override=claims,
            on_progress=on_progress,
        )
        _save_verdict(verdict)
        _update(
            job_id,
            state="complete",
            progress=1.0,
            message="Done.",
            slug=verdict.slug,
        )
    except Exception as exc:  # noqa: BLE001 - we want the message in the UI
        logger.exception("Job %s failed", job_id)
        _update(job_id, state="error", message=str(exc))
    finally:
        _RUNNING.discard(job_id)
        # Final notify so any waiting SSE clients see the terminal state.
        _notify(job_id)


def _update(
    job_id: str,
    *,
    state: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    slug: str | None = None,
) -> None:
    with session() as s:
        job = s.get(Job, job_id)
        if job is None:
            return
        if state is not None:
            job.state = state
        if progress is not None:
            job.progress = progress
        if message is not None:
            job.message = message
        if slug is not None:
            job.slug = slug
        job.updated_at = datetime.utcnow()
        s.add(job)
        s.commit()
    _notify(job_id)


def _save_verdict(verdict) -> None:
    from api.db import Product

    with session() as s:
        existing = s.get(Product, verdict.slug)
        payload = verdict.model_dump_json()
        if existing:
            existing.verdict_json = payload
            existing.last_analyzed = datetime.utcnow()
            existing.pipeline_version = verdict.pipeline_version
            existing.study_count = len(verdict.studies)
            s.add(existing)
        else:
            s.add(
                Product(
                    slug=verdict.slug,
                    name=verdict.product,
                    pipeline_version=verdict.pipeline_version,
                    verdict_json=payload,
                    study_count=len(verdict.studies),
                )
            )
        s.commit()


def find_recent_product(slug: str) -> str | None:
    from api.db import Product

    with session() as s:
        stmt = select(Product).where(Product.slug == slug)
        p = s.exec(stmt).first()
        return p.verdict_json if p else None


def list_recent_products(limit: int = 12) -> list[dict]:
    """Return summary rows for the most-recently-analyzed products.

    We pull the overall_grade from the cached verdict JSON rather than
    storing it as a separate column -- avoids schema churn and the verdict
    is the source of truth anyway.
    """
    import json

    from api.db import Product

    out: list[dict] = []
    with session() as s:
        stmt = select(Product).order_by(Product.last_analyzed.desc()).limit(limit)
        for p in s.exec(stmt).all():
            try:
                grade = json.loads(p.verdict_json).get("overall_grade", "insufficient")
            except (ValueError, AttributeError):
                grade = "insufficient"
            out.append(
                {
                    "slug": p.slug,
                    "name": p.name,
                    "overall_grade": grade,
                    "study_count": p.study_count,
                    "last_analyzed": p.last_analyzed.isoformat(),
                }
            )
    return out
