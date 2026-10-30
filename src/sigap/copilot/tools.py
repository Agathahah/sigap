"""Phase 9 · Read-only tools the copilot may call. They are the only way it touches data (ADR 0003).

Rules:
  - The copilot connects as `sigap_copilot` (sql/warehouse/005_copilot.sql): SELECT on the copilot views only,
    read-only transactions, 5 s statement timeout. Protected attributes are not in any view.
  - No free-form SQL from the model. Each tool runs a fixed, parameterized query; arguments are validated
    against allowlists and ranges before the query runs. Column names come from the allowlists only.
  - Every tool returns small JSON (aggregates or top-k rows) with numbers rounded to 4 decimals, so the
    answer can quote them exactly and the grounding check can verify them.

The functions are plain Python and can be called without an LLM, e.g. from `PYTHONPATH=src .venv/bin/python`:
    >>> from sigap.copilot.tools import query_kpi
    >>> print(query_kpi("fraud_rate", "device_os"))
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from sigap import config

METRICS = {
    "fraud_rate": "share of applications that turned out to be fraud (fully labelled months only)",
    "approve_rate": "share of scored applications approved",
    "review_rate": "share of scored applications sent to manual review",
    "decline_rate": "share of scored applications declined",
    "alert_rate": "share of scored applications reviewed or declined",
}
GROUP_BY = ("month", "device_os", "payment_type", "source", "housing_status", "email_is_free")
MONTH_RANGE = (0, 12)
_APP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SIMILARITY_FEATURES = (
    "name_email_similarity",
    "velocity_6h",
    "velocity_4w",
    "credit_risk_score",
    "proposed_credit_limit",
    "session_length_in_minutes",
    "device_distinct_emails_8w",
    "current_address_months_count",
    "date_of_birth_distinct_emails_4w",
    "zip_count_4w",
)
APPLICATION_FIELDS = (
    "application_id",
    "month",
    "source",
    "payment_type",
    "device_os",
    "housing_status",
    "email_is_free",
    "keep_alive_session",
    "name_email_similarity",
    "prev_address_months_count",
    "current_address_months_count",
    "velocity_6h",
    "velocity_4w",
    "credit_risk_score",
    "proposed_credit_limit",
    "foreign_request",
    "phone_home_valid",
    "session_length_in_minutes",
    "device_distinct_emails_8w",
    "date_of_birth_distinct_emails_4w",
)
MAX_TEXT = 900


# ---------- connection and helpers ----------
def copilot_dsn() -> str:
    """libpq URL for the read-only role: host, port and database from SIGAP_DB_URL, password from
    SIGAP_COPILOT_DB_PASSWORD. Set SIGAP_COPILOT_DB_URL to override (e.g. a separate replica)."""
    from sqlalchemy.engine import make_url

    if os.getenv("SIGAP_COPILOT_DB_URL"):
        return os.environ["SIGAP_COPILOT_DB_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    password = os.getenv("SIGAP_COPILOT_DB_PASSWORD")
    if not password or "change-me" in password:
        raise RuntimeError("SIGAP_COPILOT_DB_PASSWORD is not set: run make env-secrets, then make copilot-db")
    url = make_url(config.database_url()).set(drivername="postgresql", username="sigap_copilot", password=password)
    return url.render_as_string(hide_password=False)


def _rows(sql: Any, params: tuple | dict = ()) -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(copilot_dsn(), connect_timeout=5, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def _clean(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def _json(obj: Any) -> str:
    def walk(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return _clean(o)

    return json.dumps(walk(obj), ensure_ascii=False, default=str)


def _month(value: int | None, default: int) -> int:
    m = default if value is None else int(value)
    if not MONTH_RANGE[0] <= m <= MONTH_RANGE[1]:
        raise ValueError(f"month must be between {MONTH_RANGE[0]} and {MONTH_RANGE[1]}, got {m}")
    return m


def _app_id(application_id: str) -> str:
    if not isinstance(application_id, str) or not _APP_ID.match(application_id):
        raise ValueError("application_id must look like 'base-0761240' (letters, digits, '-' or '_')")
    return application_id


# ---------- tools ----------
def query_kpi(metric: str, group_by: str = "month", month_from: int | None = None, month_to: int | None = None) -> str:
    """Rate of one metric per group, from the warehouse and the decision log.

    metric: fraud_rate | approve_rate | review_rate | decline_rate | alert_rate
    group_by: month | device_os | payment_type | source | housing_status | email_is_free
    month_from / month_to: optional month range 0-12 (inclusive). fraud_rate only covers fully labelled months.
    """
    from psycopg import sql

    if metric not in METRICS:
        raise ValueError(f"metric must be one of {sorted(METRICS)}")
    if group_by not in GROUP_BY:
        raise ValueError(f"group_by must be one of {list(GROUP_BY)}")
    lo, hi = _month(month_from, MONTH_RANGE[0]), _month(month_to, MONTH_RANGE[1])
    if lo > hi:
        raise ValueError("month_from must be <= month_to")
    g = sql.Identifier(group_by)
    if metric == "fraud_rate":
        q = sql.SQL(
            "SELECT a.{g} AS grp, count(*) AS n, avg(a.is_fraud) AS rate FROM copilot.v_application a "
            "WHERE a.label_complete AND a.month BETWEEN %s AND %s GROUP BY 1 ORDER BY 1 LIMIT 20"
        ).format(g=g)
        params: tuple = (lo, hi)
    else:
        condition = {
            "approve_rate": "d.decision = 'approve'",
            "review_rate": "d.decision = 'review'",
            "decline_rate": "d.decision = 'decline'",
            "alert_rate": "d.decision IN ('review', 'decline')",
        }[metric]
        q = sql.SQL(
            "SELECT a.{g} AS grp, count(*) AS n, avg(CASE WHEN " + condition + " THEN 1.0 ELSE 0.0 END) AS rate "
            "FROM copilot.v_decision d JOIN copilot.v_application a USING (application_id) "
            "WHERE a.month BETWEEN %s AND %s GROUP BY 1 ORDER BY 1 LIMIT 20"
        ).format(g=g)
        params = (lo, hi)
    rows = _rows(q, params)
    return _json(
        {
            "metric": metric,
            "definition": METRICS[metric],
            "group_by": group_by,
            "months": [lo, hi],
            "rows": [{"group": r["grp"], "n": r["n"], "rate": float(r["rate"])} for r in rows],
        }
    )


def get_application(application_id: str) -> str:
    """One application: channel, device and model inputs (no protected attributes), the latest scoring decision
    with its reason codes, the review case if there is one, and the label if it has arrived."""
    from psycopg import sql

    app_id = _app_id(application_id)
    cols = sql.SQL(", ").join(sql.Identifier(c) for c in (*APPLICATION_FIELDS, "is_fraud"))
    found = _rows(sql.SQL("SELECT {} FROM copilot.v_application WHERE application_id = %s").format(cols), (app_id,))
    if not found:
        return _json({"application_id": app_id, "error": "application not found in the warehouse"})
    app = dict(found[0])
    label = app.pop("is_fraud")
    decision = _rows(
        "SELECT score, decision, reasons, model_version, decided_at FROM copilot.v_decision WHERE application_id = %s",
        (app_id,),
    )
    case = _rows(
        "SELECT case_id, day, status, priority FROM copilot.v_review_case WHERE application_id = %s", (app_id,)
    )
    return _json(
        {
            "application": app,
            "decision": decision[0] if decision else None,
            "review_case": case[0] if case else None,
            "label": {None: "not known yet (labels arrive 2 months later)", 0: "not fraud", 1: "fraud"}[label],
        }
    )


def similar_cases(application_id: str, k: int = 5) -> str:
    """The k most similar earlier applications whose outcome is known (same device_os and payment_type,
    earlier months only, distance on z-scored model inputs). k between 1 and 20."""
    from psycopg import sql

    app_id = _app_id(application_id)
    k = int(k)
    if not 1 <= k <= 20:
        raise ValueError("k must be between 1 and 20")
    f = [sql.Identifier(c) for c in SIMILARITY_FEATURES]
    stats = sql.SQL(", ").join(
        sql.SQL("avg(p.{c}) AS {m}, nullif(stddev_pop(p.{c}), 0) AS {s}").format(
            c=c, m=sql.Identifier(f"m_{n}"), s=sql.Identifier(f"s_{n}")
        )
        for c, n in zip(f, SIMILARITY_FEATURES, strict=True)
    )
    dist = sql.SQL(" + ").join(
        sql.SQL("coalesce(((coalesce(p.{c}, st.{m}) - coalesce(t.{c}, st.{m})) / st.{s})^2, 0)").format(
            c=c, m=sql.Identifier(f"m_{n}"), s=sql.Identifier(f"s_{n}")
        )
        for c, n in zip(f, SIMILARITY_FEATURES, strict=True)
    )
    q = sql.SQL(
        "WITH t AS (SELECT * FROM copilot.v_application WHERE application_id = %s), "
        "pool AS (SELECT a.* FROM copilot.v_application a, t WHERE a.month < t.month AND a.is_fraud IS NOT NULL "
        "AND a.device_os = t.device_os AND a.payment_type = t.payment_type), "
        "st AS (SELECT {stats} FROM pool p) "
        "SELECT p.application_id, p.month, p.is_fraud, sqrt({dist}) AS distance FROM pool p, t, st "
        "ORDER BY distance LIMIT %s"
    ).format(stats=stats, dist=dist)
    rows = _rows(q, (app_id, k))
    if not rows:
        return _json({"application_id": app_id, "neighbours": [], "note": "no earlier labelled applications"})
    frauds = sum(int(r["is_fraud"]) for r in rows)
    return _json(
        {
            "application_id": app_id,
            "pool": "earlier months, same device_os and payment_type, label known",
            "k": len(rows),
            "fraud_among_neighbours": frauds,
            "neighbours": [
                {
                    "application_id": r["application_id"],
                    "month": r["month"],
                    "outcome": "fraud" if r["is_fraud"] else "not fraud",
                    "distance": float(r["distance"]),
                }
                for r in rows
            ],
        }
    )


def search_policy(question: str, k: int = 4) -> str:
    """Passages from the policy documents (POJK 12/2024 anti-fraud, the bank's review SOP) that best match the
    question, each with its source file and page (or section) for citation. k between 1 and 6."""
    from sigap.copilot.rag import retrieve

    k = int(k)
    if not 1 <= k <= 6:
        raise ValueError("k must be between 1 and 6")
    chunks = retrieve(question, k=k, url=copilot_dsn())
    for c in chunks:
        c["text"] = c["text"][:MAX_TEXT]
    return _json({"question": question, "chunks": chunks})


def monitoring_status(month: int) -> str:
    """Monthly monitoring for one month (5-9 after the replay): decision rates, reviews per day against the review
    capacity, score PSI, recall and FPR once labels arrived, the age FPR ratio, the retraining flag, and the
    features with PSI >= 0.10."""
    m = _month(month, 0)
    kpis = _rows("SELECT * FROM copilot.v_monthly_kpis WHERE month = %s", (m,))
    if not kpis:
        return _json({"month": m, "error": "no monitoring for this month (the replay covers months 5-7, labels 8-9)"})
    drift = _rows(
        "SELECT feature, psi, status FROM copilot.v_feature_drift WHERE month = %s AND feature <> 'score' "
        "AND psi >= 0.10 ORDER BY psi DESC LIMIT 10",
        (m,),
    )
    return _json(
        {
            "month": m,
            "kpis": {k: v for k, v in kpis[0].items() if v is not None},
            "drifting_features": drift,
            "psi_thresholds": {"watch": 0.1, "alert": 0.25},
            "review_capacity_per_day": config.load_yaml("business")["review_capacity_per_day"],
        }
    )


TOOLS = (query_kpi, get_application, similar_cases, search_policy, monitoring_status)


def langchain_tools() -> list:
    """The same functions as LangChain tools (name and docstring are what the model reads)."""
    from langchain_core.tools import StructuredTool

    return [StructuredTool.from_function(fn) for fn in TOOLS]
