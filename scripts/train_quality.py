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
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

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
    rng = random.Random(SEED)
    rubric = RubricQualityScorer()
    X: list[np.ndarray] = []
    y: list[int] = []
    for band in ("high", "mid", "low"):
        for _ in range(N_PER_BAND):
            s = _rand_study(rng, band)
            X.append(featurize(s))
            # Binary target: rubric >= 0.6 is "high quality." Using the rubric
            # as ground truth means the ML model learns its priors; the value
            # add is interaction handling, not relabelling.
            y.append(1 if rubric.score(s).score >= 0.6 else 0)
    return np.vstack(X), np.array(y, dtype=np.int8)


def main() -> int:
    print(f"Building dataset (seed={SEED}, {N_PER_BAND}/band)...")
    X, y = build_dataset()
    pos = int(y.sum())
    print(f"  shape={X.shape}  positives={pos}  negatives={len(y) - pos}")

    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        random_state=SEED,
    )

    print("5-fold CV (AUC)...")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    aucs = cross_val_score(model, X, y, cv=skf, scoring="roc_auc")
    print(f"  AUC mean={aucs.mean():.3f} std={aucs.std():.3f} folds={aucs.round(3)}")

    print("Fitting on full dataset...")
    model.fit(X, y)
    train_auc = roc_auc_score(y, model.predict_proba(X)[:, 1])
    print(f"  Train AUC={train_auc:.3f}")
    print(classification_report(y, model.predict(X), digits=3))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Saved -> {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
