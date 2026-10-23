"""Phase 7 · Scoring API (FastAPI).

Endpoints to build:
    GET  /health            -> {"status": "ok", "model_version": ...}   (503 if no model is loaded)
    POST /v1/score          body: ApplicationIn (+ optional header X-Application-Id)
                            -> ScoreOut: calibrated score, decision band, top 3 reason codes, latency
    GET  /v1/model          -> model version, threshold(s), feature list hash, gate result, trained_at

Production requirements (each one is an interview question):
  - Load the model ONCE at startup (lifespan), from models/current/ (only gate-passed models land there).
  - Same preprocessing as training: import the silver/feature functions, never copy-paste them.
  - API key in header X-API-Key compared with secrets.compare_digest; key from env SIGAP_API_KEY.
  - Log every decision to Postgres decision_log (application_id, model_version, score, decision, reasons).
    Never log raw personal fields.
  - Latency budget: p95 < 100 ms on your Mac for one application (measure with scripts/load_test.py, phase 7).
  - Errors: 422 for invalid input (Pydantic does it), 401 for a bad key, 503 when the model is missing.

Run:  make serve   then open http://127.0.0.1:8000/docs
"""

from __future__ import annotations

# TODO(Agatha) phase 7: create `app = FastAPI(...)` with a lifespan that loads the model, and the endpoints above.
