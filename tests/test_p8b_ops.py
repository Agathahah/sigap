"""Phase 8b · ops: alerts, review cases, analyst decisions through the API (no database, no n8n needed)."""

import os

import pandas as pd
import pytest

from sigap.ops.alerts import Alert, alert_key, build_alerts, format_alert_message
from sigap.ops.cases import InvalidTransition, assign_cases, case_payload, next_status
from sigap.ops.store import InMemoryStore

pytestmark = pytest.mark.p8b

CFG = {"psi_alert": 0.25, "review_capacity_per_day": 200, "queue_tolerance": 0.0, "quarantine_rate_alert": 0.02}
EMPTY_DRIFT = pd.DataFrame(columns=["month", "feature", "psi"])
EMPTY_QUEUE = pd.DataFrame(columns=["month", "day", "review_count"])
EMPTY_QUALITY = pd.DataFrame(columns=["month", "quarantine_rate"])


# ---------- alerts ----------
def test_alert_key_is_stable():
    k = alert_key("drift", 6, "score")
    assert k == alert_key("drift", 6, "score") and len(k) == 16 and int(k, 16) >= 0
    assert len({k, alert_key("drift", 7, "score"), alert_key("drift", 6, "income")}) == 3
    with pytest.raises(ValueError):
        alert_key("model_is_sad", 6, "score")


def test_alert_key_matches_sha1_definition():
    import hashlib

    assert (
        alert_key("data_incident", 7, "month=07")
        == hashlib.sha1(b"data_incident|7|month=07", usedforsecurity=False).hexdigest()[:16]
    )


def test_build_alerts_drift_only_above_alert():
    drift = pd.DataFrame({"month": [6, 6, 6], "feature": ["score", "velocity_6h", "income"], "psi": [0.31, 0.26, 0.15]})
    alerts = build_alerts(drift, EMPTY_QUEUE, EMPTY_QUALITY, CFG)
    assert [(a.kind, a.subject, a.severity) for a in alerts] == [
        ("drift", "score", "high"),
        ("drift", "velocity_6h", "medium"),
    ]
    assert alerts[0].value == pytest.approx(0.31) and alerts[0].threshold == pytest.approx(0.25)


def test_build_alerts_queue_and_data_incident_and_order():
    queue = pd.DataFrame(
        {"month": [6, 6, 6], "day": ["2026-11-03", "2026-11-02", "2026-11-04"], "review_count": [260, 350, 200]}
    )
    quality = pd.DataFrame({"month": [6, 7], "quarantine_rate": [0.004, 0.05]})
    drift = pd.DataFrame({"month": [7], "feature": ["velocity_6h"], "psi": [0.4]})
    alerts = build_alerts(drift, queue, quality, CFG)
    got = [(a.kind, a.subject, a.severity) for a in alerts]
    assert got == [
        ("queue_over_capacity", "2026-11-02", "high"),  # 350 > 1.5 x 200
        ("data_incident", "month=07", "high"),
        ("drift", "velocity_6h", "medium"),
        ("queue_over_capacity", "2026-11-03", "medium"),  # 260 > 200 but not > 300; 200 is not > 200
    ]
    assert all(a.alert_key == alert_key(a.kind, a.month, a.subject) for a in alerts)


def test_build_alerts_dedup_and_empty():
    drift = pd.DataFrame({"month": [6, 6], "feature": ["score", "score"], "psi": [0.3, 0.5]})
    alerts = build_alerts(drift, EMPTY_QUEUE, EMPTY_QUALITY, CFG)
    assert len(alerts) == 1 and alerts[0].value == pytest.approx(0.3)  # first row kept
    assert build_alerts(EMPTY_DRIFT, EMPTY_QUEUE, EMPTY_QUALITY, CFG) == []


def test_build_alerts_queue_tolerance():
    queue = pd.DataFrame({"month": [6], "day": ["2026-11-02"], "review_count": [215]})
    assert build_alerts(EMPTY_DRIFT, queue, EMPTY_QUALITY, {**CFG, "queue_tolerance": 0.10}) == []
    assert len(build_alerts(EMPTY_DRIFT, queue, EMPTY_QUALITY, CFG)) == 1


def test_format_alert_message():
    a = Alert(alert_key("drift", 6, "score"), "drift", "high", 6, "score", 0.3124, 0.25)
    msg = format_alert_message(a, "https://example.org/RUNBOOK.md")
    lines = msg.splitlines()
    assert lines[0] == "[SIGAP] Pergeseran data (PSI) · HIGH"
    assert "score" in msg and "6" in lines[1]
    assert "0.312" in msg and "0.250" in msg
    assert lines[-1] == "Runbook: https://example.org/RUNBOOK.md#drift"
    assert len(msg) <= 1024
    q = Alert(
        alert_key("queue_over_capacity", 6, "2026-11-02"), "queue_over_capacity", "high", 6, "2026-11-02", 350, 200
    )
    qmsg = format_alert_message(q, "https://x/RUNBOOK.md")
    assert "350" in qmsg and "200" in qmsg and "350.000" not in qmsg


# ---------- cases ----------
REVIEWS = pd.DataFrame(
    {
        "case_id": ["c4", "c1", "c2", "c3", "c5"],
        "application_id": ["a4", "a1", "a2", "a3", "a5"],
        "day": ["d2", "d1", "d1", "d1", "d2"],
        "score": [0.50, 0.70, 0.90, 0.70, 0.95],
    }
)


def test_assign_cases_capacity_and_priority():
    before = REVIEWS.copy()
    out = assign_cases(REVIEWS, capacity=2)
    pd.testing.assert_frame_equal(REVIEWS, before)  # input untouched
    assert out["case_id"].tolist() == ["c2", "c1", "c3", "c5", "c4"]  # tie 0.70 -> case_id ascending
    assert out["priority"].tolist() == [1, 2, 3, 1, 2]
    assert out["status"].tolist() == ["assigned", "assigned", "backlog", "assigned", "assigned"]
    assert list(out.index) == list(range(5))


def test_assign_cases_edge():
    assert set(assign_cases(REVIEWS, capacity=0)["status"]) == {"backlog"}
    with pytest.raises(ValueError):
        assign_cases(REVIEWS, capacity=-1)


def test_next_status():
    assert next_status("assigned", "confirmed_fraud") == "closed_fraud"
    assert next_status("backlog", "legit") == "closed_legit"
    assert next_status("assigned", "need_info") == "pending_info"
    assert next_status("pending_info", "legit") == "closed_legit"
    for cur, out in [("pending_info", "need_info"), ("closed_fraud", "legit"), ("closed_legit", "confirmed_fraud")]:
        with pytest.raises(InvalidTransition):
            next_status(cur, out)
    with pytest.raises(ValueError):
        next_status("assigned", "approve")
    with pytest.raises(ValueError):
        next_status("lost", "legit")


def test_case_payload_allowlist():
    row = {
        "case_id": "c1",
        "application_id": "a1",
        "day": "2026-11-02",
        "score": 0.912345,
        "decision_band": "review",
        "reasons": ["r1", "r2", "r3", "r4"],
        "customer_age": 60,
        "income": 0.9,
        "employment_status": "CA",
        "note": "nasabah menelepon",
        "new_col": 1,
    }
    p = case_payload(row)
    assert set(p) == {"case_id", "application_id", "day", "score", "decision_band", "reasons"}
    assert p["score"] == 0.91 and p["reasons"] == ["r1", "r2", "r3"]
    assert case_payload({"case_id": "c9"}) == {"case_id": "c9"}


# ---------- API (FastAPI TestClient, in-memory store) ----------
@pytest.fixture()
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sigap.serve.ops import get_store, router

    monkeypatch.setenv("SIGAP_OPS_API_KEY", "ops-test-key")
    # seeded by hand (not with your functions) so the API tests fail only because of the API
    store = InMemoryStore()
    cases = REVIEWS.assign(
        priority=[2, 2, 1, 3, 1],
        status=["assigned", "assigned", "assigned", "backlog", "assigned"],
        decision_band="review",
        reasons=[["r1"]] * 5,
        customer_age=[30, 40, 50, 60, 25],
    )
    store.add_cases(cases)
    store.add_alerts([Alert("k-drift-score-6", "drift", "high", 6, "score", 0.31, 0.25)])
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        c.store = store
        yield c


H = {"X-API-Key": "ops-test-key"}


def test_api_auth(client, monkeypatch):
    assert client.get("/v1/ops/alerts").status_code == 401
    assert client.get("/v1/ops/alerts", headers={"X-API-Key": "wrong"}).status_code == 401
    monkeypatch.delenv("SIGAP_OPS_API_KEY")
    assert client.get("/v1/ops/alerts", headers=H).status_code == 503


def test_api_alerts_and_ack(client):
    r = client.get("/v1/ops/alerts", headers=H)
    assert r.status_code == 200 and len(r.json()) == 1
    a = r.json()[0]
    assert set(a) == {"alert_key", "kind", "severity", "message"} and a["message"].startswith("[SIGAP]")
    assert (
        client.post(f"/v1/ops/alerts/{a['alert_key']}/ack", json={"channel": "whatsapp"}, headers=H).status_code == 200
    )
    assert (
        client.post(f"/v1/ops/alerts/{a['alert_key']}/ack", json={"channel": "whatsapp"}, headers=H).status_code == 200
    )
    assert client.get("/v1/ops/alerts", headers=H).json() == []
    assert client.post("/v1/ops/alerts/nope/ack", json={"channel": "whatsapp"}, headers=H).status_code == 404
    assert client.post(f"/v1/ops/alerts/{a['alert_key']}/ack", json={"channel": "sms"}, headers=H).status_code == 422


def test_api_cases(client):
    r = client.get("/v1/ops/cases?status=assigned", headers=H)
    assert r.status_code == 200 and [c["case_id"] for c in r.json()] == ["c2", "c1", "c5", "c4"]
    assert all("customer_age" not in c and "priority" not in c for c in r.json())
    assert client.get("/v1/ops/cases?status=whatever", headers=H).status_code == 422
    assert client.get("/v1/ops/cases?limit=0", headers=H).status_code == 422
    assert client.get("/v1/ops/cases?limit=101", headers=H).status_code == 422


def test_api_decision_flow(client):
    url = "/v1/ops/cases/c2/decision"
    body = {"outcome": "confirmed_fraud", "analyst_id": "agatha.s"}
    r = client.post(url, json=body, headers=H)
    assert r.status_code == 200 and r.json() == {"case_id": "c2", "status": "closed_fraud", "idempotent": False}
    r2 = client.post(url, json=body, headers=H)  # n8n retry
    assert r2.status_code == 200 and r2.json()["idempotent"] is True
    assert len(client.store.decisions) == 1
    assert client.post(url, json={"outcome": "legit", "analyst_id": "agatha.s"}, headers=H).status_code == 409
    assert client.post("/v1/ops/cases/c999/decision", json=body, headers=H).status_code == 404


@pytest.mark.parametrize(
    "bad",
    [
        {"outcome": "approve", "analyst_id": "agatha.s"},
        {"outcome": "legit", "analyst_id": "Agatha Silalahi"},
        {"outcome": "legit", "analyst_id": "ab"},
        {"outcome": "legit", "analyst_id": "agatha.s", "note": "x" * 501},
        {"outcom": "legit", "analyst_id": "agatha.s"},
    ],
)
def test_api_decision_rejects_bad_body(client, bad):
    assert client.post("/v1/ops/cases/c1/decision", json=bad, headers=H).status_code == 422


def test_api_need_info_then_decide(client):
    url = "/v1/ops/cases/c1/decision"
    assert (
        client.post(
            url, json={"outcome": "need_info", "analyst_id": "rina_01", "note": "minta KTP ulang"}, headers=H
        ).json()["status"]
        == "pending_info"
    )
    assert client.post(url, json={"outcome": "need_info", "analyst_id": "rina_01"}, headers=H).status_code == 409
    assert (
        client.post(url, json={"outcome": "legit", "analyst_id": "rina_01"}, headers=H).json()["status"]
        == "closed_legit"
    )


@pytest.mark.skipif(not os.getenv("SIGAP_TEST_DB"), reason="set SIGAP_TEST_DB to a Postgres URL to run")
def test_postgres_store_roundtrip():
    from sqlalchemy import create_engine

    from sigap.ops.store import PostgresStore

    s = PostgresStore(create_engine(os.environ["SIGAP_TEST_DB"]))
    drift = pd.DataFrame({"month": [99], "feature": ["score"], "psi": [0.9]})
    alerts = build_alerts(drift, EMPTY_QUEUE, EMPTY_QUALITY, CFG)
    s.add_alerts(alerts)
    assert s.add_alerts(alerts) == 0  # idempotent
    assert s.ack_alert(alerts[0].alert_key, "whatsapp") is True
