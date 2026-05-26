from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from slugify import slugify

from api import jobs
from api.schemas import JobStatus, ProductVerdict, SearchRequest

router = APIRouter()


@router.post("/search", response_model=JobStatus)
def search(req: SearchRequest) -> JobStatus:
    # If we already have a recent verdict, skip the job entirely.
    slug = slugify(req.query)
    cached = jobs.find_recent_product(slug)
    if cached and req.claims is None:
        return JobStatus(
            job_id="cached",
            state="complete",
            progress=1.0,
            message="Loaded from cache.",
            slug=slug,
        )
    job_id = jobs.submit(req.query, req.max_studies, req.claims)
    return JobStatus(job_id=job_id, state="queued", progress=0.0, slug=slug)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    status = jobs.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@router.get("/products/{slug}", response_model=ProductVerdict)
def get_product(slug: str) -> ProductVerdict:
    cached = jobs.find_recent_product(slug)
    if cached is None:
        raise HTTPException(status_code=404, detail="Product not analyzed yet")
    return ProductVerdict.model_validate(json.loads(cached))
