"""Exploratory analysis in SQL on the training months only.

`load` builds `eda.applications` in Postgres: the validated applications of months 0-4 joined with their fraud
labels. Months 5-7 are left out on purpose (validation and test months stay unseen during exploration).
`run` executes `sql/analysis/q01..q07`, prints each result and saves it to `reports/eda/<query>.csv`.

Run:  make eda-load   then   make eda-sql
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

from sigap import config

EDA_MONTHS = config.TRAIN_MONTHS
SQL_DIR = config.ROOT / "sql" / "analysis"


def build_eda_frame(variant_dir: Path, months: tuple[int, ...] = EDA_MONTHS) -> pd.DataFrame:
    """Validated applications of `months` with `is_fraud` joined from the label feed.

    Reads `landing_valid` when the quality stage has run, otherwise `landing`. Labels are matched on
    application_id; every application of a training month has a label by the time those months are analysed.
    """
    valid_root = config.DATA / "landing_valid" / variant_dir.name
    apps_root = valid_root if valid_root.exists() else variant_dir / "applications"
    apps = pd.concat([pd.read_csv(apps_root / f"month={m:02d}" / "part.csv") for m in months], ignore_index=True)
    labels = pd.concat([pd.read_csv(p) for p in sorted((variant_dir / "labels").glob("*/part.csv"))])
    labels = labels.loc[labels["month"].isin(months), ["application_id", "is_fraud"]]
    out = apps.merge(labels, on="application_id", how="left", validate="one_to_one")
    if out["is_fraud"].isna().any():
        raise SystemExit(f"{int(out['is_fraud'].isna().sum())} applications have no label: check the label feed")
    out["is_fraud"] = out["is_fraud"].astype(int)
    return out


def load() -> None:
    """Create eda.applications in Postgres from the training months (fast COPY, replaces the table)."""
    from sqlalchemy import create_engine, text

    variant_dir = config.LANDING / config.VARIANT.lower().replace(" ", "_")
    df = build_eda_frame(variant_dir)
    engine = create_engine(config.database_url())
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS eda"))
        conn.execute(text("DROP TABLE IF EXISTS eda.applications"))
    df.head(0).to_sql("applications", engine, schema="eda", index=False)
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur, cur.copy("COPY eda.applications FROM STDIN WITH (FORMAT csv)") as cp:
            cp.write(buf.getvalue())
        raw.commit()
    finally:
        raw.close()
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM eda.applications")).scalar()
    print(f"eda.applications: {n:,} rows (months {EDA_MONTHS[0]}-{EDA_MONTHS[-1]}, fraud {df['is_fraud'].mean():.3%})")


def run(only: str | None = None) -> None:
    """Run every query in sql/analysis (q01-q07), print it and save the result as CSV."""
    from sqlalchemy import create_engine

    engine = create_engine(config.database_url())
    out_dir = config.REPORTS / "eda"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    for path in sorted(SQL_DIR.glob("q0[1-7]_*.sql")):
        if only and only not in path.name:
            continue
        sql = path.read_text(encoding="utf-8")
        question = next(
            (ln.split(":", 1)[1].strip() for ln in sql.splitlines() if ln.startswith("-- Question")), path.stem
        )
        result = pd.read_sql(sql, engine)
        result.to_csv(out_dir / f"{path.stem}.csv", index=False)
        print(f"\n== {path.stem} · {question}\n{result.to_string(index=False)}")
    print(f"\n-> {out_dir}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "run"
    if action == "load":
        load()
    else:
        run(sys.argv[2] if len(sys.argv) > 2 else None)
