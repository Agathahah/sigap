"""Phase 8b · Operational alerts: what wakes up the fraud team, and what does not.

Three signals, three different owners (this is the business lesson of the phase):
  drift                 score/feature PSI >= psi_alert           -> data science (model may be stale)
  queue_over_capacity   reviews in a day > capacity x (1 + tol)  -> fraud operations lead (people, not models)
  data_incident         quarantine rate of a month >= limit      -> owner of the source system (not the model!)

An alert is sent ONCE. n8n polls the API every few minutes; without a stable key the same drift would be sent
to WhatsApp every 15 minutes. `alert_key` gives the same id for the same event, so the store can de-duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

KINDS = ("drift", "queue_over_capacity", "data_incident")
SEVERITY_ORDER = {"high": 0, "medium": 1}

KIND_LABEL_ID = {  # what the analyst reads on WhatsApp
    "drift": "Pergeseran data (PSI)",
    "queue_over_capacity": "Antrean review melebihi kapasitas",
    "data_incident": "Insiden data sumber (karantina)",
}


@dataclass(frozen=True)
class Alert:
    """Provided. One operational alert, ready to be stored in ops.alert and sent by n8n."""

    alert_key: str
    kind: str  # one of KINDS
    severity: str  # "high" | "medium"
    month: int
    subject: str  # feature name (drift), day "YYYY-MM-DD" (queue) or "month=MM" (data incident)
    value: float  # observed value: PSI, review count, quarantine rate
    threshold: float  # the limit it crossed
    extra: dict = field(default_factory=dict, compare=False)


def alert_key(kind: str, month: int, subject: str) -> str:
    """Phase 8b · TODO(Agatha): stable id for one event.

    - sha1 of the text f"{kind}|{month}|{subject}" (utf-8), first 16 hex characters.
      Pass usedforsecurity=False: this is an id, not a password hash (and ruff rule S324 stays quiet).
    - Same inputs -> same key on every run and every machine (do NOT use hash(), it is salted per process).
    - Raise ValueError if kind is not in KINDS.
    Test: tests/test_p8b_ops.py::test_alert_key_is_stable
    """
    raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.alerts.alert_key")


def build_alerts(drift: pd.DataFrame, queue: pd.DataFrame, quality: pd.DataFrame, cfg: dict) -> list[Alert]:
    """Phase 8b · TODO(Agatha): turn monitoring tables into a de-duplicated, ordered list of alerts.

    Inputs (any of them may be empty):
      drift    columns month, feature, psi           (from ops.monitoring_monthly / drift_report)
      queue    columns month, day, review_count      (reviews created per day, from ops.review_case)
      quality  columns month, quarantine_rate        (0-1, from the phase 2 quality report)
      cfg      psi_alert (e.g. 0.25), review_capacity_per_day (int), queue_tolerance (e.g. 0.0),
               quarantine_rate_alert (e.g. 0.02)

    Rules:
      drift:   psi >= psi_alert -> Alert(kind="drift", subject=feature, value=psi, threshold=psi_alert),
               severity "high" if feature == "score" else "medium". PSI between "watch" and "alert" is a
               dashboard matter, NOT a message.
      queue:   review_count > capacity * (1 + queue_tolerance) -> kind "queue_over_capacity", subject=day,
               value=review_count, threshold=capacity, severity "high" if review_count > 1.5 * capacity else
               "medium".
      quality: quarantine_rate >= quarantine_rate_alert -> kind "data_incident", subject=f"month={month:02d}",
               severity "high".
    Every alert gets alert_key(kind, month, subject). If two rows produce the same key, keep the first.
    Order: severity (high first), then kind in the order of KINDS, then subject ascending.
    Tests: tests/test_p8b_ops.py::test_build_alerts_*
    """
    raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.alerts.build_alerts")


def format_alert_message(alert: Alert, runbook_base_url: str) -> str:
    """Phase 8b · TODO(Agatha): the WhatsApp text for one alert (Indonesian, plain text).

    Must contain, each on its own line:
      1. "[SIGAP] " + KIND_LABEL_ID[alert.kind] + " · " + alert.severity.upper()
      2. the subject and the month, e.g. "Subjek: score · bulan 6"
      3. value and threshold with 3 decimals for floats below 1 (PSI, rates) and no decimals otherwise,
         e.g. "Nilai: 0.312 (batas 0.250)" or "Nilai: 260 (batas 200)"
      4. "Runbook: " + runbook_base_url + "#" + alert.kind
    At most 1024 characters (the body limit of a WhatsApp interactive message). No personal data can appear
    here by construction: alerts are aggregates.
    Test: tests/test_p8b_ops.py::test_format_alert_message
    """
    raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.alerts.format_alert_message")
