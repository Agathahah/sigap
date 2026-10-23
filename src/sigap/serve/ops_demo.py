"""Phase 8b · Demo ops API with an in-memory store and synthetic cases. Plumbing, provided.

Purpose: build and test the n8n workflows BEFORE the model and Postgres tables exist. Uses YOUR functions
(build_alerts, assign_cases and the router), so it only works once those tests are green.

Run:  make ops-demo      (http://127.0.0.1:8001/docs, store resets on every restart)
No real BAF rows here: application ids and scores are made up.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from fastapi import FastAPI

from sigap.ops import store as store_mod
from sigap.ops.alerts import build_alerts
from sigap.ops.cases import assign_cases
from sigap.serve.ops import router

DEMO_CFG = {"psi_alert": 0.25, "review_capacity_per_day": 5, "queue_tolerance": 0.0, "quarantine_rate_alert": 0.02}


def seed(store: store_mod.InMemoryStore, seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    days = ["2026-11-02", "2026-11-03"]
    reviews = pd.DataFrame(
        {
            "case_id": [f"case-{i:04d}" for i in range(14)],
            "application_id": [f"demo-{rng.integers(1e6, 9e6)}" for _ in range(14)],
            "day": [days[i % 2] for i in range(14)],
            "score": rng.uniform(0.2, 0.95, 14).round(3),
            "decision_band": "review",
        }
    )
    reviews["reasons"] = [["velocity_6h_high", "device_distinct_emails_8w", "name_email_similarity_low"]] * 14
    store.add_cases(assign_cases(reviews, capacity=DEMO_CFG["review_capacity_per_day"]))
    drift = pd.DataFrame({"month": [6, 6], "feature": ["score", "velocity_6h"], "psi": [0.31, 0.12]})
    queue = reviews.groupby("day").size().rename("review_count").reset_index().assign(month=6)
    quality = pd.DataFrame({"month": [6], "quarantine_rate": [0.004]})
    store.add_alerts(build_alerts(drift, queue, quality, DEMO_CFG))


os.environ.setdefault("SIGAP_OPS_STORE", "memory")
app = FastAPI(title="SIGAP ops (demo, in-memory)")
app.include_router(router)
seed(store_mod.get_store())  # type: ignore[arg-type]
