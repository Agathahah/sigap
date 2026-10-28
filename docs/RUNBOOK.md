# Runbook

## Monthly job (Airflow DAG sigap_monthly)
_order of tasks, how to re-run one month, where logs are_

## Alerts and what to do
| Signal | Threshold | First check | Action |
|---|---|---|---|
| Quarantine rate | _> x%_ | _source system change?_ | _hold the month, contact source owner_ |
| Score PSI | > 0.25 | _which feature drifted?_ | _retraining ticket; consider tightening review band_ |
| TPR at operating threshold | _drop > 10 pts_ | _label completeness_ | _retrain / fall back to rules_ |
| API p95 latency | > 100 ms | `make load-test`: server-side vs round-trip time; container CPU and memory | add workers or replicas; if the API is down, route to the rules (Fallback) |

## Alert routing (phase 8b, n8n)
| Alert kind | Goes to | Expected first action | Silence rule |
|---|---|---|---|
| drift | _data science on duty_ | _check which feature; compare with quarantine report_ | _one message per key (alert_key)_ |
| queue_over_capacity | _fraud ops lead_ | _move analysts / tighten review band temporarily (phase 6 memo)_ | |
| data_incident | _source-system owner_ | _hold the month; do not retrain on it_ | |

If n8n is down: alerts stay in ops.alert (acked_at NULL) and are sent when it comes back; nothing is lost.

## Scoring API
- **Start (development):** `make serve` → http://127.0.0.1:8000/docs. **Start (container):** `make docker-build`
  then `make docker-run`; the model folder is mounted read-only, so a new model needs a restart, not a rebuild.
- **Health:** `GET /health`. A 503 means no model is loaded: `models/current/` must hold `model.joblib`,
  `policy.json` (bands from `make policy`) and `prior_rates.json` (`make serve-prep`).
- **New model:** `make train` (copies to `models/current/` only if the gate passes and writes the prior-rate
  lookup) → `make policy` → restart the API → `GET /v1/model` shows the new version.
- **API key:** `SIGAP_API_KEY` in `.env` (`make env-secrets` generates one); restart after changing it.
- **Decision log:** every decision is appended to `ops.decision_log` after the response. If Postgres is down the
  API keeps scoring and logs a warning; decisions from that window are missing from the log.
- **Latency:** measured with `make load-test` (500 sequential requests, one application each). 28 Oct 2026,
  MacBook Air (Apple silicon), API in the Docker container (`make docker-run`, 2 workers): round trip p50 8.8 ms,
  p95 12.3 ms, p99 29.2 ms; server side p95 9.3 ms; 0 errors. Target p95 < 100 ms.

## Fallback
_If the model or API is down: rules-only policy from configs/rules.yaml (champion)._
