# Phase 7 · API image. TODO(Agatha): write it, then `make docker-build && make docker-run`.
# Checklist (each line is an interview question: "why?"):
#   - FROM python:3.12-slim (small; no Spark/Java in the serving image)
#   - non-root user
#   - copy requirements-serve.txt first and pip install --no-cache-dir (layer caching)
#   - copy src/ and configs/ only (no data/, no notebooks)
#   - the model is mounted read-only at /app/models/current, not baked in (swap models without rebuilding)
#   - EXPOSE 8000, HEALTHCHECK on /health, CMD uvicorn sigap.serve.app:app --host 0.0.0.0 --port 8000
