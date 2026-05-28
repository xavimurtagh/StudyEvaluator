from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from slugify import slugify

from api import jobs
from api.pipeline.parse_claim import parse_claim
from api.schemas import JobStatus, ProductVerdict, SearchRequest

router = APIRouter()


class CheckClaimRequest(BaseModel):
    text: str = Field(min_length=2, max_length=300)


class CheckClaimResponse(BaseModel):
    subject: str
    predicate: str
    raw: str
    job: JobStatus


@router.post("/search", response_model=JobStatus)
async def search(req: SearchRequest) -> JobStatus:
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


class ProductListEntry(BaseModel):
    slug: str
    name: str
    overall_grade: str
    study_count: int
    last_analyzed: str


@router.get("/products", response_model=list[ProductListEntry])
def list_products(limit: int = 12) -> list[ProductListEntry]:
    """Recently analyzed products. Used by the home page for discovery."""
    return jobs.list_recent_products(limit=limit)


@router.post("/check-claim", response_model=CheckClaimResponse)
async def check_claim(req: CheckClaimRequest) -> CheckClaimResponse:
    """Parse a free-text claim, then run the pipeline focused on that predicate.

    This is the misinformation-counter flow: paste a TikTok/IG claim like
    "Collagen regrows hair" and get an evidence-graded answer back."""
    parsed = parse_claim(req.text)
    if parsed is None or not parsed.subject:
        raise HTTPException(
            status_code=400,
            detail="Could not identify a product or ingredient in the claim.",
        )
    slug = slugify(parsed.subject)
    # If we already have a verdict that includes this predicate, return cached.
    cached = jobs.find_recent_product(slug)
    if cached and parsed.predicate:
        verdict = json.loads(cached)
        existing_claims = {c["claim"].strip().lower() for c in verdict.get("claims", [])}
        if parsed.predicate.strip().lower() in existing_claims:
            return CheckClaimResponse(
                subject=parsed.subject,
                predicate=parsed.predicate,
                raw=parsed.raw,
                job=JobStatus(
                    job_id="cached",
                    state="complete",
                    progress=1.0,
                    message="Loaded from cache.",
                    slug=slug,
                ),
            )
    # Otherwise run a focused analysis.
    claims = [parsed.predicate] if parsed.predicate else None
    job_id = jobs.submit(parsed.subject, max_studies=25, claims=claims)
    return CheckClaimResponse(
        subject=parsed.subject,
        predicate=parsed.predicate,
        raw=parsed.raw,
        job=JobStatus(job_id=job_id, state="queued", progress=0.0, slug=slug),
    )
