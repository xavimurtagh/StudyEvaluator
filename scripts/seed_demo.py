"""Seed the local DB with a demo verdict using the fixture corpus.

Use this when the live PubMed API isn't reachable (sandboxed env, offline
demo). Produces a verdict for 'collagen peptides' you can browse in the UI.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.db import init_db
from api.jobs import _save_verdict
from api.pipeline.run import analyze_product
from api.tests.fixtures import make_corpus


async def main():
    init_db()
    verdict = await analyze_product(
        "collagen peptides",
        claims_override=[
            "improves skin elasticity",
            "improves skin hydration",
            "improves hair growth",
            "improves joint pain",
            "improves wound healing",
        ],
        records_override=make_corpus(),
    )
    _save_verdict(verdict)
    print(f"Seeded: /api/products/{verdict.slug}")
    print(f"Overall grade: {verdict.overall_grade.value}")
    for c in verdict.claims:
        print(f"  - [{c.grade.value:>13}] {c.claim}")


if __name__ == "__main__":
    asyncio.run(main())
