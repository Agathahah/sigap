# Runbook

## Monthly job (Airflow DAG sigap_monthly)
_order of tasks, how to re-run one month, where logs are_

## Alerts and what to do
| Signal | Threshold | First check | Action |
|---|---|---|---|
| Quarantine rate | _> x%_ | _source system change?_ | _hold the month, contact source owner_ |
| Score PSI | > 0.25 | _which feature drifted?_ | _retraining ticket; consider tightening review band_ |
| TPR at operating threshold | _drop > 10 pts_ | _label completeness_ | _retrain / fall back to rules_ |
| API p95 latency | > 100 ms | | |

## Alert routing (phase 8b, n8n)
| Alert kind | Goes to | Expected first action | Silence rule |
|---|---|---|---|
| drift | _data science on duty_ | _check which feature; compare with quarantine report_ | _one message per key (alert_key)_ |
| queue_over_capacity | _fraud ops lead_ | _move analysts / tighten review band temporarily (phase 6 memo)_ | |
| data_incident | _source-system owner_ | _hold the month; do not retrain on it_ | |

If n8n is down: alerts stay in ops.alert (acked_at NULL) and are sent when it comes back; nothing is lost.

## Fallback
_If the model or API is down: rules-only policy from configs/rules.yaml (champion)._
