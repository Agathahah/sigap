"""Phase 4 · rule baseline metrics."""

import pandas as pd
import pytest

from sigap.rules.engine import apply_rules, rule_report

pytestmark = pytest.mark.p4

RULES = [
    {"name": "device_fraud", "when": "device_fraud_count > 0"},
    {"name": "burst", "when": "velocity_6h > 3 * velocity_4w"},
]


def _df():
    return pd.DataFrame(
        {
            "device_fraud_count": [1, 0, 0, 0, 1, 0],
            "velocity_6h": [1, 9, 1, None, 1, 1],
            "velocity_4w": [1, 1, 1, 1, 1, 1],
        }
    )


def test_apply_rules():
    hits = apply_rules(_df(), RULES)
    assert list(hits.columns) == ["device_fraud", "burst", "any_rule"]
    assert hits["device_fraud"].tolist() == [True, False, False, False, True, False]
    assert hits["burst"].tolist() == [False, True, False, False, False, False]
    assert hits["any_rule"].tolist() == [True, True, False, False, True, False]


def test_rule_report_numbers():
    y = pd.Series([1, 1, 0, 0, 0, 0])
    rep = rule_report(apply_rules(_df(), RULES), y).set_index("rule")
    assert rep.loc["device_fraud", "alerts"] == 2
    assert rep.loc["device_fraud", "hit_rate"] == pytest.approx(0.5)
    assert rep.loc["device_fraud", "recall"] == pytest.approx(0.5)
    assert rep.loc["device_fraud", "fpr"] == pytest.approx(0.25)
    assert rep.loc["any_rule", "recall"] == pytest.approx(1.0)
    assert rep.loc["any_rule", "alert_rate"] == pytest.approx(0.5)


def test_rules_yaml_runs_on_silver_columns():
    """Every active rule is valid on a silver-shaped row and has a rationale; no protected attribute is used."""
    from sigap import config
    from sigap.quality.contract import load_contract
    from sigap.rules.engine import load_rules

    contract = load_contract(config.CONFIGS / "data_contract.yaml")
    row = {}
    for col, rule in contract["columns"].items():
        row[col] = rule["allowed"][0] if "allowed" in rule else rule.get("min", 0)
    row.update({f"{c}_missing": 0 for c in contract["sentinels"]})
    rules = load_rules()
    assert 5 <= len(rules) <= 8
    hits = apply_rules(pd.DataFrame([row]), rules)
    assert list(hits.columns) == [r["name"] for r in rules] + ["any_rule"]
    for r in rules:
        assert r.get("rationale"), f"{r['name']} needs a rationale"
        assert not any(p in r["when"] for p in ("customer_age", "income", "employment_status")), r["name"]
