"""Phase 3 · SILVER (PySpark): clean, typed, one row per application.

- Sentinels (BAF uses -1 or negative values for "no data") become NULL + `<col>_missing` flags.
- Deduplicate on application_id, keeping the latest `_ingested_at`.
- Labels are kept in their own table (silver/labels) with `available_month`. They are joined to
  applications only where a job is allowed to know them (training, monitoring), never in scoring.

Run:  make silver
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window  # noqa: F401
from pyspark.sql import functions as F  # noqa: F401


def clean_sentinels(df: DataFrame, sentinels: dict[str, str]) -> DataFrame:
    """Phase 3 · TODO(Agatha): sentinel -> NULL, plus a missing flag.

    sentinels: {"bank_months_count": "eq_-1", "intended_balcon_amount": "lt_0", ...}
      "eq_-1": value == -1 means missing
      "lt_0" : value < 0 means missing
    For every column: FIRST add `<col>_missing` (int 0/1), THEN replace the value with NULL.
    (The other order loses the information.) Columns not listed stay unchanged.
    Hint: F.when(cond, F.lit(None)).otherwise(F.col(c)).
    Why (interview): -1 months at the previous address is not "one month before zero". Linear models,
    descriptive stats, PSI and human analysts all misread it. And missingness itself is often a fraud signal.
    Test: tests/test_p3_spark.py::test_clean_sentinels (marker spark)
    """
    raise NotImplementedError("TODO(Agatha) phase 3: sigap.pipeline.silver.clean_sentinels")


def dedupe_latest(df: DataFrame, key: str, order_col: str = "_ingested_at") -> DataFrame:
    """Phase 3 · TODO(Agatha): keep one row per key, the one with the latest order_col.

    Hint: Window.partitionBy(key).orderBy(F.col(order_col).desc()) + F.row_number() == 1.
    Test: tests/test_p3_spark.py::test_dedupe_latest (marker spark)
    """
    raise NotImplementedError("TODO(Agatha) phase 3: sigap.pipeline.silver.dedupe_latest")


def main() -> None:
    """Phase 3 · TODO(Agatha): the silver job.

    Read bronze applications + labels -> clean_sentinels (sentinels from data_contract.yaml)
    -> dedupe_latest -> cast types -> write data/silver/<variant>/applications (partitioned by month)
    and data/silver/<variant>/labels. Print counts and the share of missing per sentinel column per month
    (you will reuse those numbers in docs/03_EDA_FINDINGS.md).
    """
    raise NotImplementedError("TODO(Agatha) phase 3: pipeline.silver.main")


if __name__ == "__main__":
    main()
