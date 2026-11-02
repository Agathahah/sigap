"""Where alerts, cases and decisions live.

`OpsStore` is the interface the API depends on. Two implementations:
  InMemoryStore  used by the tests and by `make ops-demo` (build the n8n workflows without a database)
  PostgresStore  the real one, over the tables in sql/warehouse/003_ops.sql

The API logic (validation, state machine, idempotency) is tested without a database; both stores behave the same.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import pandas as pd

from sigap.ops.alerts import Alert

MIRROR_CHANNELS = ("telegram",)  # receipts only; ops.alert.acked_at stays the primary (n8n) acknowledgement


class OpsStore(Protocol):
    def add_alerts(self, alerts: list[Alert]) -> int: ...
    def list_open_alerts(self, channel: str | None = None) -> list[Alert]: ...
    def ack_alert(self, alert_key: str, channel: str) -> bool: ...
    def add_cases(self, cases: pd.DataFrame) -> int: ...
    def list_cases(self, status: str | None = None, limit: int = 20) -> list[dict]: ...
    def get_case(self, case_id: str) -> dict | None: ...
    def last_decision(self, case_id: str) -> dict | None: ...
    def save_decision(self, case_id: str, outcome: str, analyst_id: str, note: str | None, new_status: str) -> dict: ...


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class InMemoryStore:
    """Plain dictionaries; the same behaviour as PostgresStore."""

    def __init__(self) -> None:
        self.alerts: dict[str, Alert] = {}
        self.acks: dict[str, dict] = {}
        self.deliveries: dict[tuple[str, str], str] = {}
        self.cases: dict[str, dict] = {}
        self.decisions: list[dict] = []

    # alerts
    def add_alerts(self, alerts: list[Alert]) -> int:
        new = 0
        for a in alerts:
            if a.alert_key not in self.alerts:
                self.alerts[a.alert_key] = a
                new += 1
        return new

    def list_open_alerts(self, channel: str | None = None) -> list[Alert]:
        """No channel: not acknowledged on the primary channel. A channel: not yet delivered on that channel."""
        if channel is None:
            return [a for k, a in self.alerts.items() if k not in self.acks]
        return [a for k, a in self.alerts.items() if (k, channel) not in self.deliveries]

    def ack_alert(self, alert_key: str, channel: str) -> bool:
        if alert_key not in self.alerts:
            return False
        self.deliveries.setdefault((alert_key, channel), _now())
        if channel not in MIRROR_CHANNELS:
            self.acks.setdefault(alert_key, {"channel": channel, "acked_at": _now()})
        return True

    # cases
    def add_cases(self, cases: pd.DataFrame) -> int:
        new = 0
        for row in cases.to_dict("records"):
            if row["case_id"] not in self.cases:
                self.cases[row["case_id"]] = dict(row)
                new += 1
        return new

    def list_cases(self, status: str | None = None, limit: int = 20) -> list[dict]:
        rows = [c for c in self.cases.values() if status is None or c.get("status") == status]
        rows.sort(key=lambda c: (str(c.get("day")), c.get("priority", 0), c["case_id"]))
        return [dict(c) for c in rows[:limit]]

    def get_case(self, case_id: str) -> dict | None:
        c = self.cases.get(case_id)
        return dict(c) if c else None

    def last_decision(self, case_id: str) -> dict | None:
        for d in reversed(self.decisions):
            if d["case_id"] == case_id:
                return dict(d)
        return None

    def save_decision(self, case_id: str, outcome: str, analyst_id: str, note: str | None, new_status: str) -> dict:
        rec = {
            "case_id": case_id,
            "outcome": outcome,
            "analyst_id": analyst_id,
            "note": note,
            "status": new_status,
            "decided_at": _now(),
        }
        self.decisions.append(rec)
        self.cases[case_id]["status"] = new_status
        return dict(rec)


ALERT_COLUMNS = ("alert_key", "kind", "severity", "month", "subject", "value", "threshold")
CASE_COLUMNS = ("case_id", "application_id", "month", "day", "score", "decision_band", "reasons", "priority", "status")


class PostgresStore:
    """OpsStore over Postgres (sql/warehouse/003_ops.sql). Parameterized SQL only; one transaction per write."""

    def __init__(self, engine) -> None:  # noqa: ANN001 - a SQLAlchemy engine
        self.engine = engine

    def _rows(self, sql: str, **params) -> list[dict]:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    # alerts
    def add_alerts(self, alerts: list[Alert]) -> int:
        from sqlalchemy import text

        if not alerts:
            return 0
        rows = [{c: getattr(a, c) for c in ALERT_COLUMNS} for a in alerts]
        sql = text(
            "INSERT INTO ops.alert (alert_key, kind, severity, month, subject, value, threshold) "
            "VALUES (:alert_key, :kind, :severity, :month, :subject, :value, :threshold) "
            "ON CONFLICT (alert_key) DO NOTHING RETURNING alert_key"
        )
        with self.engine.begin() as conn:
            return sum(len(conn.execute(sql, row).fetchall()) for row in rows)

    def list_open_alerts(self, channel: str | None = None) -> list[Alert]:
        """No channel: not acknowledged on the primary channel. A channel: no delivery receipt on that channel."""
        cols = "a.alert_key, a.kind, a.severity, a.month, a.subject, a.value, a.threshold"
        order = "ORDER BY CASE a.severity WHEN 'high' THEN 0 ELSE 1 END, a.kind, a.subject"
        if channel is None:
            rows = self._rows(f"SELECT {cols} FROM ops.alert a WHERE a.acked_at IS NULL {order}")  # noqa: S608
        else:
            rows = self._rows(
                f"SELECT {cols} FROM ops.alert a WHERE NOT EXISTS (SELECT 1 FROM ops.alert_delivery d "  # noqa: S608
                f"WHERE d.alert_key = a.alert_key AND d.channel = :ch) {order}",
                ch=channel,
            )
        return [Alert(**r) for r in rows]

    def ack_alert(self, alert_key: str, channel: str) -> bool:
        from sqlalchemy import text

        with self.engine.begin() as conn:
            exists = conn.execute(text("SELECT 1 FROM ops.alert WHERE alert_key = :k"), {"k": alert_key}).first()
            if not exists:
                return False
            conn.execute(
                text(
                    "INSERT INTO ops.alert_delivery (alert_key, channel) VALUES (:k, :ch) "
                    "ON CONFLICT (alert_key, channel) DO NOTHING"
                ),
                {"k": alert_key, "ch": channel},
            )
            if channel not in MIRROR_CHANNELS:
                conn.execute(
                    text(
                        "UPDATE ops.alert SET acked_at = now(), channel = :ch WHERE alert_key = :k AND acked_at IS NULL"
                    ),
                    {"k": alert_key, "ch": channel},
                )
        return True

    # cases
    def add_cases(self, cases: pd.DataFrame) -> int:
        from sqlalchemy import text

        if cases.empty:
            return 0
        rows = cases[list(CASE_COLUMNS)].to_dict("records")
        for r in rows:
            r["reasons"] = list(r["reasons"])
        sql = text(
            "INSERT INTO ops.review_case (case_id, application_id, month, day, score, decision_band, reasons, "
            "priority, status) VALUES (:case_id, :application_id, :month, :day, :score, :decision_band, :reasons, "
            ":priority, :status) ON CONFLICT (case_id) DO NOTHING"
        )
        with self.engine.begin() as conn:
            before = conn.execute(text("SELECT count(*) FROM ops.review_case")).scalar_one()
            conn.execute(sql, rows)
            after = conn.execute(text("SELECT count(*) FROM ops.review_case")).scalar_one()
        return int(after - before)

    def list_cases(self, status: str | None = None, limit: int = 20) -> list[dict]:
        where = "WHERE status = :status" if status else ""
        return self._rows(
            f"SELECT {', '.join(CASE_COLUMNS)} FROM ops.review_case {where} "  # noqa: S608 - fixed column list
            "ORDER BY day, priority, case_id LIMIT :limit",
            status=status,
            limit=limit,
        )

    def get_case(self, case_id: str) -> dict | None:
        rows = self._rows(
            f"SELECT {', '.join(CASE_COLUMNS)} FROM ops.review_case WHERE case_id = :id",  # noqa: S608
            id=case_id,
        )
        return rows[0] if rows else None

    def last_decision(self, case_id: str) -> dict | None:
        rows = self._rows(
            "SELECT case_id, outcome, analyst_id, note, status_after AS status, decided_at FROM ops.review_decision "
            "WHERE case_id = :id ORDER BY decided_at DESC, decision_id DESC LIMIT 1",
            id=case_id,
        )
        return rows[0] if rows else None

    def save_decision(self, case_id: str, outcome: str, analyst_id: str, note: str | None, new_status: str) -> dict:
        from sqlalchemy import text

        with self.engine.begin() as conn:  # the audit row and the status change succeed or fail together
            row = conn.execute(
                text(
                    "INSERT INTO ops.review_decision (case_id, outcome, analyst_id, note, status_after) "
                    "VALUES (:c, :o, :a, :n, :s) RETURNING decided_at"
                ),
                {"c": case_id, "o": outcome, "a": analyst_id, "n": note, "s": new_status},
            ).one()
            conn.execute(
                text("UPDATE ops.review_case SET status = :s WHERE case_id = :c"), {"s": new_status, "c": case_id}
            )
        return {
            "case_id": case_id,
            "outcome": outcome,
            "analyst_id": analyst_id,
            "note": note,
            "status": new_status,
            "decided_at": row.decided_at.isoformat(timespec="seconds"),
        }


def get_store() -> OpsStore:
    """FastAPI dependency. SIGAP_OPS_STORE=memory (demo, tests) or postgres (default)."""
    import os

    global _STORE
    if _STORE is None:
        if os.getenv("SIGAP_OPS_STORE", "postgres") == "memory":
            _STORE = InMemoryStore()
        else:
            from sqlalchemy import create_engine

            from sigap.config import database_url

            _STORE = PostgresStore(create_engine(database_url()))
    return _STORE


_STORE: OpsStore | None = None
