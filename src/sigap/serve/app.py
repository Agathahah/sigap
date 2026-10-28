"""Scoring API (FastAPI).

    GET  /health      -> {"status": "ok", "model_version": ...}; 503 when no model is loaded
    POST /v1/score    body: ApplicationIn (+ optional header X-Application-Id), header X-API-Key
                      -> ScoreOut: calibrated score, decision band, top 3 reason codes, latency
    GET  /v1/model    -> version, thresholds, feature-list hash, gate result, trained_at

Design:
  - The model, the decision bands and the prior-rate lookup are loaded once at startup from models/current/
    (only gate-passed models land there). Without them the service reports 503 instead of guessing.
  - Preprocessing is the training code (sigap.features.build.serving_frame), not a copy.
  - The API key is compared with secrets.compare_digest (constant time); it comes from SIGAP_API_KEY.
  - Each decision is written to ops.decision_log after the response is sent (application id, model version,
    score, decision, reason codes). Raw personal fields are never logged. SIGAP_DECISION_LOG=0 turns it off.

Run:  make serve   then open http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException

from sigap import config
from sigap.serve.schemas import ApplicationIn, ModelInfo, ScoreOut

log = logging.getLogger("sigap.api")
STATE: dict = {}


def model_dir() -> Path:
    return Path(os.getenv("SIGAP_MODEL_DIR", config.MODELS / "current"))


def load_serving_state(folder: Path) -> dict:
    """Everything a request needs, loaded once. Raises FileNotFoundError when an artefact is missing."""
    from sigap.features.build import load_feature_config
    from sigap.quality.contract import load_contract
    from sigap.train.model import load_model

    missing = [f for f in ("model.joblib", "policy.json", "prior_rates.json") if not (folder / f).exists()]
    if missing:
        raise FileNotFoundError(f"{folder} is missing {', '.join(missing)} (make train, make policy, make serve-prep)")
    model = load_model(folder)
    policy = json.loads((folder / "policy.json").read_text())
    priors = json.loads((folder / "prior_rates.json").read_text())
    numeric, categories, cfg = load_feature_config()
    sentinels = load_contract(config.CONFIGS / "data_contract.yaml")["sentinels"]
    t_decline = policy.get("t_decline")
    return {
        "model": model,
        "numeric": numeric,
        "categories": categories,
        "sentinels": sentinels,
        "priors": priors,
        "t_review": float(policy["t_review"]),
        "t_decline": float("inf") if t_decline is None else float(t_decline),
        "feature_sha": hashlib.sha256(",".join(model.features).encode()).hexdigest(),
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        STATE.update(load_serving_state(model_dir()))
        log.info("model %s loaded", STATE["model"].version)
    except FileNotFoundError as exc:
        log.error("no model loaded: %s", exc)
    yield
    STATE.clear()


app = FastAPI(title="SIGAP scoring API", version="1.0", lifespan=lifespan)


def require_model() -> dict:
    if "model" not in STATE:
        raise HTTPException(status_code=503, detail="no model loaded")
    return STATE


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("SIGAP_API_KEY", "")
    if not expected or not x_api_key or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def score_frame(raw: pd.DataFrame, state: dict) -> tuple[np.ndarray, pd.DataFrame]:
    """Calibrated scores and the model matrix for raw applications (also used by batch scoring)."""
    from sigap.features.build import serving_frame

    X = serving_frame(raw, state["numeric"], state["categories"], state["priors"]["tables"], state["sentinels"])
    return state["model"].score(X), X


def log_decision(application_id: str, version: str, score: float, decision: str, reasons: list[str]) -> None:
    """Append one row to ops.decision_log; failures are logged, never raised to the caller."""
    if os.getenv("SIGAP_DECISION_LOG", "1") == "0":
        return
    try:
        import psycopg

        dsn = config.database_url().replace("postgresql+psycopg://", "postgresql://", 1)
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute(
                "INSERT INTO ops.decision_log (application_id, model_version, score, decision, reasons) "
                "VALUES (%s, %s, %s, %s, %s)",
                (application_id, version, score, decision, reasons),
            )
    except Exception as exc:  # noqa: BLE001 - logging must not break scoring
        log.warning("decision not logged for %s: %s", application_id, exc)


@app.get("/health")
def health() -> dict:
    if "model" not in STATE:
        raise HTTPException(status_code=503, detail="no model loaded")
    return {"status": "ok", "model_version": STATE["model"].version}


@app.post("/v1/score", response_model=ScoreOut, dependencies=[Depends(require_key)])
def score(
    application: ApplicationIn,
    background: BackgroundTasks,
    x_application_id: str | None = Header(default=None),
    state: dict = Depends(require_model),
) -> ScoreOut:
    from sigap.explain.reasons import analyst_reasons
    from sigap.policy.cost import decide

    started = time.perf_counter()
    raw = pd.DataFrame([application.model_dump()])
    p, X = score_frame(raw, state)
    decision = str(decide(p, state["t_review"], state["t_decline"])[0])
    reasons = analyst_reasons(state["model"].contributions(X).iloc[0].to_dict()) if decision != "approve" else []
    app_id = x_application_id or f"api-{uuid.uuid4().hex[:12]}"
    version = state["model"].version
    background.add_task(log_decision, app_id, version, float(p[0]), decision, reasons)
    return ScoreOut(
        application_id=app_id,
        score=float(p[0]),
        decision=decision,
        reasons=reasons,
        model_version=version,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


@app.get("/v1/model", response_model=ModelInfo, dependencies=[Depends(require_key)])
def model_info(state: dict = Depends(require_model)) -> ModelInfo:
    m = state["model"]
    return ModelInfo(
        model_version=m.version,
        candidate=m.metadata.get("candidate"),
        trained_at=m.metadata.get("trained_at"),
        threshold=m.threshold,
        t_review=state["t_review"],
        t_decline=None if np.isinf(state["t_decline"]) else state["t_decline"],
        features=len(m.features),
        feature_list_sha256=state["feature_sha"],
        prior_rates_as_of_month=state["priors"]["as_of_month"],
        gate_passed=m.metadata.get("gate_passed"),
    )
