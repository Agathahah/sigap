"""Phase 8b · Ops API: the only door n8n uses to read alerts/cases and to write analyst decisions.

Mounted in serve/app.py with `app.include_router(router)` (phase 7 app) and in serve/ops_demo.py (demo).

Contract (each line is tested in tests/test_p8b_ops.py):
  Auth   every endpoint needs header X-API-Key == env SIGAP_OPS_API_KEY, compared with secrets.compare_digest.
         Missing/wrong key -> 401. Env not set -> 503 (refuse to run open). This key is NOT the scoring key:
         n8n can read alerts and write decisions, it cannot score applications (least privilege).

  GET  /v1/ops/alerts
         -> 200 [{"alert_key", "kind", "severity", "message"}] for alerts not yet acknowledged, message from
            format_alert_message(alert, env SIGAP_RUNBOOK_URL or DEFAULT_RUNBOOK_URL)
  POST /v1/ops/alerts/{alert_key}/ack      body {"channel": "whatsapp" | "email"}
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

from fastapi import APIRouter, Depends, Header, Query  # noqa: F401
from pydantic import BaseModel, ConfigDict

from sigap.ops.alerts import format_alert_message  # noqa: F401
from sigap.ops.cases import CLOSED_STATUSES, OPEN_STATUSES, InvalidTransition, case_payload, next_status  # noqa: F401
from sigap.ops.store import OpsStore, get_store  # noqa: F401

DEFAULT_RUNBOOK_URL = "https://github.com/Agathahah/sigap/blob/main/docs/RUNBOOK.md"

router = APIRouter(prefix="/v1/ops", tags=["ops"])


class AckIn(BaseModel):
    """Phase 8b · TODO(Agatha): field `channel`, only "whatsapp" or "email" (Literal). Forbid extra fields."""

    model_config = ConfigDict(extra="forbid")


class DecisionIn(BaseModel):
    """Phase 8b · TODO(Agatha): the analyst decision n8n sends.

      outcome     one of OUTCOMES ("confirmed_fraud", "legit", "need_info")
      analyst_id  3-32 characters of a-z, 0-9, ".", "_", "-" (an id, not a name or phone number)
      note        optional, at most 500 characters
    Forbid extra fields (a typo like "outcom" must be a 422, not silently ignored).
    """

    model_config = ConfigDict(extra="forbid")


def require_ops_key(x_api_key: str | None = Header(default=None)) -> None:
    """Phase 8b · TODO(Agatha): 503 if SIGAP_OPS_API_KEY is not set, 401 if the header is missing or wrong."""
    raise NotImplementedError("TODO(Agatha) phase 8b: serve.ops.require_ops_key")


@router.get("/alerts", dependencies=[Depends(require_ops_key)])
def list_alerts(store: OpsStore = Depends(get_store)) -> list[dict]:
    raise NotImplementedError("TODO(Agatha) phase 8b: GET /v1/ops/alerts")


@router.post("/alerts/{alert_key}/ack", dependencies=[Depends(require_ops_key)])
def ack_alert(alert_key: str, body: AckIn, store: OpsStore = Depends(get_store)) -> dict:
    raise NotImplementedError("TODO(Agatha) phase 8b: POST /v1/ops/alerts/{key}/ack")


@router.get("/cases", dependencies=[Depends(require_ops_key)])
def list_cases(status: str = "assigned", limit: int = 20, store: OpsStore = Depends(get_store)) -> list[dict]:
    raise NotImplementedError("TODO(Agatha) phase 8b: GET /v1/ops/cases")


@router.post("/cases/{case_id}/decision", dependencies=[Depends(require_ops_key)])
def decide(case_id: str, body: DecisionIn, store: OpsStore = Depends(get_store)) -> dict:
    raise NotImplementedError("TODO(Agatha) phase 8b: POST /v1/ops/cases/{id}/decision")
