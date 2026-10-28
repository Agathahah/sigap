"""Bronze (PySpark): validated landing CSV -> Parquet partitioned by month, as delivered plus ingestion metadata.

Input : data/landing_valid/<variant>/month=MM/part.csv     (output of `make quality`)
        data/landing/<variant>/labels/available_month=MM/part.csv
Output: data/bronze/<variant>/applications/month=M/*.parquet
        data/bronze/<variant>/labels/available_month=M/*.parquet

Idempotent: partitions are overwritten dynamically, so re-running a month replaces it instead of adding rows.

Run:  make bronze
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

from sigap import config

SPARK_TYPES = {"int": IntegerType(), "float": DoubleType(), "str": StringType()}
LABEL_SCHEMA = StructType(
    [
        StructField("application_id", StringType(), False),
        StructField("is_fraud", IntegerType(), False),
        StructField("month", IntegerType(), False),
        StructField("available_month", IntegerType(), False),
    ]
)


def schema_from_contract(contract: dict) -> StructType:
    """Explicit Spark schema in contract order. Never infer types on production data."""
    fields = [
        StructField(name, SPARK_TYPES[rule["type"]], rule.get("nullable", False))
        for name, rule in contract["columns"].items()
    ]
    return StructType(fields)


def add_ingestion_metadata(df: DataFrame, source_file_col: bool = True) -> DataFrame:
    """Add `_ingested_at` (UTC timestamp of the run) and, optionally, `_source_file` (file each row came from)."""
    out = df.withColumn("_ingested_at", F.current_timestamp())
    if source_file_col:
        out = out.withColumn("_source_file", F.col("_metadata.file_path"))
    return out


def read_csv(spark: SparkSession, path: str, schema: StructType) -> DataFrame:
    """Read every part.csv below `path` with a fixed schema; the header must match the schema names exactly."""
    return (
        spark.read.option("header", True)
        .option("enforceSchema", False)  # compare header names with the schema instead of trusting positions
        .option("mode", "FAILFAST")  # a malformed row stops the job instead of becoming NULLs
        .option("recursiveFileLookup", True)  # month=MM folders are not partitions here: month is a data column
        .option("pathGlobFilter", "part.csv")
        .schema(schema)
        .csv(path)
    )


def write_partitioned(df: DataFrame, path: str, column: str) -> None:
    df.write.mode("overwrite").partitionBy(column).parquet(path)


def main() -> None:
    from sigap.quality.contract import load_contract
    from sigap.spark import get_spark

    slug = config.VARIANT.lower().replace(" ", "_")
    spark = get_spark("sigap-bronze")
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    contract = load_contract(config.CONFIGS / "data_contract.yaml")

    apps_src = config.DATA / "landing_valid" / slug
    if not apps_src.exists():
        raise SystemExit(f"{apps_src} not found. Run `make quality` first.")
    apps = add_ingestion_metadata(read_csv(spark, str(apps_src), schema_from_contract(contract)))
    write_partitioned(apps, str(config.BRONZE / slug / "applications"), "month")

    labels = add_ingestion_metadata(read_csv(spark, str(config.LANDING / slug / "labels"), LABEL_SCHEMA))
    write_partitioned(labels, str(config.BRONZE / slug / "labels"), "available_month")

    counts = spark.read.parquet(str(config.BRONZE / slug / "applications")).groupBy("month").count().orderBy("month")
    print("bronze applications per month:")
    for r in counts.collect():
        print(f"  month {r['month']}: {r['count']:,}")
    n_labels = spark.read.parquet(str(config.BRONZE / slug / "labels")).count()
    print(f"bronze labels: {n_labels:,} -> {config.BRONZE / slug}")
    spark.stop()


if __name__ == "__main__":
    main()
