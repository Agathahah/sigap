"""Phase 8 · Airflow DAG: SIGAP's monthly cycle. TODO(Agatha).

Tasks (BashOperator calling `make` targets or `python -m sigap...`), one month per run:
    land(month) -> quality -> bronze -> silver -> gold -> features -> score_batch -> monitor -> ops_sync
                                                                        └─> retrain_ticket (only if the
                                                                            retraining rule in RUNBOOK fires)
    ops_sync (phase 8b) writes alerts + review cases; n8n picks them up. Airflow never sends WhatsApp messages:
    data pipeline here, human workflow in n8n (ADR 0007).
Requirements:
  - month from dag_run.conf {"month": 6}, so months 5, 6, 7 can be replayed in order (and backfilled)
  - retries=2, retry_delay 5 min, owner "agatha", catchup False
  - each task idempotent (re-running a month gives the same tables)

Local Airflow (separate venv; Airflow pins its own dependencies):
    python3.12 -m venv ~/airflow-venv && source ~/airflow-venv/bin/activate
    pip install "apache-airflow==3.3.2" --constraint \\
      "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt"
    export AIRFLOW_HOME=~/airflow SIGAP_HOME=~/projects/sigap
    mkdir -p $AIRFLOW_HOME/dags && ln -sf $SIGAP_HOME/dags/sigap_monthly.py $AIRFLOW_HOME/dags/
    airflow standalone            # UI at http://localhost:8080, password printed in the terminal
    airflow dags trigger sigap_monthly --conf '{"month": 6}'
"""
