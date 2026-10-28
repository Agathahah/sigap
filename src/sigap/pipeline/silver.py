"""Silver (PySpark): clean, typed, one row per application.

- Sentinels (-1 or negative values meaning "no data") become NULL plus a `<column>_missing` flag.
- Duplicates on application_id keep the latest `_ingested_at`.
- Labels stay in their own table with `available_month`. They are joined to applications only where a job is
  allowed to know them (training, monitoring), never at scoring time.

Run:  make silver
"""

from __future__ import annotations

import re

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from sigap import config


def clean_sentinels(df: DataFrame, sentinels: dict[str, str]) -> DataFrame:
    """Sentinel -> NULL, keeping a `<column>_missing` flag (0/1).

    Rules: "eq_-1" (value == -1) or "lt_0" (value < 0). The flag is written before the value is cleared, so the
    information is kept; a real NULL is not a sentinel and gets flag 0.
    """
    out = df
    for col, rule in sentinels.items():
        if col not in out.columns:
            continue
        if rule == "eq_-1":
            is_missing = F.col(col) == -1
        elif rule == "lt_0":
            is_missing = F.col(col) < 0
        else:
            raise ValueError(f"unknown sentinel rule {rule!r} for {col}")
        is_missing = F.coalesce(is_missing, F.lit(False))
        out = out.withColumn(f"{col}_missing", is_missing.cast("int"))
        out = out.withColumn(col, F.when(is_missing, F.lit(None)).otherwise(F.col(col)))
    return out


def dedupe_latest(df: DataFrame, key: str, order_col: str = "_ingested_at") -> DataFrame:
    """One row per key: the row with the latest `order_col`."""
    w = Window.partitionBy(key).orderBy(F.col(order_col).desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")


def main() -> None:
    from sigap.quality.contract import load_contract
    from sigap.spark import get_spark

    slug = config.VARIANT.lower().replace(" ", "_")
    spark = get_spark("sigap-silver")
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    contract = load_contract(config.CONFIGS / "data_contract.yaml")
    sentinels = contract["sentinels"]

    bronze_apps = spark.read.parquet(str(config.BRONZE / slug / "applications"))
    apps = dedupe_latest(clean_sentinels(bronze_apps, sentinels), config.ID).drop("_source_file")
    apps.write.mode("overwrite").partitionBy("month").parquet(str(config.SILVER / slug / "applications"))

    labels = dedupe_latest(spark.read.parquet(str(config.BRONZE / slug / "labels")), config.ID)
    labels.drop("_source_file").write.mode("overwrite").parquet(str(config.SILVER / slug / "labels"))

    silver = spark.read.parquet(str(config.SILVER / slug / "applications"))
    flags = [F.round(100 * F.avg(f"{c}_missing"), 2).alias(c) for c in sentinels]
    summary = silver.groupBy("month").agg(F.count("*").alias("rows"), *flags).orderBy("month").toPandas()
    print(f"silver applications: {int(summary['rows'].sum()):,} rows. Share missing (%) per sentinel column:")
    short = summary.rename(columns=lambda c: re.sub(r"_months_count|_amount|_in_minutes|_distinct_emails_8w", "", c))
    print(short.to_string(index=False))
    n_labels = spark.read.parquet(str(config.SILVER / slug / "labels")).count()
    print(f"silver labels: {n_labels:,} -> {config.SILVER / slug}")
    spark.stop()


if __name__ == "__main__":
    main()
