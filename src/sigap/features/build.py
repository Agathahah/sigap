"""Feature engineering: silver -> model matrix (pandas; one BAF variant is 1M rows and fits in memory).

The matrix holds the raw numeric columns (sentinels already NULL), the six `<column>_missing` flags, one-hot
columns with a fixed category list, and two engineered signals an analyst can read:

  velocity_ratio          velocity_6h / velocity_4w: the last 6 hours compared with the 4-week normal
                          (both are applications per hour, so the ratio has no unit)
  prior_rate_<column>     fraud rate of the category (payment_type, device_os) computed only from labels that had
                          arrived by that month (month <= t - label lag), smoothed toward the global rate

The label is written to a separate file, so a model can never read it as a feature by accident.

Run:  make features   -> data/gold/<variant>/features.parquet and data/gold/<variant>/labels.parquet
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sigap import config

PRIOR_RATE_COLUMNS = ("payment_type", "device_os")


def velocity_ratio(df: pd.DataFrame) -> pd.Series:
    """velocity_6h / velocity_4w; NaN (never inf) where velocity_4w is missing or not positive."""
    denom = df["velocity_4w"].where(df["velocity_4w"] > 0)
    return (df["velocity_6h"] / denom).replace([np.inf, -np.inf], np.nan).rename("velocity_ratio")


def prior_rate(df: pd.DataFrame, col: str, lag_months: int = config.LABEL_LAG_MONTHS, m: float = 100.0) -> pd.Series:
    """Point-in-time fraud rate of each row's category, smoothed toward the global rate.

    For a row in month t only rows with month <= t - lag_months count (their labels exist at month t):
        rate = (frauds_in_category + m * global_rate) / (rows_in_category + m)
    An unseen category gets the global rate. Before any label has arrived the rate is NaN.
    """
    stats = df.groupby([col, config.MONTH], observed=True)[config.LABEL].agg(n="size", f="sum").reset_index()
    out = pd.Series(np.nan, index=df.index, name=f"prior_rate_{col}", dtype=float)
    for t in sorted(df[config.MONTH].unique()):
        known = stats[stats[config.MONTH] <= t - lag_months]
        if known.empty:
            continue
        g = known["f"].sum() / known["n"].sum()
        per_cat = known.groupby(col, observed=True)[["n", "f"]].sum()
        rates = (per_cat["f"] + m * g) / (per_cat["n"] + m)
        rows = df[config.MONTH] == t
        out[rows] = df.loc[rows, col].map(rates).astype(float).fillna(g)
    return out


def one_hot(df: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    """One 0/1 column per (column, value) in the fixed list, in that order; unknown values get all zeros."""
    cols = {f"{col}__{value}": (df[col] == value).astype(int) for col, values in categories.items() for value in values}
    return pd.DataFrame(cols, index=df.index)


def build_features(
    df: pd.DataFrame,
    numeric: list[str],
    categories: dict[str, list[str]],
    m: float = 100.0,
    prior_columns: tuple[str, ...] = PRIOR_RATE_COLUMNS,
) -> pd.DataFrame:
    """Model matrix: id, month, numeric, missing flags, one-hot, velocity_ratio, prior rates. No label."""
    flags = [c for c in df.columns if c.endswith("_missing")]
    parts = [
        df[[config.ID, config.MONTH, *numeric, *flags]],
        one_hot(df, categories),
        velocity_ratio(df),
        *(prior_rate(df, c, m=m) for c in prior_columns),
    ]
    return pd.concat(parts, axis=1)


def load_feature_config() -> tuple[list[str], dict[str, list[str]], dict]:
    """Numeric columns, categories (allowed values from the data contract) and the full feature config."""
    from sigap.quality.contract import load_contract

    cfg = config.load_yaml("features")
    contract = load_contract(config.CONFIGS / "data_contract.yaml")["columns"]
    categories = {c: list(contract[c]["allowed"]) for c in cfg["categorical"]}
    return list(cfg["numeric"]), categories, cfg


def main() -> None:
    from sigap.rules.engine import load_silver_with_labels

    slug = config.VARIANT.lower().replace(" ", "_")
    numeric, categories, cfg = load_feature_config()
    df = load_silver_with_labels(slug)
    if df[config.LABEL].isna().any():
        raise SystemExit("some applications have no label in silver: check the label feed")
    prior = cfg.get("prior_rate", {})
    feats = build_features(
        df,
        numeric,
        categories,
        m=float(prior.get("smoothing_m", 100)),
        prior_columns=tuple(prior.get("columns", PRIOR_RATE_COLUMNS)),
    )
    assert config.LABEL not in feats.columns

    out = config.GOLD / slug
    out.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(out / "features.parquet", index=False)
    labels = df[[config.ID, config.MONTH, config.LABEL]].assign(
        available_month=df[config.MONTH] + config.LABEL_LAG_MONTHS
    )
    labels.to_parquet(out / "labels.parquet", index=False)

    n_feat = feats.shape[1] - 2
    print(f"features: {len(feats):,} rows x {n_feat} features -> {out / 'features.parquet'}")
    print(f"labels  : {len(labels):,} rows (separate file) -> {out / 'labels.parquet'}")
    by_month = feats.groupby(config.MONTH).agg(
        rows=(config.ID, "size"),
        velocity_ratio_median=("velocity_ratio", "median"),
        prior_rate_missing_pct=("prior_rate_device_os", lambda s: round(100 * s.isna().mean(), 1)),
    )
    win = feats.loc[df["device_os"] == "windows"].groupby(config.MONTH)["prior_rate_device_os"].first()
    lin = feats.loc[df["device_os"] == "linux"].groupby(config.MONTH)["prior_rate_device_os"].first()
    by_month["prior_rate_windows_%"] = (100 * win).round(2)
    by_month["prior_rate_linux_%"] = (100 * lin).round(2)
    print("\nper month (prior rates are NaN until the first labels arrive at month 2):")
    print(by_month.round(3).to_string())


if __name__ == "__main__":
    main()
