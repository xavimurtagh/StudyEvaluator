"""Train the v1 study-quality classifier.

We bootstrap the model from rubric-labeled synthetic data. The rubric is
auditable and lives in api/pipeline/quality.py; using its outputs as targets
means the ML scorer learns the same priors but can pick up cross-feature
interactions a hand-tuned weighted sum can't.

Outputs ./models/quality_v1.joblib, which MLQualityScorer auto-loads.

Run:  python scripts/train_quality.py
Eval: python scripts/eval_quality.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.pipeline.quality import (  # noqa: E402
    MODEL_DIR,
    MODEL_PATH,
    RubricQualityScorer,
    featurize,
)
from api.schemas import ExtractedStudy, StudyDesign  # noqa: E402

SEED = 13
N_PER_BAND = 250


def _rand_study(rng: random.Random, band: str) -> ExtractedStudy:
    """Sample a synthetic study with feature distributions matching a band."""

    if band == "high":
        design = rng.choice(
            [
                StudyDesign.META_ANALYSIS,
                StudyDesign.SYSTEMATIC_REVIEW,
                StudyDesign.RCT,
                StudyDesign.RCT,
            ]
        )
        sample_size = rng.randint(200, 8000)
        randomized = rng.random() < 0.95
        blinded = rng.random() < 0.85
        placebo = rng.random() < 0.7
        prereg = rng.random() < 0.5
        industry = rng.random() < 0.2
        coi = rng.random() < 0.25
        duration = rng.uniform(8, 104)
        year = rng.randint(2012, 2025)
        human = True
        retracted = False
        abstract_len = rng.randint(800, 2000)
    elif band == "mid":
        design = rng.choice(
            [
                StudyDesign.COHORT,
                StudyDesign.CASE_CONTROL,
                StudyDesign.CROSS_SECTIONAL,
                StudyDesign.RCT,
            ]
        )
        sample_size = rng.randint(50, 500)
        randomized = rng.random() < 0.4
        blinded = rng.random() < 0.3
        placebo = rng.random() < 0.25
        prereg = rng.random() < 0.15
        industry = rng.random() < 0.35
        coi = rng.random() < 0.35
        duration = rng.uniform(2, 24)
        year = rng.randint(2005, 2023)
        human = True
        retracted = False
        abstract_len = rng.randint(400, 900)
    else:  # low
        design = rng.choice(
            [
                StudyDesign.CASE_SERIES,
                StudyDesign.ANIMAL,
                StudyDesign.IN_VITRO,
                StudyDesign.REVIEW,
                StudyDesign.UNKNOWN,
            ]
        )
        sample_size = rng.randint(5, 60) if rng.random() < 0.7 else None
        randomized = rng.random() < 0.05
        blinded = rng.random() < 0.05
        placebo = False
        prereg = False
        industry = rng.random() < 0.6
        coi = rng.random() < 0.5
        duration = rng.uniform(0.5, 6)
        year = rng.randint(1995, 2022)
        human = design not in (StudyDesign.ANIMAL, StudyDesign.IN_VITRO)
        retracted = rng.random() < 0.05
        abstract_len = rng.randint(150, 400)

    return ExtractedStudy(
        pmid=f"synthetic-{rng.randint(0, 10**9)}",
        title="(synthetic)",
        abstract="x" * abstract_len,
        year=year,
        design=design,
        sample_size=sample_size,
        duration_weeks=duration,
        randomized=randomized,
        blinded=blinded,
        placebo_controlled=placebo,
        preregistered=prereg,
        industry_funded=industry,
        conflict_of_interest=coi,
        human_subjects=human,
        retracted=retracted,
    )


def build_dataset() -> tuple[np.ndarray, np.ndarray]:
    """Synthetic studies labeled with the *continuous* rubric score.

    Previously we labeled binary (rubric>=0.6) which forced the classifier
    to output probabilities clustered near 0/1 -- in production that made
    every study look either 99% or 1%. Regressing on the rubric's actual
    0-1 score preserves nuance: a small under-blinded RCT lands in the
    middle instead of being binned as "high" or "low".
    """
    rng = random.Random(SEED)
    rubric = RubricQualityScorer()
    X: list[np.ndarray] = []
    y: list[float] = []
    for band in ("high", "mid", "low"):
        for _ in range(N_PER_BAND):
            s = _rand_study(rng, band)
            X.append(featurize(s))
            y.append(rubric.score(s).score)
    return np.vstack(X), np.array(y, dtype=np.float32)


def main() -> int:
    print(f"Building dataset (seed={SEED}, {N_PER_BAND}/band)...")
    X, y = build_dataset()
    print(f"  shape={X.shape}  mean={y.mean():.3f}  std={y.std():.3f}")

    model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.05,
        random_state=SEED,
    )

    print("5-fold CV (R^2 and MAE)...")
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    r2s = cross_val_score(model, X, y, cv=kf, scoring="r2")
    maes = -cross_val_score(model, X, y, cv=kf, scoring="neg_mean_absolute_error")
    print(f"  R^2 mean={r2s.mean():.3f} std={r2s.std():.3f}")
    print(f"  MAE mean={maes.mean():.3f} std={maes.std():.3f}")

    print("Fitting on full dataset...")
    model.fit(X, y)
    preds = np.clip(model.predict(X), 0.0, 1.0)
    print(f"  Train R^2={r2_score(y, preds):.3f}  MAE={mean_absolute_error(y, preds):.3f}")
    print(f"  Pred range [{preds.min():.2f}, {preds.max():.2f}]  mean={preds.mean():.2f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Saved -> {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
