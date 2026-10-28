"""Fairness: predictive equality across age groups (the BAF paper protocol).

Predictive equality = equal false-positive rates between groups. A false positive here is a genuine customer whose
account opening is blocked or delayed, so an unequal FPR means one age group carries more of the friction.
Groups: customer_age >= 50 vs < 50 (as in Jesus et al., 2022).
Reference: Hardt, Price & Srebro (2016), Equality of Opportunity in Supervised Learning.
"""

from __future__ import annotations

import math

import numpy as np


def age_group(age: np.ndarray) -> np.ndarray:
    """The two groups used throughout SIGAP."""
    return np.where(np.asarray(age) >= 50, ">=50", "<50")


def fpr_by_group(y: np.ndarray, p: np.ndarray, threshold: float, group: np.ndarray) -> dict[str, float]:
    """FPR per group at a threshold (flagged = p >= threshold); NaN for a group without negatives."""
    y, flag, group = np.asarray(y), np.asarray(p, dtype=float) >= threshold, np.asarray(group)
    out = {}
    for g in np.unique(group):
        neg = (group == g) & (y == 0)
        out[str(g)] = float(flag[neg].mean()) if neg.any() else float("nan")
    return out


def fpr_ratio(fprs: dict[str, float]) -> float:
    """min(FPR) / max(FPR) over groups, ignoring NaN. 1.0 = equal; NaN when a group has no value."""
    values = list(fprs.values())
    if len(values) < 2 or any(math.isnan(v) for v in values):
        return float("nan")
    hi = max(values)
    return 1.0 if hi == 0 else min(values) / hi
