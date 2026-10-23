"""Turn one Kaggle CSV into the feeds a bank actually receives: monthly drops and late labels.

A bank does not receive a finished dataset. Applications arrive continuously; fraud labels arrive weeks
later, after chargebacks and investigations. This job simulates both, so every later stage works with
what production works with.

Output (data/landing/<variant>/):
    applications/month=00/part.csv ... month=07/part.csv   no label column
    labels/available_month=02/part.csv ...                application_id, is_fraud, month, available_month

Run:  make data-land
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sigap import config


def add_application_id(df: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Copy of `df` with a deterministic `application_id` as the first column, e.g. "variant_i-0000003".

    The id is the variant slug plus the 0-based row position, so re-running the job yields the same ids
    and loads stay idempotent.
    """
    slug = variant.lower().replace(" ", "_")
    out = df.reset_index(drop=True).copy()
    out.insert(0, "application_id", [f"{slug}-{i:07d}" for i in range(len(out))])
    return out


def make_label_feed(df: pd.DataFrame, lag_months: int = config.LABEL_LAG_MONTHS) -> pd.DataFrame:
    """Late-arriving labels: application_id, is_fraud (0/1), month, available_month = month + lag."""
    return pd.DataFrame(
        {
            "application_id": df["application_id"].to_numpy(),
            "is_fraud": df[config.RAW_LABEL].astype(int).to_numpy(),
            "month": df[config.MONTH].astype(int).to_numpy(),
            "available_month": (df[config.MONTH].astype(int) + lag_months).to_numpy(),
        }
    )


def write_landing(df: pd.DataFrame, landing_dir: Path, lag_months: int = config.LABEL_LAG_MONTHS) -> dict[str, int]:
    """Write monthly application drops (without the label) and the lagged label feed.

    Files are overwritten, never appended, so re-running a month does not duplicate rows.
    Returns the number of application rows and label rows written.
    """
    landing_dir = Path(landing_dir)
    apps = df.drop(columns=[config.RAW_LABEL])
    n_apps = 0
    for month, part in apps.groupby(config.MONTH, sort=True):
        folder = landing_dir / "applications" / f"month={int(month):02d}"
        folder.mkdir(parents=True, exist_ok=True)
        part.to_csv(folder / "part.csv", index=False)
        n_apps += len(part)
    labels = make_label_feed(df, lag_months)
    n_labels = 0
    for avail, part in labels.groupby("available_month", sort=True):
        folder = landing_dir / "labels" / f"available_month={int(avail):02d}"
        folder.mkdir(parents=True, exist_ok=True)
        part.to_csv(folder / "part.csv", index=False)
        n_labels += len(part)
    return {"applications": n_apps, "labels": n_labels}


def main() -> None:
    """CLI: read data/raw/<VARIANT>.csv, add ids, write the landing feeds."""
    src = config.RAW / f"{config.VARIANT}.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found. Run `make data-download` first.")
    df = add_application_id(pd.read_csv(src), config.VARIANT)
    out = config.LANDING / config.VARIANT.lower().replace(" ", "_")
    print(write_landing(df, out), "->", out)


if __name__ == "__main__":
    main()
