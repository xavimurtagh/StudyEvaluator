"""SQLite + SQLModel persistence.

One row per analyzed product holds the full JSON verdict. We keep raw study
features too so re-scoring with a new model version doesn't require re-fetching
from PubMed.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.engine import URL
from sqlmodel import Field, SQLModel, Session, create_engine

log = logging.getLogger(__name__)

# Anchor the default DB path to the repo root (parent of the `api/` package)
# so the file lands in the same place regardless of which directory the
# server was launched from. Override with STUDYEVAL_DB_URL if you want.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _REPO_ROOT / "studyeval.db"

_env_url = os.environ.get("STUDYEVAL_DB_URL")
if _env_url:
    DB_URL: str | URL = _env_url
    _db_file: Path | None = (
        Path(_env_url.removeprefix("sqlite:///"))
        if _env_url.startswith("sqlite:///")
        and not _env_url.startswith("sqlite:///:memory:")
        else None
    )
else:
    # Build the URL via SQLAlchemy's URL helper rather than f-stringing a
    # path into "sqlite:///{...}". On Windows the f-string form produces
    # "sqlite:///C:/foo/bar.db" which trips up some SQLAlchemy / sqlite3
    # combinations (sqlite3.OperationalError: unable to open database file
    # at INSERT time, even when startup-time access works). URL.create()
    # passes the path through as a structured field and lets the dialect
    # hand it straight to sqlite3.connect().
    DB_URL = URL.create("sqlite", database=str(_DEFAULT_DB_PATH))
    _db_file = _DEFAULT_DB_PATH

# If we're using a file-backed SQLite DB, make sure the parent directory
# exists and we can actually write to it. Doing this at import time means
# any path / permission issue surfaces with a clear error before requests
# start failing.
if _db_file is not None:
    _db_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(_db_file)) as _probe:
            _probe.execute(
                "CREATE TABLE IF NOT EXISTS _studyeval_probe (id INTEGER PRIMARY KEY)"
            )
            _probe.execute("INSERT INTO _studyeval_probe (id) VALUES (1)")
            _probe.execute("DELETE FROM _studyeval_probe WHERE id = 1")
            _probe.commit()
    except sqlite3.OperationalError as exc:
        raise RuntimeError(
            f"Cannot open SQLite DB at {_db_file}: {exc}.\n"
            f"Possible causes on Windows:\n"
            f"  - The folder is synced by OneDrive/Dropbox and a lock is held.\n"
            f"  - Antivirus is blocking sqlite3 from opening the file.\n"
            f"  - The path contains characters Python's sqlite3 doesn't like.\n"
            f"Workaround: set STUDYEVAL_DB_URL to a local path, e.g.\n"
            f'  set STUDYEVAL_DB_URL=sqlite:///%USERPROFILE%\\studyeval.db'
        ) from exc
    log.info("StudyEvaluator DB ready at %s", _db_file)
    print(f"[studyevaluator] DB file: {_db_file}", flush=True)

_url_for_engine = DB_URL
_url_str_for_check = (
    DB_URL.render_as_string(hide_password=False) if isinstance(DB_URL, URL) else DB_URL
)

engine = create_engine(
    _url_for_engine,
    echo=False,
    connect_args=(
        {"check_same_thread": False}
        if _url_str_for_check.startswith("sqlite")
        else {}
    ),
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
