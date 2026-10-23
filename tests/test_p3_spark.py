"""Phase 3 · Spark transforms (needs Java 17 + PySpark; marker spark)."""

import pytest

pytestmark = [pytest.mark.p3, pytest.mark.spark]


def test_clean_sentinels(spark):
    from sigap.pipeline.silver import clean_sentinels

    df = spark.createDataFrame(
        [(1, -1, -0.5, 7), (2, 12, 3.0, 8), (3, None, None, 9)],
        "id int, bank_months_count int, intended_balcon_amount double, other int",
    )
    out = clean_sentinels(df, {"bank_months_count": "eq_-1", "intended_balcon_amount": "lt_0"})
    rows = {r["id"]: r for r in out.collect()}
    assert rows[1]["bank_months_count"] is None and rows[1]["bank_months_count_missing"] == 1
    assert rows[1]["intended_balcon_amount"] is None and rows[1]["intended_balcon_amount_missing"] == 1
    assert rows[2]["bank_months_count"] == 12 and rows[2]["bank_months_count_missing"] == 0
    assert rows[3]["bank_months_count_missing"] == 0  # a real NULL is not a sentinel
    assert rows[1]["other"] == 7


def test_dedupe_latest(spark):
    from sigap.pipeline.silver import dedupe_latest

    df = spark.createDataFrame([("a", 1, "old"), ("a", 2, "new"), ("b", 1, "only")], "k string, t int, v string")
    out = {r["k"]: r["v"] for r in dedupe_latest(df, "k", "t").collect()}
    assert out == {"a": "new", "b": "only"}


def test_bronze_metadata(spark, tmp_path):
    from sigap.pipeline.bronze import add_ingestion_metadata

    p = tmp_path / "x.csv"
    p.write_text("a\n1\n2\n")
    df = add_ingestion_metadata(spark.read.csv(str(p), header=True))
    r = df.collect()[0]
    assert r["_ingested_at"] is not None and r["_source_file"].endswith("x.csv")
    assert "_source_file" not in add_ingestion_metadata(spark.read.csv(str(p), header=True), False).columns
