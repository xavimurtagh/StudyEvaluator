"""End-to-end auth flow + watch migration."""

from __future__ import annotations

import os

os.environ.setdefault("STUDYEVAL_DISABLE_WATCHER", "1")
os.environ.setdefault("STUDYEVAL_SECRET", "test-secret")

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import select

from api.auth import issue_magic_token
from api.db import MagicLinkToken, Product, Watch, init_db, session
from api.main import app


def _prep_product(slug: str = "collagen", name: str = "Collagen") -> None:
    init_db()
    # Clean auth state so re-running tests in the same DB doesn't pick up
    # stale rows.
    from api.db import User as _U, Watch as _W

    with session() as s:
        for row in s.exec(select(MagicLinkToken)).all():
            s.delete(row)
        for row in s.exec(select(_U)).all():
            s.delete(row)
        for row in s.exec(select(_W)).all():
            s.delete(row)
        s.commit()
        if s.get(Product, slug) is None:
            s.add(
                Product(
                    slug=slug,
                    name=name,
                    pipeline_version="test",
                    verdict_json='{"overall_grade":"weak"}',
                    study_count=3,
                )
            )
            s.commit()


def test_magic_link_round_trip_logs_user_in():
    _prep_product()
    client = TestClient(app)

    token = issue_magic_token("alice@example.com", client_id=None)
    r = client.get(
        f"/api/auth/verify?token={token}", follow_redirects=False
    )
    assert r.status_code == 302
    assert "studyeval_session" in r.cookies or any(
        "studyeval_session" in v for v in r.headers.get_list("set-cookie")
    )

    # The TestClient persists cookies across requests, so /api/me should now
    # return the user.
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_magic_token_is_single_use():
    _prep_product()
    client = TestClient(app)
    token = issue_magic_token("bob@example.com", client_id=None)
    assert client.get(f"/api/auth/verify?token={token}", follow_redirects=False).status_code == 302
    # Second use of the same signed token must fail.
    r = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert r.status_code == 400


def test_login_migrates_anon_watches():
    _prep_product()
    anon = TestClient(app)
    anon.post(
        "/api/watches",
        json={"slug": "collagen", "client_id": "anon-client-xyz"},
    )

    # Before login: anon can list its watch
    r = anon.get("/api/watches", params={"client_id": "anon-client-xyz"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Log in capturing the same client_id
    token = issue_magic_token("carol@example.com", client_id="anon-client-xyz")
    auth = TestClient(app)
    assert auth.get(f"/api/auth/verify?token={token}", follow_redirects=False).status_code == 302

    # Authenticated list should now include the migrated watch
    r = auth.get("/api/watches")
    assert r.status_code == 200
    assert any(w["slug"] == "collagen" for w in r.json())

    # And the anon listing for that client_id should be empty
    r = anon.get("/api/watches", params={"client_id": "anon-client-xyz"})
    assert r.json() == []


def test_logout_clears_session():
    _prep_product()
    client = TestClient(app)
    token = issue_magic_token("dave@example.com", client_id=None)
    client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert client.get("/api/me").status_code == 200
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert client.get("/api/me").status_code == 401


def test_expired_token_is_rejected(monkeypatch):
    _prep_product()
    client = TestClient(app)
    token = issue_magic_token("eve@example.com", client_id=None)
    # Force the DB row to look expired.
    with session() as s:
        row = s.exec(
            select(MagicLinkToken).where(MagicLinkToken.email == "eve@example.com")
        ).first()
        assert row is not None
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        s.add(row)
        s.commit()
    r = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert r.status_code == 400
