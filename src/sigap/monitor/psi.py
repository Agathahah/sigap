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
    """Phase 8 · TODO(Agatha): PSI with quantile bins taken from `expected`.

    1. Drop NaN from both arrays.
    2. Edges = unique quantiles of expected at np.linspace(0, 1, bins + 1); set the first edge to -inf
       and the last to +inf so every value of `actual` falls in a bin.
    3. e, a = share of each array per bin; clip both to at least eps.
    4. PSI = sum((a - e) * ln(a / e)).
    Identical distributions give ~0; the result is never negative.
    Tests: tests/test_p8_monitor.py::test_psi_*
    """
    raise NotImplementedError("TODO(Agatha) phase 8: sigap.monitor.psi.psi")


def drift_report(
    reference: pd.DataFrame, current: pd.DataFrame, columns: list[str], watch: float = 0.10, alert: float = 0.25
) -> pd.DataFrame:
    """Phase 8 · TODO(Agatha): PSI per column with a status.

    Return columns: feature, psi, status ("stable" if psi < watch, "watch" if < alert, else "alert"),
    sorted by psi descending.
    Test: tests/test_p8_monitor.py::test_drift_report_status
    """
    raise NotImplementedError("TODO(Agatha) phase 8: sigap.monitor.psi.drift_report")
