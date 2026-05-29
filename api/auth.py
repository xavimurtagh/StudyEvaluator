"""Email magic-link auth.

Passwordless: users prove ownership of an email address by clicking a link
we send them. On click we mint a signed session cookie (``itsdangerous``)
so the rest of the app can identify them on every subsequent request
without server-side session storage.

Tokens are double-protected: the URL token is itself signed (no DB lookup
needed to detect tampering) AND tracked in MagicLinkToken so we can
single-use it and prevent replay.

Cookie security:
  - httpOnly so JS can't read it (XSS-resistant)
  - samesite=lax so it's sent on top-level GETs (the magic link click) but
    not on cross-site POSTs (CSRF-resistant)
  - secure when running behind HTTPS (``STUDYEVAL_COOKIE_SECURE=1``)
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from dataclasses import dataclass

from fastapi import Cookie, Depends, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import select

from api.db import MagicLinkToken, User, session


@dataclass
class CurrentUser:
    """Detached view of a user, safe to use outside a DB session."""

    id: int
    email: str

SESSION_COOKIE = "studyeval_session"
LINK_TTL_SECONDS = 15 * 60
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
_SECRET = os.environ.get("STUDYEVAL_SECRET", "dev-insecure-secret-change-me")
_signer = URLSafeTimedSerializer(_SECRET, salt="studyeval.session.v1")
_link_signer = URLSafeTimedSerializer(_SECRET, salt="studyeval.magiclink.v1")
COOKIE_SECURE = os.environ.get("STUDYEVAL_COOKIE_SECURE") == "1"


def issue_magic_token(email: str, client_id: Optional[str]) -> str:
    """Mint and persist a single-use magic-link token. Returns the token."""
    raw = secrets.token_urlsafe(32)
    signed = _link_signer.dumps({"email": email, "t": raw})
    with session() as s:
        s.add(
            MagicLinkToken(
                token=raw,
                email=email,
                client_id=client_id,
                expires_at=datetime.utcnow() + timedelta(seconds=LINK_TTL_SECONDS),
            )
        )
        s.commit()
    return signed


def consume_magic_token(signed: str) -> tuple[CurrentUser, Optional[str]]:
    """Verify a magic link, ensure single-use, return the user (+ client_id).

    Raises HTTPException(400) for any failure mode so we don't reveal which
    bucket the token fell into.
    """
    try:
        payload = _link_signer.loads(signed, max_age=LINK_TTL_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="This link has expired.")
    except BadSignature:
        raise HTTPException(status_code=400, detail="This link isn't valid.")

    email = payload["email"]
    raw = payload["t"]
    with session() as s:
        row = s.get(MagicLinkToken, raw)
        if row is None or row.used_at is not None:
            raise HTTPException(status_code=400, detail="This link has already been used.")
        if row.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="This link has expired.")

        # Find-or-create the user.
        user = s.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(email=email)
            s.add(user)
            s.commit()
            s.refresh(user)

        row.used_at = datetime.utcnow()
        s.add(row)
        s.commit()
        s.refresh(user)
        cu = CurrentUser(id=int(user.id), email=user.email)
        client_id = row.client_id
        return cu, client_id


def issue_session_cookie(user: CurrentUser | User) -> str:
    return _signer.dumps({"uid": user.id, "email": user.email})


def read_session_cookie(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        payload = _signer.loads(value, max_age=SESSION_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    uid = payload.get("uid")
    return int(uid) if uid is not None else None


def current_user_optional(
    studyeval_session: Optional[str] = Cookie(default=None),
) -> Optional[CurrentUser]:
    uid = read_session_cookie(studyeval_session)
    if uid is None:
        return None
    with session() as s:
        u = s.get(User, uid)
        if u is None:
            return None
        return CurrentUser(id=int(u.id), email=u.email)


def require_current_user(
    user: Optional[CurrentUser] = Depends(current_user_optional),
) -> CurrentUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user
