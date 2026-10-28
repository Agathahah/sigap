"""Serving tables that travel with the model: the prior_rate lookup a scorer needs for one application.

Training computes prior_rate from history row by row; a single application has no history, so the API reads the
rates from models/current/prior_rates.json. They are built "as of" the month after the last drop: with a 2-month
label lag, scoring month 8 may use the labels of months 0-6.

Run:  make serve-prep   (after make train / make policy; train also calls it when the gate passes)
"""

from __future__ import annotations

import json
from pathlib import Path

from sigap import config


def build_prior_tables(slug: str, as_of: int | None = None) -> dict:
    from sigap.features.build import PRIOR_RATE_COLUMNS, prior_rate_table
    from sigap.rules.engine import load_silver_with_labels

    cfg = config.load_yaml("features").get("prior_rate", {})
    columns = tuple(cfg.get("columns", PRIOR_RATE_COLUMNS))
    m = float(cfg.get("smoothing_m", 100))
    df = load_silver_with_labels(slug)
    as_of = int(df[config.MONTH].max()) + 1 if as_of is None else as_of
    tables = {c: prior_rate_table(df, c, as_of, config.LABEL_LAG_MONTHS, m) for c in columns}
    return {"as_of_month": as_of, "label_lag": config.LABEL_LAG_MONTHS, "smoothing_m": m, "tables": tables}


def write_prior_tables(folder: Path, slug: str) -> Path:
    out = folder / "prior_rates.json"
    out.write_text(json.dumps(build_prior_tables(slug), indent=2), encoding="utf-8")
    return out


def main() -> None:
    slug = config.VARIANT.lower().replace(" ", "_")
    folder = config.MODELS / "current"
    if not (folder / "model.joblib").exists():
        raise SystemExit("models/current has no model: run `make train` first")
    out = write_prior_tables(folder, slug)
    data = json.loads(out.read_text())
    print(
        f"prior-rate lookup as of month {data['as_of_month']} (labels up to month "
        f"{data['as_of_month'] - data['label_lag']}) -> {out}"
    )
    for col, t in data["tables"].items():
        top = sorted(t["rates"].items(), key=lambda kv: -kv[1])[:3]
        print(f"  {col}: global {t['global']:.2%}; highest " + ", ".join(f"{k} {v:.2%}" for k, v in top))


if __name__ == "__main__":
    main()
