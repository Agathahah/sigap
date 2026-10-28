"""Data contract checked at the door, before a monthly drop enters the pipeline.

`configs/data_contract.yaml` describes a valid application: columns, types, ranges and allowed categories.
Each monthly drop is validated on arrival:
  - valid rows continue to `data/landing_valid/<variant>/month=MM/part.csv`
  - invalid rows go to `data/quarantine/<variant>/month=MM.csv` with the reason, never silently dropped
  - counts per rule go to `reports/quality/<variant>.csv`, so the quarantine rate can be followed month to month

A jump in the quarantine rate is a source-system incident to raise with the data owner, not a modelling problem.

Run:  make quality
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from sigap import config

NUMERIC_TYPES = {"int", "float"}


class ContractError(Exception):
    """Raised when a batch cannot be validated at all (e.g. a required column is missing)."""


def load_contract(path: Path) -> dict[str, Any]:
    """Load a contract YAML."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_batch(df: pd.DataFrame, contract: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Split a batch into (valid rows, quarantined rows with `_reason`, report of counts).

    Checks per contract column, in contract order: null (when not nullable), wrong type (numeric columns; int
    columns also reject non-whole numbers), out of range (min/max), not allowed (category list). A row keeps the
    first reason found. Valid rows are returned with int columns cast to integers.
    Columns that are not in the contract pass through untouched. A missing contract column rejects the batch.
    """
    columns = contract["columns"]
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ContractError(f"missing columns: {', '.join(missing)}")

    reason = pd.Series(pd.NA, index=df.index, dtype="object")

    def flag(mask: pd.Series, text: str) -> None:
        nonlocal reason
        reason = reason.mask(reason.isna() & mask.fillna(False).astype(bool), text)

    for col, rule in columns.items():
        values = df[col]
        is_null = values.isna()
        if not rule.get("nullable", False):
            flag(is_null, f"{col}: null")
        if rule.get("type") in NUMERIC_TYPES:
            numbers = pd.to_numeric(values, errors="coerce")
            flag(numbers.isna() & ~is_null, f"{col}: wrong type")
            if rule["type"] == "int":
                flag(numbers.notna() & (numbers % 1 != 0), f"{col}: wrong type")  # 12.5 is not an int
            if "min" in rule:
                flag(numbers < rule["min"], f"{col}: out of range")
            if "max" in rule:
                flag(numbers > rule["max"], f"{col}: out of range")
        if "allowed" in rule:
            flag(~values.isin(rule["allowed"]) & ~is_null, f"{col}: not allowed")

    bad = reason.notna()
    valid = df.loc[~bad].copy()
    for col, rule in columns.items():  # valid rows leave in contract types: 181.0 -> 181 for int columns
        if rule.get("type") == "int":
            valid[col] = pd.to_numeric(valid[col]).astype("Int64")
    quarantine = df.loc[bad].assign(_reason=reason[bad])
    report: dict[str, int] = {"rows": len(df), "valid": len(valid), "quarantined": int(bad.sum())}
    report.update(Counter(reason[bad].tolist()))
    return valid, quarantine, report


def main() -> None:
    """Validate every landing month of the current variant and write valid rows, quarantine and a report."""
    contract = load_contract(config.CONFIGS / "data_contract.yaml")
    slug = config.VARIANT.lower().replace(" ", "_")
    src = config.LANDING / slug / "applications"
    months = sorted(src.glob("month=*/part.csv"))
    if not months:
        raise SystemExit(f"No landing files in {src}. Run `make data-land` first.")

    rows = []
    for path in months:
        mm = path.parent.name.split("=")[1]
        valid, quarantine, report = validate_batch(pd.read_csv(path), contract)
        out = config.DATA / "landing_valid" / slug / f"month={mm}"
        out.mkdir(parents=True, exist_ok=True)
        valid.to_csv(out / "part.csv", index=False)
        qdir = config.QUARANTINE / slug
        qdir.mkdir(parents=True, exist_ok=True)
        quarantine.to_csv(qdir / f"month={mm}.csv", index=False)
        rows.append({"month": int(mm), **report})
        reasons = {k: v for k, v in report.items() if k not in ("rows", "valid", "quarantined")}
        top = max(reasons, key=reasons.get) if reasons else "-"
        rate = report["quarantined"] / report["rows"] if report["rows"] else 0
        bad = report["quarantined"]
        print(f"month {mm}: {report['rows']:>7,} rows  quarantined {bad:>5,} ({rate:.3%})  top: {top}")

    rep_dir = config.REPORTS / "quality"
    rep_dir.mkdir(parents=True, exist_ok=True)
    out_csv = rep_dir / f"{slug}.csv"
    pd.DataFrame(rows).fillna(0).to_csv(out_csv, index=False)
    print(f"-> {out_csv}")


if __name__ == "__main__":
    main()
