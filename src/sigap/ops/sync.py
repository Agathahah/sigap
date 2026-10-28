"""Refresh alerts and review cases for one month from the warehouse (runs after `make replay`).

  1. drift: PSI rows of the month from ops.monitoring_monthly (score and features)
  2. data quality: the month's quarantine rate from reports/quality/<variant>.csv
  3. review cases: the month's "review" decisions in ops.decision_log (latest model version), case_id
     "case-<application_id>", a day of the month and the score and reason codes of the decision
  4. assign_cases with the daily capacity; 5. queue = reviews per day; 6. build_alerts; 7. store both

BAF has no application date, so each application gets a deterministic day of its month (from its id) and the
months are placed on a 2026 calendar (month 0 = January). The daily capacity is the review share the team can
handle (business.yaml max_review_rate) times that day's application volume, so the queue is judged against the
volume actually replayed.

Idempotent: case ids and alert keys are stable, so a second run inserts nothing new.

Run:   make ops-sync M=6
Airflow: task `ops_sync` after `replay` in dags/sigap_monthly.py.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import date

import pandas as pd

from sigap import config


def day_of_month(application_id: str, month: int, days: int = 28) -> date:
    """Deterministic calendar day for an application (BAF has no dates): month 0 = January 2026."""
    offset = int(hashlib.sha1(application_id.encode(), usedforsecurity=False).hexdigest()[:8], 16) % days
    return date(2026, month + 1, offset + 1)


def quarantine_rate(slug: str, month: int) -> pd.DataFrame:
    path = config.REPORTS / "quality" / f"{slug}.csv"
    if not path.exists():
        return pd.DataFrame(columns=["month", "quarantine_rate"])
    q = pd.read_csv(path)
    q = q[q["month"] == month]
    return pd.DataFrame({"month": q["month"], "quarantine_rate": q["quarantined"] / q["rows"]})


def read_month(conn, month: int) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Drift rows, review decisions (latest model version) and the number of applications of the month."""
    drift = pd.DataFrame(
        conn.execute(
            "SELECT month, feature, value AS psi FROM ops.monitoring_monthly WHERE month = %s AND metric = 'psi'",
            (month,),
        ).fetchall(),
        columns=["month", "feature", "psi"],
    )
    rows = conn.execute(
        "WITH latest AS (SELECT model_version FROM ops.decision_log ORDER BY decided_at DESC LIMIT 1) "
        "SELECT l.application_id, l.score, l.decision, l.reasons "
        "FROM ops.decision_log l JOIN latest USING (model_version) "
        "JOIN gold.fact_application f USING (application_id) JOIN gold.dim_month d USING (month_key) "
        "WHERE d.month_index = %s",
        (month,),
    ).fetchall()
    decisions = pd.DataFrame(rows, columns=["application_id", "score", "decision", "reasons"])
    return drift, decisions, len(decisions)


def build_cases(decisions: pd.DataFrame, month: int, review_share: float) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    from sigap.ops.cases import assign_cases

    decisions = decisions.assign(day=[day_of_month(a, month) for a in decisions["application_id"]])
    per_day = decisions.groupby("day").size()
    capacity = int(round(review_share * per_day.mean())) if len(per_day) else 0
    reviews = decisions[decisions["decision"] == "review"]
    reviews = pd.DataFrame(
        {
            "case_id": "case-" + reviews["application_id"],
            "application_id": reviews["application_id"],
            "month": month,
            "day": reviews["day"],
            "score": reviews["score"].astype(float),
            "decision_band": "review",
            "reasons": reviews["reasons"],
        }
    )
    cases = assign_cases(reviews, capacity)
    queue = cases.groupby("day").size().rename("review_count").reset_index().assign(month=month)
    return cases, queue, capacity


def main(month: int) -> None:
    import psycopg
    from sqlalchemy import create_engine

    from sigap.ops.alerts import build_alerts
    from sigap.ops.store import PostgresStore

    slug = config.VARIANT.lower().replace(" ", "_")
    biz, ops_cfg = config.load_yaml("business"), config.load_yaml("ops")
    dsn = config.database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn) as conn:
        drift, decisions, n_apps = read_month(conn, month)
    if decisions.empty:
        raise SystemExit(f"no decisions for month {month}: run `make replay` first")
    cases, queue, capacity = build_cases(decisions, month, float(biz["max_review_rate"]))
    cfg = {
        "psi_alert": ops_cfg["psi_alert"],
        "queue_tolerance": ops_cfg.get("queue_tolerance", 0.0),
        "quarantine_rate_alert": ops_cfg["quarantine_rate_alert"],
        "review_capacity_per_day": capacity,
    }
    alerts = build_alerts(drift, queue, quarantine_rate(slug, month), cfg)
    store = PostgresStore(create_engine(config.database_url()))
    new_cases, new_alerts = store.add_cases(cases), store.add_alerts(alerts)

    backlog = int((cases["status"] == "backlog").sum())
    print(f"month {month}: {n_apps:,} applications, {len(cases):,} review cases over {queue['day'].nunique()} days")
    print(
        f"  capacity {capacity}/day ({biz['max_review_rate']:.0%} of the daily volume); assigned "
        f"{len(cases) - backlog:,}, backlog {backlog:,}; days over capacity {(queue['review_count'] > capacity).sum()}"
    )
    print(
        f"  alerts: {len(alerts)} ({', '.join(f'{a.kind}:{a.subject}' for a in alerts[:6]) or 'none'}"
        f"{' ...' if len(alerts) > 6 else ''})"
    )
    print(f"  stored: {new_cases:,} new cases, {new_alerts} new alerts (0 on a re-run: idempotent)")


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        raise SystemExit("usage: make ops-sync M=6")
    main(int(sys.argv[1]))
