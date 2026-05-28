"""Evaluate the ML quality scorer against the rubric on the fixture corpus.

Reports per-design and overall agreement so we can see whether the ML
model is just parroting the rubric or actually disagreeing in instructive
ways.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.pipeline.extract import extract  # noqa: E402
from api.pipeline.quality import MLQualityScorer, RubricQualityScorer  # noqa: E402
from api.tests.fixtures import make_corpus  # noqa: E402


def main() -> int:
    rubric = RubricQualityScorer()
    ml = MLQualityScorer()
    if ml.model is None:
        print("No model artifact found. Run scripts/train_quality.py first.")
        return 1

    studies = [extract(r) for r in make_corpus()]

    by_design: dict[str, list[tuple[float, float]]] = defaultdict(list)
    print(f"{'design':<22} {'rubric':>8} {'ml':>8} {'delta':>8}  title")
    print("-" * 96)
    for s in studies:
        r = rubric.score(s).score
        m = ml.score(s).score
        by_design[s.design.value].append((r, m))
        title = (s.title or "")[:48]
        print(
            f"{s.design.value:<22} {r:>8.3f} {m:>8.3f} {m - r:>+8.3f}  {title}"
        )

    print()
    print("Per-design averages:")
    for design, pairs in by_design.items():
        rs = sum(p[0] for p in pairs) / len(pairs)
        ms = sum(p[1] for p in pairs) / len(pairs)
        print(f"  {design:<22} rubric={rs:.3f}  ml={ms:.3f}  n={len(pairs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
