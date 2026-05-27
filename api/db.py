"""SQLite + SQLModel persistence.

One row per analyzed product holds the full JSON verdict. We keep raw study
features too so re-scoring with a new model version doesn't require re-fetching
from PubMed.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Field, SQLModel, Session, create_engine

log = logging.getLogger(__name__)

# Anchor the default DB path to the repo root (parent of the `api/` package)
# so the file lands in the same place regardless of which directory the
# server was launched from. Override with STUDYEVAL_DB_URL if you want.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _REPO_ROOT / "studyeval.db"
DB_URL = os.environ.get("STUDYEVAL_DB_URL", f"sqlite:///{_DEFAULT_DB_PATH.as_posix()}")

# If we're using a file-backed SQLite DB, make sure the parent directory
# exists and is writable. Failing here gives a clear message instead of the
# opaque "unable to open database file" from sqlite later.
if DB_URL.startswith("sqlite:///") and not DB_URL.startswith("sqlite:///:memory:"):
    _db_file = Path(DB_URL.removeprefix("sqlite:///"))
    _db_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        _db_file.touch(exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot create SQLite DB at {_db_file}: {exc}. "
            f"Set STUDYEVAL_DB_URL to a writable location."
        ) from exc
    log.info("StudyEvaluator DB: %s", _db_file)
    # Also print so it shows up even when uvicorn is configured to filter
    # INFO logs. Helps users diagnose path issues on Windows.
    print(f"[studyevaluator] DB file: {_db_file}", flush=True)

engine = create_engine(
    DB_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)


class Product(SQLModel, table=True):
    slug: str = Field(primary_key=True)
    name: str
    last_analyzed: datetime = Field(default_factory=datetime.utcnow)
    pipeline_version: str
    verdict_json: str
    study_count: int = 0


class Job(SQLModel, table=True):
    job_id: str = Field(primary_key=True)
    query: str
    slug: Optional[str] = None
    state: str = "queued"
    progress: float = 0.0
    message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def session() -> Session:
    return Session(engine)
