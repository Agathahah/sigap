"""Phase 4 · Rule baseline: what a fraud team runs BEFORE any model.

Every fraud team already has rules ("more than N applications from this device this week").
SIGAP measures them first, so the model has to beat something real, and so you can talk about
rule tuning the way fraud analyst job descriptions do (hit rate, false positives, alert volume).

Rules live in configs/rules.yaml:
    - name: device_seen_with_fraud
      when: "device_fraud_count > 0"
      rationale: "..."
Run:  make rules   -> reports/rules/<variant>_valid.csv
"""

from __future__ import annotations

import pandas as pd


def apply_rules(df: pd.DataFrame, rules: list[dict]) -> pd.DataFrame:
    """Phase 4 · TODO(Agatha): evaluate each rule on every row.

    Each rule has "name" and "when" (a pandas query expression). Return a DataFrame aligned to df.index
    with one bool column per rule (named by rule["name"], in rule order) plus "any_rule" (OR of all).
    Rows where the expression cannot be True (e.g. NaN comparisons) are False.
    Hint: df.eval(rule["when"]) returns a boolean Series; .fillna(False).
    Test: tests/test_p4_rules.py::test_apply_rules
    """
    raise NotImplementedError("TODO(Agatha) phase 4: sigap.rules.engine.apply_rules")


def rule_report(hits: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Phase 4 · TODO(Agatha): the table a fraud manager reads.

    For every column of `hits` (each rule and any_rule) return one row with:
        rule, alerts, alert_rate (alerts / rows), hit_rate (fraud among alerts = precision),
        recall (share of all fraud that the rule flags), fpr (good customers flagged / all good)
    Use 0.0 instead of dividing by zero. Index = default RangeIndex, order = hits column order.
    Test: tests/test_p4_rules.py::test_rule_report_numbers
    """
    raise NotImplementedError("TODO(Agatha) phase 4: sigap.rules.engine.rule_report")


def main() -> None:
    """Phase 4 · TODO(Agatha): run configs/rules.yaml on the validation month(s) and save the report.

    Then tune: change thresholds in rules.yaml, re-run, and keep a short log in docs/04_DECISION_POLICY.md
    ("raised velocity threshold from X to Y: alerts -30%, recall -2 pts").
    """
    raise NotImplementedError("TODO(Agatha) phase 4: rules.engine.main")


if __name__ == "__main__":
    main()
