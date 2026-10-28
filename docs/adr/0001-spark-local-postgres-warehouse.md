# ADR 0001 · PySpark (local) for bronze/silver, Postgres for the gold warehouse

- Status: proposed
- Date: 2026-10-27

## Context
- Applications arrive as monthly drops (CSV), with fraud labels two months later in a separate feed.
  Each drop must be re-processable without creating duplicates, and every row has to be traceable to its file.
- One BAF variant is 1M rows and fits in pandas; the six variants together are 6M, and a bank's application
  history is far larger. The transformation code should not need a rewrite when the data or the cluster grows.
- Three consumers read the curated data: analysts (SQL), the monitoring dashboard, and the copilot (read-only,
  without protected attributes). They need one shared, queryable source with access control.
- Constraint: everything runs on one laptop, free tooling, no cloud account.

## Options considered
1. **pandas end to end, CSV/Parquet files as the warehouse** — simplest and fast at 1M rows; no role-based
   access, no SQL for analysts, and the code would have to be rewritten for data that does not fit in memory.
2. **PySpark local for bronze/silver + Postgres star schema for gold** — the same DataFrame code runs on
   YARN, Kubernetes or Databricks by changing the master and paths; Postgres gives SQL, constraints, roles and
   pgvector for the copilot in one service. Costs: Java 17 and a JVM start-up of a few seconds per job.
3. **dbt/DuckDB** — strong for SQL transforms on one machine; does not show distributed processing, and the
   job descriptions targeted (Spark, star schema, Postgres) ask for that combination directly.
4. **Cloud warehouse (BigQuery/Snowflake)** — closest to some production stacks; needs a cloud account and
   billing, and moves data outside the laptop.

## Decision
Use PySpark in local mode for bronze and silver (Parquet, partitioned by month) and load the gold star schema
into Postgres 16 with pgvector, running in Docker.

## Consequences
- **Idempotent by design.** Bronze and silver overwrite month partitions dynamically; gold inserts new
  dimension members only and upserts the fact on `application_id`, so re-running a month gives the same tables.
  Gold never truncates, because `ops.decision_log` references the fact.
- **Explicit schema.** Bronze reads with the schema built from `configs/data_contract.yaml` (`FAILFAST`, header
  checked against the schema); no type inference on incoming data.
- **Point-in-time labels.** Gold joins a label only when `available_month <= as_of`; `dim_month.label_complete`
  tells dashboards which months can report a fraud rate.
- **Access control in the database.** Protected attributes live in `gold.dim_profile`; the copilot gets a
  read-only role and views without them (ADR 0003).
- **Harder:** Java 17 on every machine that runs the pipeline; Spark start-up dominates run time at this data
  size, so Spark is not faster than pandas here and that is not the reason for choosing it.
- **Monitor:** rows per month at each layer (bronze = silver = fact), quarantine rate, and the share of
  months with `label_complete = false` (should be exactly the last two).
