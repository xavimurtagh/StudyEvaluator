from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import watcher
from api.db import init_db
from api.routes.search import router as search_router
from api.routes.watches import router as watches_router

app = FastAPI(
    title="StudyEvaluator API",
    description=(
        "Evidence-graded verdicts on health and wellness products. "
        "Pulls studies from PubMed, extracts structured features, scores quality "
        "with an interpretable classifier, and aligns marketed claims to "
        "the actual findings."
    ),
    version="0.1.0",
)

origins = os.environ.get(
    "STUDYEVAL_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    if os.environ.get("STUDYEVAL_DISABLE_WATCHER") != "1":
        watcher.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await watcher.stop()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(search_router, prefix="/api")
app.include_router(watches_router, prefix="/api")
