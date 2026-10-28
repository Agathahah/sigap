"""Phase 4 · features: no inf, no leakage, fixed one-hot columns."""

import numpy as np
import pandas as pd
import pytest

from sigap.features import build

pytestmark = pytest.mark.p4


def test_velocity_ratio_no_inf():
    df = pd.DataFrame({"velocity_6h": [10.0, 5.0, 3.0, 1.0], "velocity_4w": [5.0, 0.0, -1.0, None]})
    r = build.velocity_ratio(df)
    assert r.name == "velocity_ratio"
    assert r.iloc[0] == 2.0 and r.iloc[1:].isna().all()
    assert not np.isinf(r.fillna(0)).any()


def _hist():
    # month 0: cat A 1/2 fraud, cat B 0/2 ; month 1: A 0/1, B 1/1 ; month 2..3: unknown labels for the test
    return pd.DataFrame(
        {
            "device_os": ["A", "A", "B", "B", "A", "B", "A", "B", "C", "A"],
            "month": [0, 0, 0, 0, 1, 1, 2, 2, 2, 3],
            "is_fraud": [1, 0, 0, 0, 0, 1, 1, 1, 1, 0],
        }
    )


def test_prior_rate_values_and_nan_before_labels():
    df = _hist()
    r = build.prior_rate(df, "device_os", lag_months=2, m=2)
    assert r.name == "prior_rate_device_os"
    assert r[df["month"] < 2].isna().all()  # no label is available yet in months 0-1
    g = 1 / 4  # month 0 only
    exp_a = (1 + 2 * g) / (2 + 2)
    exp_b = (0 + 2 * g) / (2 + 2)
    assert r.iloc[6] == pytest.approx(exp_a)
    assert r.iloc[7] == pytest.approx(exp_b)
    assert r.iloc[8] == pytest.approx(g)  # unseen category -> global rate


def test_prior_rate_has_no_leakage():
    df = _hist()
    before = build.prior_rate(df, "device_os", lag_months=2, m=2)
    leaked = df.copy()
    leaked.loc[leaked["month"] >= 2, "is_fraud"] = 1 - leaked.loc[leaked["month"] >= 2, "is_fraud"]
    leaked.loc[leaked["month"] == 1, "is_fraud"] = 1  # month 1 is NOT known at month 2 with lag 2
    after = build.prior_rate(leaked, "device_os", lag_months=2, m=2)
    pd.testing.assert_series_equal(before[df["month"] == 2], after[df["month"] == 2])


def test_one_hot_fixed_columns():
    df = pd.DataFrame({"source": ["INTERNET", "OTHER"], "device_os": ["linux", "linux"]})
    out = build.one_hot(df, {"source": ["INTERNET", "TELEAPP"], "device_os": ["windows", "linux"]})
    assert list(out.columns) == ["source__INTERNET", "source__TELEAPP", "device_os__windows", "device_os__linux"]
    assert out.iloc[1].tolist() == [0, 0, 0, 1]


def test_build_features_contract():
    df = _hist().assign(
        application_id=[f"x-{i}" for i in range(10)],
        payment_type=["AA", "AB"] * 5,
        velocity_6h=1.0,
        velocity_4w=2.0,
        income=0.5,
        bank_months_count_missing=0,
    )
    out = build.build_features(df, ["income"], {"payment_type": ["AA", "AB"]})
    assert list(out.columns) == [
        "application_id",
        "month",
        "income",
        "bank_months_count_missing",
        "payment_type__AA",
        "payment_type__AB",
        "velocity_ratio",
        "prior_rate_payment_type",
        "prior_rate_device_os",
    ]
    assert "is_fraud" not in out.columns and len(out) == 10


def test_feature_config_matches_contract():
    from sigap import config
    from sigap.quality.contract import load_contract

    numeric, categories, cfg = build.load_feature_config()
    contract = load_contract(config.CONFIGS / "data_contract.yaml")["columns"]
    used = set(numeric) | set(categories) | set(cfg["excluded"]) | {config.ID, config.MONTH}
    assert used == set(contract), f"not covered: {set(contract) - used}, unknown: {used - set(contract)}"
    assert not set(numeric) & set(cfg["excluded"])
