# Quality model artifacts

`quality_v1.joblib` is a `GradientBoostingClassifier` trained over the
shared feature vector defined in `api/pipeline/quality.py`. It produces a
probability that a study is "high quality" (rubric score >= 0.6).

## Training

```
python scripts/train_quality.py
```

The bootstrap uses 750 synthetic `ExtractedStudy` samples drawn from three
quality bands (high / mid / low) with feature distributions that match real
papers in each band. The rubric (also in `api/pipeline/quality.py`) labels
each sample, and the model learns to reproduce that mapping. 5-fold
stratified AUC on the synthetic set is ~0.99; the model picks up
cross-feature interactions a flat weighted sum can't (e.g. small-n RCTs
without blinding shouldn't outscore well-powered meta-analyses).

## Evaluation

```
python scripts/eval_quality.py
```

Compares rubric vs ML scores on the hand-curated fixture corpus. Expected
behavior: RCTs and meta-analyses score high, animal and case-series score
low. The model can disagree with the rubric — that's the point — but
large rank inversions across the fixture corpus mean the next training
pass needs more diverse samples (especially edge-case meta-analyses with
sparse metadata).

## Future passes

- Add real labeled data: hand-graded papers from Retraction Watch (negatives)
  and Cochrane reviews (positives) instead of relying on synthetic.
- Replace the binary target with the continuous rubric score and use a
  regressor for finer-grained scoring.
- Per-design calibration so the same probability means the same thing
  whether the design is RCT or cohort.
