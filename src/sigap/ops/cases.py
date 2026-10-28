"""Review cases: who looks at what today, and what an analyst is allowed to decide.

Business rules:
  - The review band of phase 6 creates more cases than the team can handle on busy days. The riskiest cases are
    assigned first; the rest wait in a backlog (and the backlog itself is an alert, see alerts.py).
  - An analyst decision is an audit record. A closed case cannot be re-opened by a second message.
  - Analyst decisions are EARLY labels, but only for reviewed cases (selective labels, Lakkaraju et al. 2017).
    They are stored in ops.review_decision and never overwrite the 2-month label in gold.fact_application.
"""

from __future__ import annotations

import pandas as pd

OUTCOMES = ("confirmed_fraud", "legit", "need_info")
OPEN_STATUSES = ("assigned", "backlog", "pending_info")
CLOSED_STATUSES = ("closed_fraud", "closed_legit")

# Fields allowed to leave SIGAP (to n8n and WhatsApp). An ALLOWLIST: anything new is excluded by default.
PAYLOAD_FIELDS = ("case_id", "application_id", "day", "score", "decision_band", "reasons")


class InvalidTransition(ValueError):
    """Raised when an outcome is not allowed from the current status (the API maps it to HTTP 409)."""


def assign_cases(reviews: pd.DataFrame, capacity: int) -> pd.DataFrame:
    """Assign the riskiest reviews of each day up to capacity; the rest go to the backlog.

    Per day: order by score (highest first, ties by case_id), priority 1, 2, 3, ...; status "assigned" for
    priority <= capacity, else "backlog". Returns a new frame sorted by day and priority; the input is unchanged.
    """
    if capacity < 0:
        raise ValueError("capacity must be >= 0")
    out = reviews.sort_values(["day", "score", "case_id"], ascending=[True, False, True]).copy()
    out["priority"] = out.groupby("day").cumcount() + 1
    out["status"] = ["assigned" if p <= capacity else "backlog" for p in out["priority"]]
    return out.reset_index(drop=True)


def next_status(current: str, outcome: str) -> str:
    """The case state machine.

    open (assigned, backlog, pending_info) + confirmed_fraud -> closed_fraud
    open + legit -> closed_legit;  assigned/backlog + need_info -> pending_info
    pending_info + need_info and any closed case -> InvalidTransition (ask once, then decide; no re-opening).
    Unknown status or outcome -> ValueError (bad input).
    """
    if current not in OPEN_STATUSES + CLOSED_STATUSES:
        raise ValueError(f"unknown status {current!r}")
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}")
    if current in CLOSED_STATUSES:
        raise InvalidTransition(f"case is {current}; a closed case cannot be decided again")
    if outcome == "confirmed_fraud":
        return "closed_fraud"
    if outcome == "legit":
        return "closed_legit"
    if current == "pending_info":
        raise InvalidTransition("information was already requested once; decide fraud or legit")
    return "pending_info"


def case_payload(row: dict) -> dict:
    """What may leave SIGAP about a case (to n8n, and so to WhatsApp): PAYLOAD_FIELDS only.

    Score rounded to 2 decimals, at most 3 reason codes. An allowlist, so a column added later never leaks.
    """
    payload = {k: row[k] for k in PAYLOAD_FIELDS if k in row}
    if "score" in payload:
        payload["score"] = round(float(payload["score"]), 2)
    if "reasons" in payload:
        payload["reasons"] = list(payload["reasons"])[:3]
    if "day" in payload:
        payload["day"] = str(payload["day"])
    return payload
