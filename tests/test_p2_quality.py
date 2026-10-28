"""Phase 2 · data contract: quarantine with reasons, never silent drops."""

import pandas as pd
import pytest

from sigap.quality.contract import ContractError, validate_batch

pytestmark = pytest.mark.p2

CONTRACT = {
    "columns": {
        "income": {"type": "float", "min": 0, "max": 1},
        "customer_age": {"type": "int", "min": 10, "max": 100},
        "payment_type": {"type": "str", "allowed": ["AA", "AB"]},
        "bank_months_count": {"type": "int", "nullable": True, "min": -1},
    }
}


def _df():
    return pd.DataFrame(
        {
            "income": [0.5, 1.5, None, 0.2, 0.3],
            "customer_age": [30, 40, 50, 5, 20],
            "payment_type": ["AA", "AB", "AA", "AA", "ZZ"],
            "bank_months_count": [-1, None, 3, 4, 5],
            "extra": [1, 2, 3, 4, 5],
        }
    )


def test_valid_and_quarantine_split():
    valid, bad, report = validate_batch(_df(), CONTRACT)
    assert len(valid) == 1 and valid["extra"].tolist() == [1]
    assert bad["_reason"].tolist() == [
        "income: out of range",
        "income: null",
        "customer_age: out of range",
        "payment_type: not allowed",
    ]
    assert report["rows"] == 5 and report["valid"] == 1 and report["quarantined"] == 4
    assert report["income: out of range"] == 1


def test_first_reason_wins():
    df = _df().iloc[[1]].assign(customer_age=1)
    _, bad, _ = validate_batch(df, CONTRACT)
    assert bad["_reason"].tolist() == ["income: out of range"]


def test_int_column_rejects_fractions_and_returns_integers():
    df = _df().iloc[[0, 0]].reset_index(drop=True)
    df["customer_age"] = [30.0, 30.5]
    valid, bad, _ = validate_batch(df, CONTRACT)
    assert bad["_reason"].tolist() == ["customer_age: wrong type"]
    assert valid["customer_age"].tolist() == [30] and str(valid["customer_age"].dtype) == "Int64"


def test_missing_column_rejects_batch():
    with pytest.raises(ContractError):
        validate_batch(_df().drop(columns=["payment_type"]), CONTRACT)


def test_eda_frame_keeps_training_months_and_joins_labels(tmp_path, monkeypatch):
    from sigap import config
    from sigap.quality import eda

    variant = tmp_path / "landing" / "base"
    for m in range(6):
        d = variant / "applications" / f"month={m:02d}"
        d.mkdir(parents=True)
        pd.DataFrame({"application_id": [f"a{m}"], "month": [m], "income": [0.5]}).to_csv(d / "part.csv", index=False)
        lab = variant / "labels" / f"available_month={m + 2:02d}"
        lab.mkdir(parents=True)
        pd.DataFrame(
            {"application_id": [f"a{m}"], "is_fraud": [m % 2], "month": [m], "available_month": [m + 2]}
        ).to_csv(lab / "part.csv", index=False)
    monkeypatch.setattr(config, "DATA", tmp_path)
    out = eda.build_eda_frame(variant, months=(0, 1, 2, 3, 4))
    assert sorted(out["month"]) == [0, 1, 2, 3, 4]
    assert out.set_index("application_id")["is_fraud"].to_dict() == {"a0": 0, "a1": 1, "a2": 0, "a3": 1, "a4": 0}
