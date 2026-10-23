"""Phase 2 · Data quality: a data contract checked at the door, before data enters bronze.

configs/data_contract.yaml says what a valid application looks like (columns, types, ranges,
allowed categories). Each monthly drop is validated on arrival:
  - valid rows continue to bronze
  - invalid rows go to data/quarantine/ WITH the reason (never silently dropped)
  - a report (counts per rule) goes to reports/quality/ so the trend is visible month to month

Run:  make quality            (validates every landing month of the current variant)
Interview line: "Bad rows are quarantined with a reason and counted. If quarantine jumps from
0.1% to 5% in one month, that is an incident with the source system, not a modelling problem."
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


class ContractError(Exception):
    """Raised when a batch cannot be validated at all (e.g. a required column is missing)."""


def load_contract(path: Path) -> dict[str, Any]:
    """Load a contract YAML. Provided."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_batch(df: pd.DataFrame, contract: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Phase 2 · TODO(Agatha): split a batch into (valid, quarantine, report).

    contract format (see configs/data_contract.yaml):
        columns:
          <name>: {type: int|float|str, nullable: false, min: <num>, max: <num>, allowed: [..]}
    Rules, checked in this order for every row:
      1. Any contract column missing from df -> raise ContractError (whole batch rejected).
      2. Value null and nullable is false           -> reason "<col>: null"
      3. Numeric value < min or > max (if given)    -> reason "<col>: out of range"
      4. Value not in allowed (if given)            -> reason "<col>: not allowed"
    A row may break several rules; keep the FIRST reason found, scanning columns in contract order.
    Return:
      valid       rows with no reason (same columns as df)
      quarantine  rows with a reason, plus a column `_reason`
      report      {"rows": n, "valid": n_valid, "quarantined": n_bad, "<reason>": count, ...}
    Extra columns that are not in the contract pass through untouched.
    Tests: tests/test_p2_quality.py
    """
    raise NotImplementedError("TODO(Agatha) phase 2: sigap.quality.contract.validate_batch")


def main() -> None:
    """Phase 2 · TODO(Agatha): validate every landing/applications/month=XX/part.csv.

    For each month: validate_batch -> write valid rows to data/landing_valid/<variant>/month=XX/part.csv,
    quarantine to data/quarantine/<variant>/month=XX.csv, and append the report (with the month) to
    reports/quality/<variant>.csv. Print one line per month: month, rows, quarantined, top reason.
    """
    raise NotImplementedError("TODO(Agatha) phase 2: quality.contract.main")


if __name__ == "__main__":
    main()
