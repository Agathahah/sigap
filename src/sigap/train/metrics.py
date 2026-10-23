"""Phase 5 · Evaluation metrics that match how a fraud team operates.

Accuracy is useless at ~1% fraud (predict "never fraud" = 99% accurate). SIGAP reports:
  - TPR at a fixed FPR (the BAF paper protocol: recall at 5% FPR)
  - the confusion counts at the chosen threshold (alerts per day is what the ops team feels)
  - calibration (a score of 0.2 should mean ~20% of such applications are fraud; phase 6 needs it)
"""

from __future__ import annotations

import numpy as np


def threshold_at_fpr(y: np.ndarray, p: np.ndarray, target_fpr: float = 0.05) -> float:
    """Phase 5 · TODO(Agatha): the score threshold whose FPR on (y, p) is about target_fpr.

    Use only the scores of negatives (y == 0): threshold = their (1 - target_fpr) quantile.
    Flag rule everywhere in SIGAP: flagged = p >= threshold.
    Compute it on VALIDATION and reuse it unchanged on test (never re-fit on test).
    Test: tests/test_p5_metrics.py::test_threshold_at_fpr
    """
    raise NotImplementedError("TODO(Agatha) phase 5: sigap.train.metrics.threshold_at_fpr")


def confusion_at(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float]:
    """Phase 5 · TODO(Agatha): counts and rates when flagged = p >= threshold.

    Return keys: tp, fp, tn, fn (ints), tpr, fpr, precision, alert_rate (floats; 0.0 when dividing by zero).
    Test: tests/test_p5_metrics.py::test_confusion_at
    """
    raise NotImplementedError("TODO(Agatha) phase 5: sigap.train.metrics.confusion_at")


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Phase 5 · TODO(Agatha): ECE with equal-width bins on [0, 1].

    For each bin b with n_b rows: |mean(p in b) - mean(y in b)|. ECE = sum(n_b / n * gap_b).
    Bin edges: np.linspace(0, 1, n_bins + 1); a score of exactly 1.0 belongs to the last bin.
    Empty bins contribute 0.
    Test: tests/test_p5_metrics.py::test_ece_perfect_and_bad
    """
    raise NotImplementedError("TODO(Agatha) phase 5: sigap.train.metrics.expected_calibration_error")
