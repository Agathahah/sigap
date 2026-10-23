"""Phase 8b · Where alerts, cases and decisions live.

`OpsStore` is the interface the API depends on. Two implementations:
  InMemoryStore  provided: used by the tests and by `make ops-demo` (lets you build the n8n workflows
                 before the model exists)
  PostgresStore  TODO(Agatha): the real one, over the tables in sql/warehouse/003_ops.sql

Why an interface: the API logic (validation, state machine, idempotency) is tested without a database, and the
same tests protect the Postgres version once you write it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import pandas as pd

from sigap.ops.alerts import Alert


class OpsStore(Protocol):
    def add_alerts(self, alerts: list[Alert]) -> int: ...
    def list_open_alerts(self) -> list[Alert]: ...
    def ack_alert(self, alert_key: str, channel: str) -> bool: ...
    def add_cases(self, cases: pd.DataFrame) -> int: ...
    def list_cases(self, status: str | None = None, limit: int = 20) -> list[dict]: ...
    def get_case(self, case_id: str) -> dict | None: ...
    def last_decision(self, case_id: str) -> dict | None: ...
    def save_decision(self, case_id: str, outcome: str, analyst_id: str, note: str | None, new_status: str) -> dict: ...


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class InMemoryStore:
    """Provided. Plain dictionaries; same behaviour the PostgresStore must have."""

    def __init__(self) -> None:
        self.alerts: dict[str, Alert] = {}
        self.acks: dict[str, dict] = {}
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

    def list_open_alerts(self) -> list[Alert]:
        return [a for k, a in self.alerts.items() if k not in self.acks]

    def ack_alert(self, alert_key: str, channel: str) -> bool:
        if alert_key not in self.alerts:
            return False
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


class PostgresStore:
    """Phase 8b · TODO(Agatha): OpsStore over Postgres (tables in sql/warehouse/003_ops.sql).

    - Constructor takes a SQLAlchemy engine (sigap.config.database_url()).
    - add_alerts: INSERT ... ON CONFLICT (alert_key) DO NOTHING; return the number inserted.
    - ack_alert: set acked_at/channel only if still NULL (idempotent); False if the key does not exist.
    - save_decision: INSERT into ops.review_decision AND UPDATE ops.review_case.status in ONE transaction.
    - Parameterized queries only (text() with bind params), never f-strings with values.
    Integration test (runs only when SIGAP_TEST_DB is set): tests/test_p8b_ops.py::test_postgres_store_roundtrip
    """

    def __init__(self, engine) -> None:  # noqa: ANN001
        raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.store.PostgresStore")


def get_store() -> OpsStore:
    """Provided. FastAPI dependency. SIGAP_OPS_STORE=memory (demo/tests) or postgres (default)."""
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
