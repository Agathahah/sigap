"""Phase 4 · Feature engineering (pandas on the gold/silver table: 1M rows per variant fits in memory).

Two engineered signals, both explainable to a fraud analyst:
  velocity_ratio        velocity_6h / velocity_4w: a burst of applications in the last 6 hours compared
                        with the 4-week normal (both are applications per hour, so the ratio is unit-free)
  prior_rate_<col>      fraud rate of the category (payment_type, device_os) using ONLY labels that
                        were already available at that month (label lag!), smoothed toward the global rate

Run:  make features   -> data/gold/<variant>/features.parquet
"""

from __future__ import annotations

import numpy as np  # noqa: F401
import pandas as pd

from sigap import config


def velocity_ratio(df: pd.DataFrame) -> pd.Series:
    """Phase 4 · TODO(Agatha): velocity_6h / velocity_4w.

    Where velocity_4w <= 0 or is null, return NaN (never inf). Name the Series "velocity_ratio".
    Test: tests/test_p4_features.py::test_velocity_ratio_no_inf
    """
    raise NotImplementedError("TODO(Agatha) phase 4: sigap.features.build.velocity_ratio")


def prior_rate(df: pd.DataFrame, col: str, lag_months: int = config.LABEL_LAG_MONTHS, m: float = 100.0) -> pd.Series:
    """Phase 4 · TODO(Agatha): point-in-time, smoothed fraud rate per category.

    df has columns: <col>, month, is_fraud (0/1).
    For a row in month t, use ONLY rows with month <= t - lag_months (their labels exist at month t):
        n_c   = number of those rows with the same category
        f_c   = number of frauds among them
        g     = fraud rate over ALL those rows (any category)
        rate  = (f_c + m * g) / (n_c + m)
    If no row satisfies month <= t - lag_months, the rate is NaN (we honestly know nothing yet).
    Return a float Series aligned to df.index, named f"prior_rate_{col}".
    Leakage check: changing is_fraud of any row in months > t - lag_months must not change rows of month t.
    Hint: aggregate to (category, month) first, then loop over the 8 months (cheap), then map back.
    Tests: tests/test_p4_features.py::test_prior_rate_*
    """
    raise NotImplementedError("TODO(Agatha) phase 4: sigap.features.build.prior_rate")


def one_hot(df: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    """Phase 4 · TODO(Agatha): one-hot encode with a FIXED category list (from the data contract).

    Columns named f"{col}__{value}" (int 0/1) for every value in categories[col], in that order,
    even if a value does not occur in df. Unknown values get all zeros.
    Why fixed: the API must produce the same columns for a single application as training did for 1M.
    Test: tests/test_p4_features.py::test_one_hot_fixed_columns
    """
    raise NotImplementedError("TODO(Agatha) phase 4: sigap.features.build.one_hot")


def build_features(df: pd.DataFrame, numeric: list[str], categories: dict[str, list[str]]) -> pd.DataFrame:
    """Phase 4 · TODO(Agatha): assemble the model matrix.

    Output columns, in this order:
      application_id, month, <numeric...>, <*_missing flags already in df>, one_hot(...),
      velocity_ratio, prior_rate_payment_type, prior_rate_device_os
    The label is NOT in the output (keep it in a separate Series when training).
    Test: tests/test_p4_features.py::test_build_features_contract
    """
    raise NotImplementedError("TODO(Agatha) phase 4: sigap.features.build.build_features")


def main() -> None:
    """Phase 4 · TODO(Agatha): read silver applications + labels, build features, write gold/features.parquet.

    Join labels on application_id. Remember: prior_rate uses labels by month with the lag rule;
    the label column itself is written to a separate file gold/labels.parquet.
    """
    raise NotImplementedError("TODO(Agatha) phase 4: features.build.main")


if __name__ == "__main__":
    main()
