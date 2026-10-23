"""Deterministic synthetic cohort for training the baseline risk model.

This is scaffolding to prove the pipeline learns and calibrates - NOT clinical
data and NOT a validated predictor. The labels come from a known generative
signal with noise, so the recovered metrics (AUC/Brier) measure the model's
learning, not real-world clinical performance. Replace with a properly consented,
clinically-adjudicated cohort before any study.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .features import PatientSignals
from .model import LogisticRegression, brier, classification_report, roc_auc, sigmoid

SEED = 20260101


def _true_logit(s: PatientSignals) -> float:
    return (-0.9
            + 0.60 * ((s.hba1c or 7.0) - 7.0)
            + 2.00 * s.hba1c_slope
            + 1.30 * (s.years_since_hba1c or 0.0)
            + 0.030 * ((s.sbp or 120) - 120)
            + 0.010 * ((s.dbp or 80) - 80)
            + 0.90 * ((s.creatinine or 1.0) - 1.0))


def _sample_signals(rng: random.Random) -> PatientSignals:
    return PatientSignals(
        hba1c=round(min(14.0, max(4.0, rng.gauss(7.6, 1.3))), 2),
        hba1c_slope=round(rng.gauss(0.04, 0.22), 3),
        years_since_hba1c=round(rng.uniform(0.0, 2.2), 3),
        sbp=round(min(200, max(90, rng.gauss(132, 16)))),
        dbp=round(min(120, max(50, rng.gauss(82, 10)))),
        creatinine=round(min(5.0, max(0.4, rng.gauss(1.15, 0.35))), 2),
    )


def _make_cohort(n: int, seed: int) -> tuple[list[list[float]], list[int]]:
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        s = _sample_signals(rng)
        p = sigmoid(_true_logit(s))
        label = 1 if rng.random() < p else 0
        X.append(s.to_vector())
        y.append(label)
    return X, y


def train_and_evaluate(n: int = 800, holdout: int = 300) -> tuple[LogisticRegression, dict]:
    Xall, yall = _make_cohort(n + holdout, SEED)
    # deterministic interleaved split
    trainX, trainY, testX, testY = [], [], [], []
    for i, (x, yy) in enumerate(zip(Xall, yall)):
        if i % 4 == 0:
            testX.append(x); testY.append(yy)
        else:
            trainX.append(x); trainY.append(yy)

    model = LogisticRegression(features=[
        "hba1c_pct", "hba1c_slope_pct_per_month", "years_since_hba1c",
        "sbp", "dbp", "creatinine_mgdl"]).fit(trainX, trainY)

    probs = [model.predict_proba(x) for x in testX]
    metrics = {
        "auc": round(roc_auc(testY, probs), 3),
        "brier": round(brier(testY, probs), 3),
        **classification_report(testY, probs),
    }
    return model, metrics
