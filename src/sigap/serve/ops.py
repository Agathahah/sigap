"""Ops API: the only door n8n uses to read alerts/cases and to write analyst decisions.

Mounted in serve/app.py with `app.include_router(router)` (phase 7 app) and in serve/ops_demo.py (demo).

Contract (each line is tested in tests/test_p8b_ops.py):
  Auth   every endpoint needs header X-API-Key == env SIGAP_OPS_API_KEY, compared with secrets.compare_digest.
         Missing/wrong key -> 401. Env not set -> 503 (refuse to run open). This key is NOT the scoring key:
         n8n can read alerts and write decisions, it cannot score applications (least privilege).

  GET  /v1/ops/alerts[?channel=email|whatsapp|telegram]
         -> 200 [{"alert_key", "kind", "severity", "message"}], message from
            format_alert_message(alert, env SIGAP_RUNBOOK_URL or DEFAULT_RUNBOOK_URL).
            Without channel: alerts not acknowledged on the primary channel (n8n). With a channel: alerts not yet
            delivered on that channel (ops.alert_delivery), so each channel sends an alert once.
  POST /v1/ops/alerts/{alert_key}/ack      body {"channel": "whatsapp" | "email" | "telegram"}
         -> 200 {"alert_key", "acked": true}; acking twice is fine (200 again); unknown key -> 404
  GET  /v1/ops/cases?status=assigned&limit=20
         -> 200 [case_payload(case), ...]; status must be one of OPEN_STATUSES + CLOSED_STATUSES (else 422);
            1 <= limit <= 100 (else 422)
  POST /v1/ops/cases/{case_id}/decision    body DecisionIn
         -> 200 {"case_id", "status", "idempotent": false} after store.save_decision(...)
         -> 404 unknown case
         -> 409 InvalidTransition (e.g. deciding a closed case differently)
         -> 422 invalid body (Pydantic)
         Idempotency: n8n retries when the network hiccups. If the case is already closed AND the last decision
         has the same outcome and analyst_id, return 200 {"case_id", "status", "idempotent": true} without
         writing a second record.
"""

from __future__ import annotations

import os
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from sigap.ops.alerts import format_alert_message
from sigap.ops.cases import CLOSED_STATUSES, OPEN_STATUSES, InvalidTransition, case_payload, next_status
from sigap.ops.store import OpsStore, get_store

DEFAULT_RUNBOOK_URL = "https://github.com/Agathahah/sigap/blob/main/docs/RUNBOOK.md"

router = APIRouter(prefix="/v1/ops", tags=["ops"])


class AckIn(BaseModel):
    """Acknowledge an alert after it was delivered."""

    model_config = ConfigDict(extra="forbid")
    channel: Literal["whatsapp", "email", "telegram"]


class DecisionIn(BaseModel):
    """An analyst decision as n8n sends it. Unknown fields are rejected (a typo is a 422, not ignored)."""

    model_config = ConfigDict(extra="forbid")
    outcome: Literal["confirmed_fraud", "legit", "need_info"]
    analyst_id: str = Field(pattern=r"^[a-z0-9._-]{3,32}$", description="an id, not a name or phone number")
    note: str | None = Field(default=None, max_length=500)


def require_ops_key(x_api_key: str | None = Header(default=None)) -> None:
    """503 when SIGAP_OPS_API_KEY is not configured (never run open), 401 when the header is missing or wrong."""
    expected = os.getenv("SIGAP_OPS_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="ops API key is not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


CHANNELS = ("whatsapp", "email", "telegram")


@router.get("/alerts", dependencies=[Depends(require_ops_key)])
def list_alerts(channel: str | None = None, store: OpsStore = Depends(get_store)) -> list[dict]:
    if channel is not None and channel not in CHANNELS:
        raise HTTPException(status_code=422, detail=f"channel must be one of {CHANNELS}")
    url = os.getenv("SIGAP_RUNBOOK_URL", DEFAULT_RUNBOOK_URL)
    return [
        {"alert_key": a.alert_key, "kind": a.kind, "severity": a.severity, "message": format_alert_message(a, url)}
        for a in store.list_open_alerts(channel)
    ]


@router.post("/alerts/{alert_key}/ack", dependencies=[Depends(require_ops_key)])
def ack_alert(alert_key: str, body: AckIn, store: OpsStore = Depends(get_store)) -> dict:
    if not store.ack_alert(alert_key, body.channel):
        raise HTTPException(status_code=404, detail="unknown alert")
    return {"alert_key": alert_key, "acked": True}


@router.get("/cases", dependencies=[Depends(require_ops_key)])
def list_cases(
    status: str = "assigned",
    limit: int = Query(20, ge=1, le=100),
    store: OpsStore = Depends(get_store),
) -> list[dict]:
    if status not in OPEN_STATUSES + CLOSED_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {OPEN_STATUSES + CLOSED_STATUSES}")
    return [case_payload(c) for c in store.list_cases(status, limit)]


@router.post("/cases/{case_id}/decision", dependencies=[Depends(require_ops_key)])
def decide(case_id: str, body: DecisionIn, store: OpsStore = Depends(get_store)) -> dict:
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="unknown case")
    last = store.last_decision(case_id)
    if (
        case["status"] in CLOSED_STATUSES
        and last
        and last["outcome"] == body.outcome
        and last["analyst_id"] == body.analyst_id
    ):
        return {"case_id": case_id, "status": case["status"], "idempotent": True}  # a retry of the same decision
    try:
        new_status = next_status(case["status"], body.outcome)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save_decision(case_id, body.outcome, body.analyst_id, body.note, new_status)
    return {"case_id": case_id, "status": new_status, "idempotent": False}
