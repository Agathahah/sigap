"""Phase 1 · Data acquisition: turn one Kaggle CSV into the feeds a real bank would receive.

A bank does not get "Base.csv". It gets applications every day, and fraud labels weeks later
(after chargebacks and investigations). This module simulates that, so the rest of SIGAP has to
deal with what production deals with: monthly drops and late labels.

Output (data/landing/):
    applications/month=00/part.csv ... month=07/part.csv   # NO label column
    labels/available_month=02/part.csv ...                # application_id, is_fraud, month, available_month

Run:  make data-land
Story for interview: "Labels arrive two months late, so at month 6 the newest label I can
train on is month 4. My features and my monitoring both respect that."
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sigap import config


def add_application_id(df: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Phase 1 · TODO(Agatha): add a deterministic `application_id` as the FIRST column.

    Format: f"{variant_slug}-{row_number:07d}", where variant_slug = variant.lower() with spaces
    replaced by "_" ("Variant I" -> "variant_i") and row_number is the 0-based position in the file.
    Deterministic = running the job twice gives the same ids (idempotent loads, safe re-runs).
    Do not modify the input DataFrame (return a copy).
    Test: tests/test_p1_acquisition.py::test_application_id_deterministic_and_unique
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.landing.add_application_id")


def make_label_feed(df: pd.DataFrame, lag_months: int = config.LABEL_LAG_MONTHS) -> pd.DataFrame:
    """Phase 1 · TODO(Agatha): build the late-arriving label feed.

    Input has columns application_id, month, fraud_bool. Return a DataFrame with exactly:
        application_id, is_fraud (int 0/1), month, available_month (= month + lag_months)
    Test: tests/test_p1_acquisition.py::test_label_feed_is_lagged
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.landing.make_label_feed")


def write_landing(df: pd.DataFrame, landing_dir: Path, lag_months: int = config.LABEL_LAG_MONTHS) -> dict[str, int]:
    """Phase 1 · TODO(Agatha): write monthly application drops and the label feed.

    `df` already has application_id. Write:
      landing_dir/applications/month=MM/part.csv   all columns EXCEPT fraud_bool, one folder per month
      landing_dir/labels/available_month=MM/part.csv  from make_label_feed(), one folder per available_month
    MM is zero-padded to 2 digits. Overwrite existing files (re-runs must not duplicate rows).
    Return {"applications": total rows written, "labels": total label rows written}.
    Test: tests/test_p1_acquisition.py::test_landing_has_no_label_leak
    """
    raise NotImplementedError("TODO(Agatha) phase 1: sigap.ingest.landing.write_landing")


def main() -> None:
    """CLI: read data/raw/<VARIANT>.csv, add ids, write landing. Provided."""
    src = config.RAW / f"{config.VARIANT}.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found. Run `make data-download` first.")
    df = add_application_id(pd.read_csv(src), config.VARIANT)
    out = config.LANDING / config.VARIANT.lower().replace(" ", "_")
    print(write_landing(df, out), "->", out)


if __name__ == "__main__":
    main()
