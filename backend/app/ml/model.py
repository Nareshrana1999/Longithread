"""A small, dependency-free logistic regression + calibration metrics.

Why hand-rolled and transparent: a medical decision-support model must be
auditable - feature names, weights, and per-patient contributions are exposed,
not hidden behind an opaque estimator. This is a baseline, not a deployed
clinical model; real deployment needs proper cohort data, regularization,
external validation, and regulatory review.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


@dataclass
class LogisticRegression:
    features: list[str]
    means: list[float] = field(default_factory=list)
    stds: list[float] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    bias: float = 0.0

    def _standardize(self, x: list[float]) -> list[float]:
        return [(v - m) / (s or 1.0) for v, m, s in zip(x, self.means, self.stds)]

    def decision(self, x: list[float]) -> float:
        xs = self._standardize(x)
        return sum(w * v for w, v in zip(self.weights, xs)) + self.bias

    def predict_proba(self, x: list[float]) -> float:
        return sigmoid(self.decision(x))

    def fit(self, X: list[list[float]], y: list[int], steps: int = 4000,
            lr: float = 0.08, l2: float = 0.01) -> "LogisticRegression":
        n = len(X)
        d = len(X[0])
        self.means = [sum(row[j] for row in X) / n for j in range(d)]
        self.stds = []
        for j in range(d):
            var = sum((row[j] - self.means[j]) ** 2 for row in X) / n
            self.stds.append(math.sqrt(var) or 1.0)
        Xs = [self._standardize(row) for row in X]
        self.weights = [0.0] * d
        self.bias = 0.0
        for _ in range(steps):
            grad_w = [0.0] * d
            grad_b = 0.0
            for xi, yi in zip(Xs, y):
                err = sigmoid(sum(w * v for w, v in zip(self.weights, xi)) + self.bias) - yi
                grad_b += err
                for j in range(d):
                    grad_w[j] += err * xi[j]
            self.bias -= lr * grad_b / n
            for j in range(d):
                self.weights[j] -= lr * (grad_w[j] / n + l2 * self.weights[j])
        return self


def roc_auc(y_true: list[int], scores: list[float]) -> float:
    """Rank-based AUC (Mann-Whitney). Handles ties via average ranks."""
    pos = [s for y, s in zip(y_true, scores) if y == 1]
    neg = [s for y, s in zip(y_true, scores) if y == 0]
    if not pos or not neg:
        return float("nan")
    pairs = [(s, y) for s, y in zip(scores, y_true)]
    pairs.sort(key=lambda t: t[0])
    # assign average ranks
    ranks = [0.0] * len(pairs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    sum_pos_ranks = sum(r for r, (s, y) in zip(ranks, pairs) if y == 1)
    n_pos, n_neg = len(pos), len(neg)
    return (sum_pos_ranks - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def brier(y_true: list[int], probs: list[float]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, y_true)) / len(y_true)


def classification_report(y_true: list[int], probs: list[float], thresh: float = 0.5) -> dict:
    tp = fp = fn = tn = 0
    for y, p in zip(y_true, probs):
        pred = 1 if p >= thresh else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
        elif pred == 0 and y == 1:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(y_true)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3), "accuracy": round(accuracy, 3)}
