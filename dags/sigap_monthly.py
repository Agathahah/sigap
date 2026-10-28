"""Airflow DAG: SIGAP's monthly cycle, one month per run.

    quality -> bronze -> silver -> gold -> features -> replay(month) -> ops_sync(month)

The data pipeline is idempotent (partitions overwritten, gold upserted, a month's replay rows replaced), so a
month can be re-run or backfilled safely. Airflow never sends WhatsApp messages: it writes alerts and review
cases (ops_sync, phase 8b) and n8n delivers them (ADR 0007). Each task calls the same `make` target a person
would run, so the DAG adds scheduling, retries and history, not new logic.

Local Airflow in its own virtual environment (Airflow pins its own dependencies):
    python3.12 -m venv ~/airflow-venv && source ~/airflow-venv/bin/activate
    pip install "apache-airflow==3.3.2" --constraint \\
      "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt"
    export AIRFLOW_HOME=~/airflow SIGAP_HOME=~/projects/sigap
    mkdir -p $AIRFLOW_HOME/dags && ln -sf $SIGAP_HOME/dags/sigap_monthly.py $AIRFLOW_HOME/dags/
    airflow standalone            # UI at http://localhost:8080, password printed in the terminal
    airflow dags trigger sigap_monthly --conf '{"month": 6}'
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param

SIGAP_HOME = os.environ.get("SIGAP_HOME", os.path.expanduser("~/projects/sigap"))
MONTH = "{{ params.month }}"

with DAG(
    dag_id="sigap_monthly",
    description="Monthly drop -> pipeline -> scoring replay and monitoring -> ops alerts",
    start_date=datetime(2026, 10, 1),
    schedule=None,  # triggered per month (replay); a live system would use "@monthly"
    catchup=False,
    params={"month": Param(7, type="integer", minimum=5, maximum=7, description="month to process")},
    default_args={"owner": "agatha", "retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["sigap"],
) as dag:

    def make(task_id: str, target: str) -> BashOperator:
        return BashOperator(task_id=task_id, bash_command=f"cd {SIGAP_HOME} && make {target}")

    quality = make("quality", "quality")
    bronze = make("bronze", "bronze")
    silver = make("silver", "silver")
    gold = make("gold", "gold")
    features = make("features", "features")
    replay = make("replay", f"replay M={MONTH}")
    ops_sync = make("ops_sync", f"ops-sync M={MONTH}")

    quality >> bronze >> silver >> gold >> features >> replay >> ops_sync
