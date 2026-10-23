"""Phase 8 · Production replay: pretend SIGAP is live from month 5 onward.

For month t = 5, 6, 7 (in this order):
  1. score the month's applications with models/current (batch scoring, same code as the API)
  2. write decisions to Postgres decision_log and the month's KPIs (alert rate, review rate) to monitoring_monthly
  3. drift_report(train months vs month t) on the top features and on the score
  4. labels that became available at month t (landing/labels/available_month=t) -> compute TPR/FPR
     for the month they belong to (t - lag), and append to monitoring_monthly
  5. retraining rule (write it in docs/RUNBOOK.md first): e.g. score PSI > 0.25 OR TPR at the operating
     threshold drops more than 10 points vs validation -> open a retraining ticket (print + write a row)

Run:  make replay
Orchestration: dags/sigap_monthly.py runs ingest -> quality -> bronze -> silver -> gold -> features -> score
-> monitor once per month in Airflow.
"""

from __future__ import annotations


def main() -> None:
    """Phase 8 · TODO(Agatha): implement the replay loop described above."""
    raise NotImplementedError("TODO(Agatha) phase 8: monitor.replay.main")


if __name__ == "__main__":
    main()
