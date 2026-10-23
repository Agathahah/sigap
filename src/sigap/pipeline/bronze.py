"""Phase 3 · BRONZE (PySpark): validated landing CSV -> Parquet partitioned by month.

Bronze keeps the data as delivered (no cleaning), adds ingestion metadata, and is idempotent:
running the job twice for the same month must not double the rows.

Input : data/landing_valid/<variant>/month=XX/part.csv   (output of `make quality`)
Output: data/bronze/<variant>/applications/month=XX/*.parquet
        data/bronze/<variant>/labels/available_month=XX/*.parquet   (from landing/labels)

Run:  make bronze
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F  # noqa: F401


def add_ingestion_metadata(df: DataFrame, source_file_col: bool = True) -> DataFrame:
    """Phase 3 · TODO(Agatha): add `_ingested_at` (current UTC timestamp) and `_source_file`.

    `_source_file`: the file each row came from. Hint: F.input_file_name() (or the `_metadata.file_path`
    column in Spark 4). If source_file_col is False, add only `_ingested_at`.
    Test: tests/test_p3_spark.py::test_bronze_metadata (marker spark)
    """
    raise NotImplementedError("TODO(Agatha) phase 3: sigap.pipeline.bronze.add_ingestion_metadata")


def main() -> None:
    """Phase 3 · TODO(Agatha): the bronze job.

    Steps:
      1. spark = sigap.spark.get_spark("sigap-bronze")
      2. Read landing_valid CSVs with an EXPLICIT schema (build it from configs/data_contract.yaml;
         never inferSchema on production data: it is slow and silently changes types).
      3. add_ingestion_metadata, write Parquet partitioned by month with
         .mode("overwrite") and spark.sql.sources.partitionOverwriteMode=dynamic
         (only the months you re-run are replaced: this is what makes it idempotent).
      4. Same for labels, partitioned by available_month.
      5. Print row counts per month. Compare them with the manifest / quality report.
    """
    raise NotImplementedError("TODO(Agatha) phase 3: pipeline.bronze.main")


if __name__ == "__main__":
    main()
