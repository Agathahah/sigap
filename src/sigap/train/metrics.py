"""Evaluation metrics that match how a fraud team operates.

Accuracy is useless at ~1% fraud (predicting "never fraud" is 99% accurate). SIGAP reports:
  - TPR at a fixed FPR (the BAF paper protocol: recall at 5% FPR)
  - the confusion counts at the chosen threshold (alerts per day is what the operations team feels)
  - calibration (a score of 0.2 should mean about 20% of such applications are fraud; the cost policy needs it)

Flag rule everywhere in SIGAP: flagged = score >= threshold.
"""

from __future__ import annotations

import numpy as np


def threshold_at_fpr(y: np.ndarray, p: np.ndarray, target_fpr: float = 0.05) -> float:
    """Score threshold whose FPR on (y, p) is about `target_fpr`: the (1 - target_fpr) quantile of negatives.

    Fit it on validation and reuse it unchanged on test; re-fitting on test would hide drift.
    """
    y, p = np.asarray(y), np.asarray(p, dtype=float)
    return float(np.quantile(p[y == 0], 1 - target_fpr))


def _div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def confusion_at(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float]:
    """Counts and rates when flagged = p >= threshold."""
    y = np.asarray(y).astype(int)
    flag = np.asarray(p, dtype=float) >= threshold
    tp = int(np.sum(flag & (y == 1)))
    fp = int(np.sum(flag & (y == 0)))
    fn = int(np.sum(~flag & (y == 1)))
    tn = int(np.sum(~flag & (y == 0)))
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "tpr": _div(tp, tp + fn),
        "fpr": _div(fp, fp + tn),
        "precision": _div(tp, tp + fp),
        "alert_rate": _div(tp + fp, len(y)),
    }


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """ECE with equal-width bins on [0, 1]: sum over bins of (share of rows) x |mean score - fraud rate|."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    if len(p) == 0:
        return 0.0
    bins = np.minimum((p * n_bins).astype(int), n_bins - 1)  # a score of exactly 1.0 goes to the last bin
    ece = 0.0
    for b in range(n_bins):
        mask = bins == b
        if mask.any():
            ece += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return float(ece)
