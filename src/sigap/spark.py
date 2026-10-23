"""Local SparkSession. Provided.

On a laptop Spark runs as `local[*]`: driver and executors share one JVM and use every core.
The same DataFrame code runs on a cluster (YARN/Hadoop, Kubernetes, Databricks) by changing the
master and the storage path (hdfs://, s3a://). That is why the pipeline uses the DataFrame API
even though one BAF variant (1M rows) would still fit in pandas.
"""

from __future__ import annotations

import os
import sys

from pyspark.sql import SparkSession


def get_spark(app_name: str = "sigap", shuffle_partitions: int = 8) -> SparkSession:
    # Make Spark's Python workers use the venv interpreter (classic Mac + conda problem).
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    return (
        SparkSession.builder.appName(app_name)
        .master(os.getenv("SIGAP_SPARK_MASTER", "local[*]"))
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))  # default 200 -> thousands of tiny files
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.memory", os.getenv("SIGAP_SPARK_DRIVER_MEMORY", "3g"))
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
