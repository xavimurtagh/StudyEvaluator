"""Quick smoke test against the live PubMed API.

Run with: .venv/bin/python scripts/smoke_test.py "creatine"
"""

from __future__ import annotations

import asyncio
import sys

from api.pipeline.run import analyze_product


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "ashwagandha"
    print(f"Analyzing: {query}")

    def progress(pct, msg):
        print(f"  [{pct:>4.0%}] {msg}")

    verdict = await analyze_product(query, max_studies=15, on_progress=progress)
    print()
    print(f"Product:       {verdict.product}")
    print(f"Overall grade: {verdict.overall_grade.value}")
    print(f"Summary:       {verdict.summary}")
    print(f"Studies:       {len(verdict.studies)}")
    print()
    print("Claims:")
    for c in verdict.claims:
        print(f"  - [{c.grade.value:>13}] {c.claim}")
        print(f"      {c.plain_language}")
    print()
    print("Red flags:")
    for f in verdict.red_flags:
        print(f"  - [{f.severity}] {f.kind}: {f.message}")
    print()
    print("Top 5 studies by quality:")
    for s in sorted(verdict.studies, key=lambda x: x.quality.score, reverse=True)[:5]:
        print(
            f"  - {s.quality.score:.2f}  {s.extracted.design.value:>18}  "
            f"n={s.extracted.sample_size}  {s.extracted.title[:80]}"
        )


if __name__ == "__main__":
    asyncio.run(main())
