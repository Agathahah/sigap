"""Operational alerts: what wakes up the fraud team, and what does not.

Three signals, three different owners (this is the business lesson of the phase):
  drift                 score/feature PSI >= psi_alert           -> data science (model may be stale)
  queue_over_capacity   reviews in a day > capacity x (1 + tol)  -> fraud operations lead (people, not models)
  data_incident         quarantine rate of a month >= limit      -> owner of the source system (not the model!)

An alert is sent ONCE. n8n polls the API every few minutes; without a stable key the same drift would be sent
to WhatsApp every 15 minutes. `alert_key` gives the same id for the same event, so the store can de-duplicate.
"""

from __future__ import annotations

import hashlib
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
    """One operational alert, ready to be stored in ops.alert and sent by n8n."""

    alert_key: str
    kind: str  # one of KINDS
    severity: str  # "high" | "medium"
    month: int
    subject: str  # feature name (drift), day "YYYY-MM-DD" (queue) or "month=MM" (data incident)
    value: float  # observed value: PSI, review count, quarantine rate
    threshold: float  # the limit it crossed
    extra: dict = field(default_factory=dict, compare=False)


def alert_key(kind: str, month: int, subject: str) -> str:
    """Stable id for one event: first 16 hex characters of sha1("kind|month|subject").

    The same event gets the same key on every run and machine (Python's hash() is salted per process), so the
    store de-duplicates repeated polls and an alert reaches WhatsApp once.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown alert kind {kind!r}; expected one of {KINDS}")
    return hashlib.sha1(f"{kind}|{month}|{subject}".encode(), usedforsecurity=False).hexdigest()[:16]


def build_alerts(drift: pd.DataFrame, queue: pd.DataFrame, quality: pd.DataFrame, cfg: dict) -> list[Alert]:
    """Monitoring tables -> de-duplicated, ordered alerts.

    drift   (month, feature, psi):            psi >= psi_alert -> "drift"; high for the score, medium otherwise.
                                              Watch-level PSI belongs on the dashboard, not in a message.
    queue   (month, day, review_count):       count > capacity x (1 + tolerance) -> "queue_over_capacity";
                                              high above 1.5 x capacity.
    quality (month, quarantine_rate):         rate >= quarantine_rate_alert -> "data_incident", high.
    The first row wins when two produce the same key. Order: severity, kind (KINDS order), subject.
    """
    psi_alert = float(cfg["psi_alert"])
    capacity = float(cfg["review_capacity_per_day"])
    tolerance = float(cfg.get("queue_tolerance", 0.0))
    q_limit = float(cfg["quarantine_rate_alert"])
    out: list[Alert] = []
    for r in drift.itertuples(index=False):
        if r.psi >= psi_alert:
            severity = "high" if r.feature == "score" else "medium"
            key = alert_key("drift", int(r.month), str(r.feature))
            out.append(Alert(key, "drift", severity, int(r.month), str(r.feature), float(r.psi), psi_alert))
    for r in queue.itertuples(index=False):
        if r.review_count > capacity * (1 + tolerance):
            severity = "high" if r.review_count > 1.5 * capacity else "medium"
            key = alert_key("queue_over_capacity", int(r.month), str(r.day))
            out.append(
                Alert(key, "queue_over_capacity", severity, int(r.month), str(r.day), float(r.review_count), capacity)
            )
    for r in quality.itertuples(index=False):
        if r.quarantine_rate >= q_limit:
            subject = f"month={int(r.month):02d}"
            key = alert_key("data_incident", int(r.month), subject)
            out.append(Alert(key, "data_incident", "high", int(r.month), subject, float(r.quarantine_rate), q_limit))
    unique: dict[str, Alert] = {}
    for a in out:
        unique.setdefault(a.alert_key, a)  # first row wins
    return sorted(unique.values(), key=lambda a: (SEVERITY_ORDER[a.severity], KINDS.index(a.kind), a.subject))


def format_alert_message(alert: Alert, runbook_base_url: str) -> str:
    """The WhatsApp text for one alert (Indonesian, plain text, at most 1024 characters).

    Alerts are aggregates (a feature, a day, a month), so no personal data can appear here by construction.
    """

    def num(x: float) -> str:
        return f"{x:.3f}" if abs(x) < 1 else f"{x:.0f}"

    lines = [
        f"[SIGAP] {KIND_LABEL_ID[alert.kind]} · {alert.severity.upper()}",
        f"Subjek: {alert.subject} · bulan {alert.month}",
        f"Nilai: {num(alert.value)} (batas {num(alert.threshold)})",
        f"Runbook: {runbook_base_url}#{alert.kind}",
    ]
    return "\n".join(lines)[:1024]
