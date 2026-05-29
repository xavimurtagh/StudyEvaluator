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


class Watch(SQLModel, table=True):
    """A user-watched product.

    Two ways to own a watch:
      - ``client_id`` (anonymous, scoped to one browser/device) -- the original
        flow, kept so logged-out users still work.
      - ``user_id`` (signed in via email magic link) -- watches survive across
        browsers and can be migrated from anon on first login.

    Exactly one of the two is non-null at any moment.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[str] = Field(default=None, index=True)
    user_id: Optional[int] = Field(default=None, index=True, foreign_key="user.id")
    slug: str = Field(index=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_checked_at: datetime = Field(default_factory=datetime.utcnow)
    last_study_count: int = 0
    has_new: bool = False
    new_since_seen: int = 0


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MagicLinkToken(SQLModel, table=True):
    """One-time-use signed token used to verify ownership of an email address.

    The token itself is also signed (``itsdangerous``) so it can't be forged
    without our secret, but we still write it to the DB so we can mark it
    used and prevent replay.
    """

    token: str = Field(primary_key=True)
    email: str = Field(index=True)
    client_id: Optional[str] = None  # to migrate anon watches on first login
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    used_at: Optional[datetime] = None


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # SQLModel.create_all doesn't add new columns to existing tables, so any
    # pre-auth Watch rows are missing user_id. Idempotent ALTER for SQLite.
    if _db_file is not None:
        with sqlite3.connect(str(_db_file)) as conn:
            info = list(conn.execute("PRAGMA table_info(watch)"))
            cols = {row[1] for row in info}
            if "user_id" not in cols:
                conn.execute("ALTER TABLE watch ADD COLUMN user_id INTEGER")
                conn.commit()
            # SQLite can't DROP NOT NULL in-place, so if the existing
            # client_id column is still NOT NULL we rebuild the table.
            # `notnull` is column index 3 in PRAGMA table_info.
            client_id_notnull = any(
                row[1] == "client_id" and row[3] == 1 for row in info
            )
            if client_id_notnull:
                conn.executescript(
                    """
                    CREATE TABLE watch_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id VARCHAR,
                        user_id INTEGER,
                        slug VARCHAR NOT NULL,
                        name VARCHAR NOT NULL,
                        created_at DATETIME NOT NULL,
                        last_checked_at DATETIME NOT NULL,
                        last_study_count INTEGER NOT NULL DEFAULT 0,
                        has_new BOOLEAN NOT NULL DEFAULT 0,
                        new_since_seen INTEGER NOT NULL DEFAULT 0
                    );
                    INSERT INTO watch_new
                        (id, client_id, user_id, slug, name, created_at,
                         last_checked_at, last_study_count, has_new, new_since_seen)
                    SELECT id, client_id, NULL, slug, name, created_at,
                           last_checked_at, last_study_count, has_new, new_since_seen
                    FROM watch;
                    DROP TABLE watch;
                    ALTER TABLE watch_new RENAME TO watch;
                    CREATE INDEX ix_watch_client_id ON watch (client_id);
                    CREATE INDEX ix_watch_user_id ON watch (user_id);
                    CREATE INDEX ix_watch_slug ON watch (slug);
                    """
                )
                conn.commit()


def session() -> Session:
    return Session(engine)
