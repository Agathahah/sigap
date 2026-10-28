"""Phase 7 · API contract, training/serving consistency, and the API itself (on a tiny model built here)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.p7

GOOD = {
    "income": 0.6,
    "name_email_similarity": 0.3,
    "prev_address_months_count": -1,
    "current_address_months_count": 25,
    "customer_age": 40,
    "days_since_request": 0.01,
    "intended_balcon_amount": -1.2,
    "payment_type": "AB",
    "zip_count_4w": 1200,
    "velocity_6h": 5000.0,
    "velocity_24h": 4800.0,
    "velocity_4w": 4700.0,
    "bank_branch_count_8w": 3,
    "date_of_birth_distinct_emails_4w": 5,
    "employment_status": "CA",
    "credit_risk_score": 120,
    "email_is_free": 1,
    "housing_status": "BC",
    "phone_home_valid": 0,
    "phone_mobile_valid": 1,
    "bank_months_count": -1,
    "has_other_cards": 0,
    "proposed_credit_limit": 500.0,
    "foreign_request": 0,
    "source": "INTERNET",
    "session_length_in_minutes": 4.5,
    "device_os": "linux",
    "keep_alive_session": 1,
    "device_distinct_emails_8w": 1,
    "device_fraud_count": 0,
}


def test_schema_accepts_valid():
    from sigap.serve.schemas import ApplicationIn

    assert ApplicationIn(**GOOD).payment_type == "AB"


@pytest.mark.parametrize(
    "patch",
    [
        {"customer_age": 5},
        {"payment_type": "ZZ"},
        {"income": 1.5},
        {"device_os": "ios"},
        {"email_is_free": 2},
        {"unexpected_field": 1},
    ],
)
def test_schema_rejects_bad(patch):
    from sigap.serve.schemas import ApplicationIn

    with pytest.raises(ValidationError):
        ApplicationIn(**{**GOOD, **patch})


def test_schema_requires_every_field():
    from sigap.serve.schemas import ApplicationIn

    with pytest.raises(ValidationError):
        ApplicationIn(**{k: v for k, v in GOOD.items() if k != "device_fraud_count"})


CURRENT = Path(__file__).resolve().parents[1] / "models" / "current"
READY = all((CURRENT / f).exists() for f in ("model.joblib", "policy.json", "prior_rates.json"))


@pytest.mark.skipif(not READY, reason="models/current not ready (make train, make policy, make serve-prep)")
def test_api_scores_one_application(monkeypatch):
    monkeypatch.setenv("SIGAP_API_KEY", "test-key")
    monkeypatch.setenv("SIGAP_DECISION_LOG", "0")
    monkeypatch.delenv("SIGAP_MODEL_DIR", raising=False)
    from fastapi.testclient import TestClient

    from sigap.serve.app import app

    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.post("/v1/score", json=GOOD).status_code == 401
        r = c.post("/v1/score", json=GOOD, headers={"X-API-Key": "test-key"})
        assert r.status_code == 200 and r.json()["decision"] in {"approve", "review", "decline"}
        assert (
            c.post("/v1/score", json={**GOOD, "customer_age": 5}, headers={"X-API-Key": "test-key"}).status_code == 422
        )


SENTINELS = {
    "prev_address_months_count": "eq_-1",
    "current_address_months_count": "eq_-1",
    "intended_balcon_amount": "lt_0",
    "bank_months_count": "eq_-1",
    "session_length_in_minutes": "eq_-1",
    "device_distinct_emails_8w": "eq_-1",
}


def test_clean_sentinels_frame_flags_then_nulls():
    import pandas as pd

    from sigap.features.build import clean_sentinels_frame

    df = pd.DataFrame({"bank_months_count": [-1, 5], "intended_balcon_amount": [-0.3, 2.0]})
    out = clean_sentinels_frame(df, {"bank_months_count": "eq_-1", "intended_balcon_amount": "lt_0"})
    assert out["bank_months_count_missing"].tolist() == [1, 0] and pd.isna(out.loc[0, "bank_months_count"])
    assert out["intended_balcon_amount_missing"].tolist() == [1, 0] and out.loc[1, "intended_balcon_amount"] == 2.0


def _raw_history(n=400, seed=3):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    df = pd.DataFrame({k: [v] * n for k, v in GOOD.items()})
    df["application_id"] = [f"a{i}" for i in range(n)]
    df["month"] = rng.integers(0, 5, n)
    df["device_os"] = rng.choice(["windows", "linux", "other"], n)
    df["payment_type"] = rng.choice(["AA", "AB", "AC"], n)
    df["bank_months_count"] = rng.choice([-1, 3, 12], n)
    df["intended_balcon_amount"] = rng.normal(0, 5, n)
    df["velocity_6h"] = rng.uniform(1000, 9000, n)
    df["is_fraud"] = (rng.uniform(size=n) < 0.1).astype(int)
    return df


def test_serving_features_match_training():
    """The API's features for an application equal the training features of the same application."""
    import pandas as pd

    from sigap.features.build import build_features, clean_sentinels_frame, prior_rate_table, serving_frame

    raw = _raw_history()
    numeric = ["income", "credit_risk_score", "bank_months_count", "intended_balcon_amount", "velocity_6h"]
    cats = {"payment_type": ["AA", "AB", "AC", "AD", "AE"], "device_os": ["windows", "linux", "other"]}
    train = build_features(clean_sentinels_frame(raw, SENTINELS), numeric, cats, m=10).set_index("application_id")
    month = 4
    rows = raw[raw["month"] == month]
    tables = {c: prior_rate_table(raw, c, as_of=month, lag_months=2, m=10) for c in ("payment_type", "device_os")}
    serve = serving_frame(rows.drop(columns=["is_fraud"]), numeric, cats, tables, SENTINELS)
    serve.index = rows["application_id"]
    expected = train.loc[serve.index, serve.columns]
    pd.testing.assert_frame_equal(serve.astype(float), expected.astype(float), check_dtype=False)


def _tiny_model_folder(tmp_path):
    import json

    import pandas as pd
    import xgboost as xgb

    from sigap.features.build import clean_sentinels_frame, load_feature_config, prior_rate_table, serving_frame
    from sigap.train.model import SigapModel
    from sigap.train.train import calibrate

    raw = _raw_history(n=600)
    numeric, cats, _ = load_feature_config()
    tables = {c: prior_rate_table(raw, c, as_of=6, lag_months=2) for c in ("payment_type", "device_os")}
    X = serving_frame(raw.drop(columns=["is_fraud", "application_id", "month"]), numeric, cats, tables, SENTINELS)
    y = raw["is_fraud"].to_numpy()
    booster = xgb.XGBClassifier(n_estimators=10, max_depth=2).fit(X, y)
    SigapModel(calibrate(booster, X, y), booster, list(X.columns), 0.5, "tiny-v1").save(tmp_path)
    (tmp_path / "policy.json").write_text(json.dumps({"t_review": 0.0, "t_decline": None}))
    (tmp_path / "prior_rates.json").write_text(json.dumps({"as_of_month": 6, "tables": tables}))
    assert isinstance(clean_sentinels_frame(pd.DataFrame([GOOD]), SENTINELS), pd.DataFrame)
    return tmp_path


def test_api_contract_on_tiny_model(tmp_path, monkeypatch):
    pytest.importorskip("xgboost")
    from fastapi.testclient import TestClient

    folder = _tiny_model_folder(tmp_path)
    monkeypatch.setenv("SIGAP_MODEL_DIR", str(folder))
    monkeypatch.setenv("SIGAP_API_KEY", "k")
    monkeypatch.setenv("SIGAP_DECISION_LOG", "0")
    from sigap.serve.app import app

    with TestClient(app) as c:
        assert c.get("/health").json()["model_version"] == "tiny-v1"
        assert c.post("/v1/score", json=GOOD, headers={"X-API-Key": "wrong"}).status_code == 401
        r = c.post("/v1/score", json=GOOD, headers={"X-API-Key": "k", "X-Application-Id": "app-1"})
        body = r.json()
        assert r.status_code == 200 and body["application_id"] == "app-1" and body["decision"] == "review"
        assert all("age" not in reason for reason in body["reasons"])
        assert c.get("/v1/model", headers={"X-API-Key": "k"}).json()["features"] == 59  # tiny model: all features


def test_api_without_model_is_503(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SIGAP_MODEL_DIR", str(tmp_path))
    from sigap.serve.app import app

    with TestClient(app) as c:
        assert c.get("/health").status_code == 503
