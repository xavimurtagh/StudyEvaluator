"""Magic-link auth endpoints.

Flow:
  1. POST /api/auth/request-link {email, client_id?} -> we email a link
  2. User clicks link -> GET /api/auth/verify?token=... -> sets cookie,
     redirects to the frontend root.
  3. POST /api/auth/logout -> clears cookie.
  4. GET /api/me -> { id, email } if logged in.

Anonymous client_id is captured at request time so we can migrate any
watches that browser made before signing in.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select

from api.auth import (
    COOKIE_SECURE,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    consume_magic_token,
    current_user_optional,
    issue_magic_token,
    issue_session_cookie,
)
from api.auth import CurrentUser
from api.db import User, Watch, session
from api.email import send_magic_link

router = APIRouter()

FRONTEND_URL = os.environ.get("STUDYEVAL_FRONTEND_URL", "http://localhost:3000")


class RequestLinkBody(BaseModel):
    email: EmailStr
    client_id: Optional[str] = Field(default=None, max_length=64)


class MeResponse(BaseModel):
    id: int
    email: str


@router.post("/auth/request-link")
async def request_link(body: RequestLinkBody, request: Request) -> dict[str, bool]:
    signed = issue_magic_token(body.email.lower(), body.client_id)
    # The verify endpoint lives on the API, not the frontend, because it
    # needs to set a cookie before redirecting. The browser follows the 302
    # and lands on the frontend with the cookie attached.
    base = str(request.base_url).rstrip("/")
    link = f"{base}/api/auth/verify?token={signed}"
    await send_magic_link(body.email, link)
    return {"ok": True}


@router.get("/auth/verify")
def verify(token: str) -> Response:
    user, anon_client_id = consume_magic_token(token)
    _migrate_anon_watches(user, anon_client_id)
    cookie = issue_session_cookie(user)
    resp = RedirectResponse(url=FRONTEND_URL, status_code=302)
    resp.set_cookie(
        SESSION_COOKIE,
        cookie,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )
    return resp


@router.post("/auth/logout")
def logout() -> Response:
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/me", response_model=MeResponse)
def me(user: Optional[CurrentUser] = Depends(current_user_optional)) -> MeResponse:
    if user is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not signed in.")
    return MeResponse(id=user.id, email=user.email)


def _migrate_anon_watches(user: CurrentUser, client_id: Optional[str]) -> None:
    """Re-key any anon watches owned by this browser to the user.

    Skip rows the user already has (same slug) to avoid dupes -- the older
    user-owned row wins.
    """
    if not client_id:
        return
    with session() as s:
        anon = s.exec(
            select(Watch)
            .where(Watch.client_id == client_id)
            .where(Watch.user_id.is_(None))  # type: ignore[union-attr]
        ).all()
        if not anon:
            return
        existing_slugs = {
            w.slug
            for w in s.exec(select(Watch).where(Watch.user_id == user.id)).all()
        }
        for w in anon:
            if w.slug in existing_slugs:
                s.delete(w)
                continue
            # Old DBs may have NOT NULL on client_id, so insert a fresh row
            # for the user and drop the anon one rather than UPDATE-ing
            # the existing watch to null its client_id.
            replacement = Watch(
                user_id=user.id,
                client_id=None,
                slug=w.slug,
                name=w.name,
                created_at=w.created_at,
                last_checked_at=w.last_checked_at,
                last_study_count=w.last_study_count,
                has_new=w.has_new,
                new_since_seen=w.new_since_seen,
            )
            s.delete(w)
            s.add(replacement)
        s.commit()
