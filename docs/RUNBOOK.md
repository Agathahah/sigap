# Runbook

## Monthly job (Airflow DAG sigap_monthly)
Order: `quality → bronze → silver → gold → features → replay(month) → ops_sync(month)`. Every task is a `make`
target and is idempotent (partitions overwritten, gold upserted, a month's replay rows replaced), so a failed or
repeated month is simply re-run.

- **Run one month by hand:** `make replay M=6` (after the pipeline targets). **All replay months:** `make replay`.
- **Run in Airflow:** `airflow dags trigger sigap_monthly --conf '{"month": 6}'`; logs per task in the Airflow UI
  (http://localhost:8080) under the DAG run. Retries: 2, five minutes apart.
- **Outputs:** decisions in `ops.decision_log`, monthly metrics in `ops.monitoring_monthly`, a summary in
  `reports/monitor/replay_<variant>.csv`, dashboard views from `make monitor-views`.

## Retraining rule
Written on 28 Oct 2026, before the first replay. A retraining ticket is opened when any of these holds:

| Signal | When it is known | Threshold | Why |
|---|---|---|---|
| Score PSI vs training months | the day the month's data arrives | ≥ 0.25 | the score distribution has moved enough that the threshold and bands no longer mean what they meant |
| Recall at the operating threshold | when the month's labels arrive (+2 months) | more than 10 points below validation (0.518) | the model misses noticeably more fraud than when it was approved |
| FPR ratio by age group | when labels arrive | < 0.50 | the release-gate fairness limit (ADR 0005) no longer holds |

Feature PSI ≥ 0.25 alone does not open a ticket: it is investigated first (data incident or real change), because
a single drifting input can leave the score stable.

## Alerts and what to do
| Signal | Threshold | First check | Action |
|---|---|---|---|
| Quarantine rate | > 2% of a month | did the source system change a field, a format or a code list? | hold the month, contact the source owner, do not retrain on it |
| Score PSI | > 0.25 | which top features drifted (`ops.v_feature_drift`)? | retraining ticket; consider tightening the review band until then |
| Recall at operating threshold | drop > 10 pts vs validation | are the month's labels complete? | retrain; if severe, fall back to the rules |
| API p95 latency | > 100 ms | `make load-test`: server-side vs round-trip time; container CPU and memory | add workers or replicas; if the API is down, route to the rules (Fallback) |

## Alert routing (n8n)
n8n polls `GET /v1/ops/alerts` every 15 minutes, sends each open alert to WhatsApp and acknowledges it only after
WhatsApp accepted the message. Alerts are written by `make ops-sync M=<month>` (after `make replay`).

| Alert kind | Goes to | Expected first action | Silence rule |
|---|---|---|---|
| drift | data science on duty | check which feature moved (`ops.v_feature_drift`); compare with the quarantine report | one message per `alert_key`; watch-level PSI stays on the dashboard |
| queue_over_capacity | fraud operations lead | move analysts or approve overtime; if it lasts, tighten the review band (decision policy) | only above capacity + 10%; one message per day |
| data_incident | source-system owner | hold the month; do not retrain or trust drift on it | one message per month |

### drift
Score PSI ≥ 0.25 is high severity and follows the retraining rule. A single feature at PSI ≥ 0.25 (medium) is
investigated first: a source change (data incident) or a real shift in applicants.

### queue_over_capacity
Cases beyond the day's capacity wait in the backlog (status `backlog`, riskiest first). Review the backlog the
next morning before new cases; if three days in a row are over capacity, raise it with the fraud operations lead.

### data_incident
More than 2% of a month quarantined. Base had 0% in every month, so this means the source system changed. The
month is held until the owner confirms.

**Review cases:** every weekday at 08:30 n8n sends the five highest-priority assigned cases with a link to the
decision form; the form posts to `POST /v1/ops/cases/{case_id}/decision`. If n8n is down, alerts stay in
`ops.alert` (`acked_at` NULL) and cases stay assigned; both are sent when it comes back, nothing is lost.

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
If the API is down, the model fails its monthly checks, or a retraining ticket is open and severe, account opening
switches to the rules-only policy (`configs/rules.yaml`, the champion): any rule hit goes to review, everything
else is approved, nothing is declined automatically. The rules need about 14 analysts at today's volume (decision
policy), so the review queue is the first thing to watch during a fallback.
