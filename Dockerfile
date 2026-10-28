# Scoring API image: `make docker-build && make docker-run`.
FROM python:3.12-slim

# XGBoost needs the OpenMP runtime (libgomp); slim images do not ship it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    SIGAP_ROOT=/app \
    SIGAP_MODEL_DIR=/app/models/current

WORKDIR /app

# Dependencies first: this layer is rebuilt only when requirements-serve.txt changes.
COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

# Code and configuration only: no data, notebooks or models (the model is mounted read-only at run time).
COPY src/ src/
COPY configs/ configs/
# Files keep their host permissions when copied; make the code readable (not writable) for the app user.
RUN chmod -R a+rX /app/src /app/configs

RUN useradd --create-home --uid 10001 sigap
USER sigap

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "sigap.serve.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
