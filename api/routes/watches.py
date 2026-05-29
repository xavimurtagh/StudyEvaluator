"""Watchlist endpoints.

Supports two ownership models in parallel:
  - Anonymous: keyed by ``client_id`` (UUID stored in localStorage).
  - Authenticated: keyed by ``user_id`` from a signed session cookie.

When a request carries both, the authenticated user wins. The frontend
keeps sending its client_id so anon watches remain reachable until login.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import select

from api.auth import CurrentUser, current_user_optional
from api.db import Product, User, Watch, session

router = APIRouter()


class WatchCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=120)
    client_id: Optional[str] = Field(default=None, min_length=4, max_length=64)


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


def _grade_for(p: Product | None) -> str:
    if p is None:
        return "insufficient"
    try:
        return json.loads(p.verdict_json).get("overall_grade", "insufficient")
    except (ValueError, AttributeError):
        return "insufficient"


def _owner_filter(stmt, user: CurrentUser | None, client_id: str | None):
    if user is not None:
        return stmt.where(Watch.user_id == user.id)
    if client_id:
        return stmt.where(Watch.client_id == client_id).where(Watch.user_id.is_(None))  # type: ignore[union-attr]
    raise HTTPException(status_code=401, detail="Sign in or provide a client_id.")


def _owns(w: Watch, user: CurrentUser | None, client_id: str | None) -> bool:
    if user is not None:
        return w.user_id == user.id
    if client_id:
        return w.client_id == client_id and w.user_id is None
    return False


@router.get("/watches", response_model=list[WatchView])
def list_watches(
    client_id: Optional[str] = Query(default=None),
    user: CurrentUser | None = Depends(current_user_optional),
) -> list[WatchView]:
    with session() as s:
        stmt = _owner_filter(select(Watch), user, client_id).order_by(
            Watch.created_at.desc()
        )
        watches = s.exec(stmt).all()
        return [_to_view(w, _grade_for(s.get(Product, w.slug))) for w in watches]


@router.post("/watches", response_model=WatchView)
def create_watch(
    body: WatchCreate,
    user: CurrentUser | None = Depends(current_user_optional),
) -> WatchView:
    if user is None and not body.client_id:
        raise HTTPException(status_code=401, detail="Sign in or include a client_id.")
    with session() as s:
        stmt = select(Watch).where(Watch.slug == body.slug)
        if user is not None:
            stmt = stmt.where(Watch.user_id == user.id)
        else:
            stmt = stmt.where(Watch.client_id == body.client_id).where(
                Watch.user_id.is_(None)  # type: ignore[union-attr]
            )
        existing = s.exec(stmt).first()
        if existing:
            return _to_view(existing, _grade_for(s.get(Product, existing.slug)))

        product = s.get(Product, body.slug)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail="That product hasn't been analyzed yet -- run a search first.",
            )
        w = Watch(
            client_id=body.client_id if user is None else None,
            user_id=user.id if user is not None else None,
            slug=body.slug,
            name=product.name,
            last_study_count=product.study_count,
            last_checked_at=datetime.utcnow(),
        )
        s.add(w)
        s.commit()
        s.refresh(w)
        return _to_view(w, _grade_for(product))


@router.delete("/watches/{watch_id}")
def delete_watch(
    watch_id: int,
    client_id: Optional[str] = Query(default=None),
    user: CurrentUser | None = Depends(current_user_optional),
) -> dict[str, bool]:
    with session() as s:
        w = s.get(Watch, watch_id)
        if w is None or not _owns(w, user, client_id):
            raise HTTPException(status_code=404, detail="Watch not found")
        s.delete(w)
        s.commit()
    return {"ok": True}


@router.post("/watches/{watch_id}/seen", response_model=WatchView)
def mark_seen(
    watch_id: int,
    client_id: Optional[str] = Query(default=None),
    user: CurrentUser | None = Depends(current_user_optional),
) -> WatchView:
    with session() as s:
        w = s.get(Watch, watch_id)
        if w is None or not _owns(w, user, client_id):
            raise HTTPException(status_code=404, detail="Watch not found")
        product = s.get(Product, w.slug)
        if product is not None:
            w.last_study_count = product.study_count
        w.has_new = False
        w.new_since_seen = 0
        s.add(w)
        s.commit()
        s.refresh(w)
        return _to_view(w, _grade_for(product))
