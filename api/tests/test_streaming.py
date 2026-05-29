"""SSE job-stream endpoint."""

from __future__ import annotations

import json
import os

os.environ.setdefault("STUDYEVAL_DISABLE_WATCHER", "1")

from fastapi.testclient import TestClient

from api import jobs as jobs_mod
from api.db import Job, init_db, session
from api.main import app


def test_stream_returns_404_for_unknown_job():
    init_db()
    client = TestClient(app)
    r = client.get("/api/jobs/no-such-job/stream")
    assert r.status_code == 404


def test_stream_emits_current_state_immediately_for_terminal_job():
    init_db()
    job_id = "stream-test-1"
    with session() as s:
        existing = s.get(Job, job_id)
        if existing:
            s.delete(existing)
            s.commit()
        s.add(
            Job(
                job_id=job_id,
                query="collagen",
                state="complete",
                progress=1.0,
                message="Done.",
                slug="collagen",
            )
        )
        s.commit()

    client = TestClient(app)
    with client.stream("GET", f"/api/jobs/{job_id}/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        chunks = []
        for line in r.iter_lines():
            chunks.append(line)
            if line.startswith("data:"):
                break
        data_line = next(c for c in chunks if c.startswith("data:"))
        payload = json.loads(data_line.removeprefix("data: ").strip())
        assert payload["state"] == "complete"
        assert payload["progress"] == 1.0


def test_notify_wakes_subscribers():
    """Calling _notify on a job_id should set the per-job asyncio.Event."""
    import asyncio

    async def go():
        ev = jobs_mod.event_for("notify-test")
        assert not ev.is_set()
        jobs_mod._notify("notify-test")
        assert ev.is_set()

    asyncio.run(go())
