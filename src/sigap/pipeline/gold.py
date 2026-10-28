"""Gold: star schema in Postgres for analysts, dashboards and the copilot.

Grain of `gold.fact_application`: one row per application. Dimensions: month, channel, device, profile.
DDL: sql/warehouse/001_schemas.sql (applied on every run, idempotent). Diagram: docs/01_ERD.md.

Point-in-time labels: the warehouse is built "as of" the latest month in silver. A label is joined only when
`available_month <= as_of`; every other application keeps `is_fraud = NULL`, and `dim_month.label_complete`
says which months are fully labelled. Re-running after the next drop fills in the labels that have arrived.

Idempotent without TRUNCATE: dimensions insert new natural keys only (keys never change), the fact is upserted
on application_id. TRUNCATE would cascade into ops.decision_log, which references the fact.

Run:  make db-up && make gold
"""

from __future__ import annotations

import io
import os

import pandas as pd

from sigap import config

SENTINELS = (
    "prev_address_months_count",
    "current_address_months_count",
    "intended_balcon_amount",
    "bank_months_count",
    "session_length_in_minutes",
    "device_distinct_emails_8w",
)
MEASURES = (
    "name_email_similarity",
    "prev_address_months_count",
    "current_address_months_count",
    "days_since_request",
    "intended_balcon_amount",
    "zip_count_4w",
    "velocity_6h",
    "velocity_24h",
    "velocity_4w",
    "bank_branch_count_8w",
    "date_of_birth_distinct_emails_4w",
    "credit_risk_score",
    "phone_home_valid",
    "phone_mobile_valid",
    "bank_months_count",
    "has_other_cards",
    "proposed_credit_limit",
    "foreign_request",
    "session_length_in_minutes",
    "device_distinct_emails_8w",
) + tuple(f"{c}_missing" for c in SENTINELS)
DIMENSIONS = {
    "dim_channel": ("channel_key", ("source", "payment_type")),
    "dim_device": ("device_key", ("device_os", "keep_alive_session", "email_is_free")),
    "dim_profile": ("profile_key", ("age_band", "income_decile", "employment_status", "housing_status")),
}
INT_COLUMNS = (
    "zip_count_4w",
    "bank_branch_count_8w",
    "date_of_birth_distinct_emails_4w",
    "credit_risk_score",
    "phone_home_valid",
    "phone_mobile_valid",
    "has_other_cards",
    "foreign_request",
    "keep_alive_session",
    "email_is_free",
)
NULLABLE_INT_COLUMNS = (
    "prev_address_months_count",
    "current_address_months_count",
    "bank_months_count",
    "device_distinct_emails_8w",
)


def age_band(age: pd.Series) -> pd.Series:
    """BAF ages are rounded to decades (10..90). Bands match the fairness groups used later (50+ vs under 50)."""
    bins = [-1, 29, 39, 49, 59, 200]
    labels = ["<30", "30-39", "40-49", "50-59", "60+"]
    return pd.cut(age, bins=bins, labels=labels).astype(str)


def income_decile(income: pd.Series) -> pd.Series:
    """BAF income is a decile written as a fraction (0.1..0.9) -> integer 1..9."""
    return (income * 10).round().astype(int)


def labels_as_of(labels: pd.DataFrame, as_of: int) -> pd.DataFrame:
    """Labels a warehouse built at month `as_of` is allowed to know: available_month <= as_of."""
    known = labels.loc[labels["available_month"] <= as_of, [config.ID, config.LABEL]]
    return known.drop_duplicates(config.ID, keep="last")


def month_dimension(months: list[int], as_of: int, lag: int = config.LABEL_LAG_MONTHS) -> pd.DataFrame:
    """One row per month; label_complete when every label of that month has arrived (month + lag <= as_of)."""
    return pd.DataFrame(
        {"month_key": months, "month_index": months, "label_complete": [m + lag <= as_of for m in months]}
    )


def build_fact_frame(apps: pd.DataFrame, labels: pd.DataFrame, as_of: int) -> pd.DataFrame:
    """Silver applications + derived dimension attributes + point-in-time label, one row per application."""
    out = apps.copy()
    out["age_band"] = age_band(out["customer_age"])
    out["income_decile"] = income_decile(out["income"])
    out = out.merge(labels_as_of(labels, as_of), on=config.ID, how="left", validate="one_to_one")
    for c in INT_COLUMNS:
        out[c] = out[c].astype(int)
    for c in (*NULLABLE_INT_COLUMNS, config.LABEL):
        out[c] = out[c].astype("Int64")  # keep NULLs without turning integers into floats
    natural = [k for _, nat in DIMENSIONS.values() for k in nat]
    cols = [config.ID, config.MONTH, *natural, *MEASURES, config.LABEL]
    return out[cols]


def read_silver(slug: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    apps = pd.read_parquet(config.SILVER / slug / "applications")
    apps[config.MONTH] = apps[config.MONTH].astype(int)  # partition column comes back as a category
    labels = pd.read_parquet(config.SILVER / slug / "labels")
    return apps, labels


def _copy(cur, table: str, df: pd.DataFrame) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    with cur.copy(f"COPY {table} ({', '.join(df.columns)}) FROM STDIN WITH (FORMAT csv)") as cp:
        cp.write(buf.getvalue())


def load(fact: pd.DataFrame, months: pd.DataFrame, dsn: str) -> dict[str, int]:
    """Apply the DDL and upsert dims + fact in one transaction. Returns row counts for the checks."""
    import psycopg

    ddl = (config.ROOT / "sql" / "warehouse" / "001_schemas.sql").read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(ddl)
        cur.execute("CREATE TEMP TABLE stage_month (LIKE gold.dim_month) ON COMMIT DROP")
        _copy(cur, "stage_month", months)
        cur.execute(
            "INSERT INTO gold.dim_month SELECT * FROM stage_month "
            "ON CONFLICT (month_key) DO UPDATE SET label_complete = EXCLUDED.label_complete"
        )
        measures = ", ".join((*MEASURES, config.LABEL))
        cur.execute(
            f"CREATE TEMP TABLE stage_app ON COMMIT DROP AS SELECT application_id, {measures}, "  # noqa: S608
            "NULL::smallint AS month, NULL::text AS source, NULL::text AS payment_type, "
            "NULL::text AS device_os, NULL::smallint AS keep_alive_session, NULL::smallint AS email_is_free, "
            "NULL::text AS age_band, NULL::smallint AS income_decile, NULL::text AS employment_status, "
            "NULL::text AS housing_status "
            "FROM gold.fact_application WITH NO DATA"
        )
        _copy(cur, "stage_app", fact)
        for table, (_, natural) in DIMENSIONS.items():
            cols = ", ".join(natural)
            cur.execute(
                f"INSERT INTO gold.{table} ({cols}) SELECT DISTINCT {cols} FROM stage_app "  # noqa: S608
                f"ON CONFLICT ({cols}) DO NOTHING"
            )
        joins = " ".join(f"JOIN gold.{t} USING ({', '.join(nat)})" for t, (_, nat) in DIMENSIONS.items())
        keys = ", ".join(key for key, _ in DIMENSIONS.values())
        targets = ("month_key", *(key for key, _ in DIMENSIONS.values()), *MEASURES, config.LABEL)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in targets)
        cur.execute(
            f"INSERT INTO gold.fact_application (application_id, month_key, {keys}, {measures}) "  # noqa: S608
            f"SELECT application_id, month, {keys}, {measures} FROM stage_app {joins} "
            f"ON CONFLICT (application_id) DO UPDATE SET {updates}"
        )
        cur.execute("SELECT count(*) FROM stage_app")
        staged = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM gold.fact_application f JOIN stage_app s USING (application_id)")
        loaded = cur.fetchone()[0]
        if loaded != staged:
            raise RuntimeError(f"fact load incomplete: {loaded:,} of {staged:,} staged rows; rolling back")
        conn.commit()
    return {"staged": staged, "loaded": loaded}


def summary(dsn: str) -> pd.DataFrame:
    import psycopg

    sql = (
        "SELECT m.month_index AS month, m.label_complete, count(*) AS applications, "
        "count(f.is_fraud) AS labelled, round(100.0 * avg(f.is_fraud), 2) AS fraud_pct "
        "FROM gold.fact_application f JOIN gold.dim_month m USING (month_key) "
        "GROUP BY 1, 2 ORDER BY 1"
    )
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cur.execute(
            "SELECT 'dim_channel', count(*) FROM gold.dim_channel UNION ALL "
            "SELECT 'dim_device', count(*) FROM gold.dim_device UNION ALL "
            "SELECT 'dim_profile', count(*) FROM gold.dim_profile"
        )
        dims = cur.fetchall()
    print("dimension rows: " + ", ".join(f"{t} {n}" for t, n in dims))
    return pd.DataFrame(rows, columns=["month", "label_complete", "applications", "labelled", "fraud_pct"])


def psycopg_dsn(url: str) -> str:
    """SQLAlchemy URL (postgresql+psycopg://...) -> libpq URL that psycopg.connect accepts."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    slug = config.VARIANT.lower().replace(" ", "_")
    apps, labels = read_silver(slug)
    months = sorted(apps[config.MONTH].unique().tolist())
    as_of = int(os.getenv("SIGAP_AS_OF_MONTH", max(months)))
    fact = build_fact_frame(apps, labels, as_of)
    dsn = psycopg_dsn(config.database_url())
    counts = load(fact, month_dimension(months, as_of), dsn)
    print(f"gold as of month {as_of}: silver {len(apps):,} rows -> fact {counts['loaded']:,} rows")
    print(summary(dsn).to_string(index=False))


if __name__ == "__main__":
    main()
