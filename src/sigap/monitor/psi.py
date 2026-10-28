"""Phase 8 · Drift: Population Stability Index.

PSI compares a feature (or the score) this month with the reference period (training months).
Rule of thumb: < 0.10 stable, 0.10-0.25 watch, > 0.25 significant shift (investigate before trusting the model).
Drift can be measured the day data arrives; performance (TPR/FPR) only when labels arrive two months later.
That gap is why both are monitored.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10, eps: float = 1e-4) -> float:
    """PSI with quantile bins taken from `expected`; NaN dropped, shares clipped at eps. Never negative."""
    e = np.asarray(expected, dtype=float)
    a = np.asarray(actual, dtype=float)
    e, a = e[~np.isnan(e)], a[~np.isnan(a)]
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    e_share = np.clip(np.histogram(e, edges)[0] / len(e), eps, None)
    a_share = np.clip(np.histogram(a, edges)[0] / len(a), eps, None)
    return float(np.sum((a_share - e_share) * np.log(a_share / e_share)))


def drift_report(
    reference: pd.DataFrame, current: pd.DataFrame, columns: list[str], watch: float = 0.10, alert: float = 0.25
) -> pd.DataFrame:
    """Phase 8 · TODO(Agatha): PSI per column with a status.

    Return columns: feature, psi, status ("stable" if psi < watch, "watch" if < alert, else "alert"),
    sorted by psi descending.
    Test: tests/test_p8_monitor.py::test_drift_report_status
    """
    raise NotImplementedError("TODO(Agatha) phase 8: sigap.monitor.psi.drift_report")
