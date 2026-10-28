"""Drift: Population Stability Index.

PSI compares a feature (or the score) this month with the reference period (training months).
Rule of thumb: < 0.10 stable, 0.10-0.25 watch, > 0.25 significant shift (investigate before trusting the model).
Drift can be measured the day data arrives; performance (TPR/FPR) only when labels arrive two months later.
That gap is why both are monitored.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10, eps: float = 1e-4) -> float:
    """Population Stability Index of `actual` against `expected`; NaN dropped, shares clipped at eps.

    Continuous values: quantile bins taken from `expected` (outer edges open). Discrete values (at most `bins`
    distinct whole numbers in `expected`, e.g. 0/1 flags and one-hot columns): one bin per value, because quantile edges
    of a 0/1 column collapse into a single bin and would always report 0. Never negative.
    """
    e = np.asarray(expected, dtype=float)
    a = np.asarray(actual, dtype=float)
    e, a = e[~np.isnan(e)], a[~np.isnan(a)]
    if len(e) == 0 or len(a) == 0:
        return float("nan")
    values = np.unique(e)
    if len(values) <= bins and np.all(np.mod(values, 1) == 0):  # flags, one-hot columns, small counts
        cats = np.union1d(values, np.unique(a))
        e_share = np.array([(e == v).mean() for v in cats])
        a_share = np.array([(a == v).mean() for v in cats])
    else:
        edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
        edges[0], edges[-1] = -np.inf, np.inf
        e_share = np.histogram(e, edges)[0] / len(e)
        a_share = np.histogram(a, edges)[0] / len(a)
    e_share, a_share = np.clip(e_share, eps, None), np.clip(a_share, eps, None)
    return float(np.sum((a_share - e_share) * np.log(a_share / e_share)))


def drift_report(
    reference: pd.DataFrame, current: pd.DataFrame, columns: list[str], watch: float = 0.10, alert: float = 0.25
) -> pd.DataFrame:
    """PSI per column with a status: stable (< watch), watch (< alert), alert. Sorted by PSI, highest first."""
    rows = []
    for col in columns:
        value = psi(reference[col].to_numpy(), current[col].to_numpy())
        status = "stable" if value < watch else ("watch" if value < alert else "alert")
        rows.append({"feature": col, "psi": value, "status": status})
    return pd.DataFrame(rows, columns=["feature", "psi", "status"]).sort_values(
        "psi", ascending=False, ignore_index=True
    )
