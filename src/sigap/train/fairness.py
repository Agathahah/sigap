"""Phase 5 · Fairness: predictive equality across age groups (BAF paper protocol).

Predictive equality = equal false positive rates between groups. A false positive here is a genuine
customer whose account opening is blocked or delayed, so an unequal FPR means one age group carries
more of the friction. Groups: customer_age >= 50 vs < 50 (as in Jesus et al., 2022).
Reference: Hardt, Price & Srebro (2016), Equality of Opportunity in Supervised Learning.
"""

from __future__ import annotations

import numpy as np


def fpr_by_group(y: np.ndarray, p: np.ndarray, threshold: float, group: np.ndarray) -> dict[str, float]:
    """Phase 5 · TODO(Agatha): FPR per group at a threshold (flagged = p >= threshold).

    Keys are str(group value). A group with no negatives gets float("nan").
    Test: tests/test_p5_metrics.py::test_fpr_by_group
    """
    raise NotImplementedError("TODO(Agatha) phase 5: sigap.train.fairness.fpr_by_group")


def fpr_ratio(fprs: dict[str, float]) -> float:
    """Phase 5 · TODO(Agatha): min(FPR) / max(FPR), ignoring NaN. 1.0 = equal.

    If max is 0 (nobody flagged), return 1.0. If fewer than 2 valid groups, return float("nan").
    Test: tests/test_p5_metrics.py::test_fpr_ratio
    """
    raise NotImplementedError("TODO(Agatha) phase 5: sigap.train.fairness.fpr_ratio")
