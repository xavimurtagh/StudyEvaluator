"""Watchlist endpoints.

Anonymous, browser-scoped watchlists keyed by a `client_id` the frontend
generates and stores in localStorage. Each watched slug records the
study count at the time it was last checked; a background poller (see
api/watcher.py) periodically re-analyzes the product and flips `has_new`
when fresh studies show up.
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from api.db import Product, Watch, session

router = APIRouter()


class WatchCreate(BaseModel):
    client_id: str = Field(min_length=4, max_length=64)
    slug: str = Field(min_length=1, max_length=120)


class WatchView(BaseModel):
    id: int
    slug: str
    name: str
    created_at: str
    last_checked_at: str
    last_study_count: int
    has_new: bool
    new_since_seen: int
    overall_grade: str


def _to_view(w: Watch, overall_grade: str) -> WatchView:
    return WatchView(
        id=w.id or 0,
        slug=w.slug,
        name=w.name,
        created_at=w.created_at.isoformat(),
        last_checked_at=w.last_checked_at.isoformat(),
        last_study_count=w.last_study_count,
        has_new=w.has_new,
        new_since_seen=w.new_since_seen,
        overall_grade=overall_grade,
    )


@router.get("/watches", response_model=list[WatchView])
def list_watches(client_id: str) -> list[WatchView]:
    with session() as s:
        watches = s.exec(
            select(Watch)
            .where(Watch.client_id == client_id)
            .order_by(Watch.created_at.desc())
        ).all()
        out: list[WatchView] = []
        for w in watches:
            p = s.get(Product, w.slug)
            grade = "insufficient"
            if p:
                try:
                    grade = json.loads(p.verdict_json).get("overall_grade", grade)
                except (ValueError, AttributeError):
                    pass
            out.append(_to_view(w, grade))
        return out


@router.post("/watches", response_model=WatchView)
def create_watch(body: WatchCreate) -> WatchView:
    with session() as s:
        existing = s.exec(
            select(Watch)
            .where(Watch.client_id == body.client_id)
            .where(Watch.slug == body.slug)
        ).first()
        if existing:
            # Idempotent: return the existing watch instead of erroring.
            p = s.get(Product, existing.slug)
            grade = "insufficient"
            if p:
                try:
                    grade = json.loads(p.verdict_json).get("overall_grade", grade)
                except (ValueError, AttributeError):
                    pass
            return _to_view(existing, grade)

        product = s.get(Product, body.slug)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail="That product hasn't been analyzed yet -- run a search first.",
            )
        w = Watch(
            client_id=body.client_id,
            slug=body.slug,
            name=product.name,
            last_study_count=product.study_count,
            last_checked_at=datetime.utcnow(),
        )
        s.add(w)
        s.commit()
        s.refresh(w)
        try:
            grade = json.loads(product.verdict_json).get("overall_grade", "insufficient")
        except (ValueError, AttributeError):
            grade = "insufficient"
        return _to_view(w, grade)


@router.delete("/watches/{watch_id}")
def delete_watch(watch_id: int, client_id: str) -> dict[str, bool]:
    with session() as s:
        w = s.get(Watch, watch_id)
        if w is None or w.client_id != client_id:
            raise HTTPException(status_code=404, detail="Watch not found")
        s.delete(w)
        s.commit()
    return {"ok": True}


@router.post("/watches/{watch_id}/seen", response_model=WatchView)
def mark_seen(watch_id: int, client_id: str) -> WatchView:
    """Clear the 'new evidence' badge. Called when the user opens the
    verdict page for a watched product."""
    with session() as s:
        w = s.get(Watch, watch_id)
        if w is None or w.client_id != client_id:
            raise HTTPException(status_code=404, detail="Watch not found")
        product = s.get(Product, w.slug)
        if product is not None:
            w.last_study_count = product.study_count
        w.has_new = False
        w.new_since_seen = 0
        s.add(w)
        s.commit()
        s.refresh(w)
        grade = "insufficient"
        if product:
            try:
                grade = json.loads(product.verdict_json).get(
                    "overall_grade", grade
                )
            except (ValueError, AttributeError):
                pass
        return _to_view(w, grade)
