"""Phase 3 · GOLD: star schema in Postgres for analysts, dashboards and the copilot.

Design it first in docs/01_ERD.md (that is the deliverable an interviewer asks about), then build it.
Minimum model (grain = one application):

    fact_application(application_id PK, month_key FK, channel_key FK, device_key FK, profile_key FK,
                     credit_risk_score, proposed_credit_limit, velocity_6h, velocity_24h, velocity_4w,
                     ... numeric measures ..., is_fraud NULL until the label is available)
    dim_month(month_key, month_index, label_complete BOOLEAN)
    dim_channel(channel_key, source, payment_type)
    dim_device(device_key, device_os, keep_alive_session, email_is_free)
    dim_profile(profile_key, age_band, income_decile, employment_status, housing_status)

Plus two operational tables written by later phases:
    decision_log(application_id, model_version, score, decision, reasons, decided_at)    -- phase 7
    monitoring_monthly(month, feature, psi, alert_rate, tpr, fpr, computed_at)           -- phase 8

DDL lives in sql/warehouse/*.sql (you write it). Load with Spark JDBC or pandas.to_sql.
Run:  make db-up && make gold
"""

from __future__ import annotations


def main() -> None:
    """Phase 3 · TODO(Agatha): build dims + fact from silver and load them into Postgres.

    1. Apply sql/warehouse/001_schemas.sql (CREATE SCHEMA/TABLE IF NOT EXISTS).
    2. Build each dimension with distinct values + a surrogate key (row_number over the natural key).
    3. Build the fact by joining silver to the dims on natural keys.
    4. Load with TRUNCATE + INSERT inside one transaction (idempotent).
    5. Check: row count of fact == silver rows; no NULL foreign keys; print both.
    """
    raise NotImplementedError("TODO(Agatha) phase 3: pipeline.gold.main")


if __name__ == "__main__":
    main()
