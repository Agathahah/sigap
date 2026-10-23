"""Phase 8b · Review cases: who looks at what today, and what an analyst is allowed to decide.

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
    """Provided. Raised when an outcome is not allowed from the current status (the API maps it to HTTP 409)."""


def assign_cases(reviews: pd.DataFrame, capacity: int) -> pd.DataFrame:
    """Phase 8b · TODO(Agatha): assign the riskiest reviews of each day, up to capacity.

    reviews: columns case_id, application_id, day, score (one row per review case).
    For each day separately:
      - order by score descending, ties by case_id ascending (deterministic)
      - priority = 1, 2, 3, ... in that order
      - status = "assigned" for priority <= capacity, else "backlog"
    Return a new DataFrame with all input columns + priority + status, sorted by day then priority,
    with a fresh RangeIndex. Do not modify the input. capacity must be >= 0 (ValueError otherwise).
    Tests: tests/test_p8b_ops.py::test_assign_cases_*
    """
    raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.cases.assign_cases")


def next_status(current: str, outcome: str) -> str:
    """Phase 8b · TODO(Agatha): the case state machine.

      assigned | backlog | pending_info  + confirmed_fraud -> closed_fraud
      assigned | backlog | pending_info  + legit           -> closed_legit
      assigned | backlog                 + need_info       -> pending_info
      pending_info                       + need_info       -> InvalidTransition (ask once, then decide)
      closed_*                           + anything        -> InvalidTransition
    Unknown status or outcome -> ValueError (bad input, HTTP 422), not InvalidTransition.
    Test: tests/test_p8b_ops.py::test_next_status
    """
    raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.cases.next_status")


def case_payload(row: dict) -> dict:
    """Phase 8b · TODO(Agatha): what n8n (and therefore WhatsApp) may see about a case.

    - Keep only PAYLOAD_FIELDS that are present in row (missing ones are simply absent).
    - score rounded to 2 decimals; reasons cut to at most 3 items (list of reason codes from phase 5).
    - Everything else is dropped: protected attributes (customer_age, income, employment_status), raw features,
      notes. Allowlist, not denylist: a column added next month must not leak by accident.
    Test: tests/test_p8b_ops.py::test_case_payload_allowlist
    """
    raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.cases.case_payload")
