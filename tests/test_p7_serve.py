"""Phase 7 · API contract. (The live API test runs only when models/current exists.)"""

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


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "models" / "current").exists(), reason="no model yet")
def test_api_scores_one_application(monkeypatch):
    monkeypatch.setenv("SIGAP_API_KEY", "test-key")
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
