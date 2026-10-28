"""Rule baseline: what a fraud team runs before any model, measured the way a fraud manager reads it.

Rules live in `configs/rules.yaml` as pandas expressions evaluated on silver columns (sentinels are NULL there,
with `<column>_missing` flags). Each rule is reported with alerts, alert rate, hit rate (precision), recall and
false-positive rate. The union of all rules (`any_rule`) is the champion policy the model has to beat.

Rules are tuned on the training months (0-4) and checked once on the validation month (5). The test months stay
untouched until the champion/challenger replay.

Run:  make rules   -> reports/rules/<variant>_train.csv and reports/rules/<variant>_valid.csv
"""

from __future__ import annotations

import pandas as pd

from sigap import config

REPORT_COLUMNS = ["rule", "alerts", "alert_rate", "hit_rate", "recall", "fpr"]


def load_rules(path=config.CONFIGS / "rules.yaml") -> list[dict]:
    """Active rules from the YAML file (the `retired` section is documentation only)."""
    import yaml

    with open(path, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("rules", [])


def apply_rules(df: pd.DataFrame, rules: list[dict]) -> pd.DataFrame:
    """One boolean column per rule (in rule order) plus `any_rule`, aligned to df.index.

    A comparison with a missing value is False, so a NULL never raises an alert by accident.
    """
    hits = pd.DataFrame(index=df.index)
    for rule in rules:
        hit = df.eval(rule["when"])
        hits[rule["name"]] = pd.Series(hit, index=df.index).fillna(False).astype(bool)
    hits["any_rule"] = hits.any(axis=1) if rules else False
    return hits


def _ratio(num: float, den: float) -> float:
    return float(num) / float(den) if den else 0.0


def rule_report(hits: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """One row per rule: alerts, alert_rate, hit_rate (precision), recall, fpr."""
    y = pd.Series(y, index=hits.index).astype(int)
    fraud, good, rows = int(y.sum()), int((y == 0).sum()), len(y)
    out = []
    for col in hits.columns:
        h = hits[col].astype(bool)
        alerts = int(h.sum())
        tp = int((h & (y == 1)).sum())
        fp = alerts - tp
        out.append(
            {
                "rule": col,
                "alerts": alerts,
                "alert_rate": _ratio(alerts, rows),
                "hit_rate": _ratio(tp, alerts),
                "recall": _ratio(tp, fraud),
                "fpr": _ratio(fp, good),
            }
        )
    return pd.DataFrame(out, columns=REPORT_COLUMNS)


def load_silver_with_labels(slug: str) -> pd.DataFrame:
    """Silver applications joined with their fraud label (historical evaluation, not scoring)."""
    apps = pd.read_parquet(config.SILVER / slug / "applications")
    apps[config.MONTH] = apps[config.MONTH].astype(int)
    labels = pd.read_parquet(config.SILVER / slug / "labels", columns=[config.ID, config.LABEL])
    return apps.merge(labels, on=config.ID, how="left", validate="one_to_one")


def _print(name: str, report: pd.DataFrame, rows: int) -> None:
    shown = report.assign(
        alert_rate=(100 * report["alert_rate"]).round(2),
        hit_rate=(100 * report["hit_rate"]).round(2),
        recall=(100 * report["recall"]).round(1),
        fpr=(100 * report["fpr"]).round(2),
    ).rename(columns={"alert_rate": "alert_%", "hit_rate": "hit_%", "recall": "recall_%", "fpr": "fpr_%"})
    print(f"\n{name}: {rows:,} applications")
    print(shown.to_string(index=False))


def main() -> None:
    slug = config.VARIANT.lower().replace(" ", "_")
    rules = load_rules()
    df = load_silver_with_labels(slug)
    out_dir = config.REPORTS / "rules"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{len(rules)} rules from configs/rules.yaml; base fraud rate shown per period below")
    for period, months in (("train", config.TRAIN_MONTHS), ("valid", config.VALID_MONTHS)):
        part = df[df[config.MONTH].isin(months)]
        report = rule_report(apply_rules(part, rules), part[config.LABEL])
        report.to_csv(out_dir / f"{slug}_{period}.csv", index=False)
        span = f"months {months[0]}-{months[-1]}" if len(months) > 1 else f"month {months[0]}"
        _print(f"{period} ({span}, fraud {100 * part[config.LABEL].mean():.2f}%)", report, len(part))
    print(f"\n-> {out_dir}/{slug}_train.csv, {slug}_valid.csv")


if __name__ == "__main__":
    main()
