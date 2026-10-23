"""Phase 8b · Job: refresh alerts and review cases from the warehouse (runs after `make replay`).

Steps (TODO Agatha):
  1. read drift rows for the month from ops.monitoring_monthly (month, feature, psi)
  2. read the month's quarantine rate from reports/quality/ (phase 2)
  3. read review decisions of the month from ops.decision_log (decision == "review"), give each a case_id
     (e.g. "case-" + application_id), a day, score, reasons
  4. cases = assign_cases(reviews, capacity from configs/business.yaml review_capacity_per_day)
  5. queue = cases grouped by (month, day) -> review_count
  6. alerts = build_alerts(drift, queue, quality, cfg from configs/ops.yaml + business.yaml)
  7. store = PostgresStore(...); store.add_cases(cases); store.add_alerts(alerts); print what was new
Idempotent: running it twice for the same month inserts nothing new (keys and case ids are stable).

Run:   make ops-sync M=6
Airflow: task `ops_sync` after `monitor` in dags/sigap_monthly.py.
"""

from __future__ import annotations


def main(month: int) -> None:
    raise NotImplementedError("TODO(Agatha) phase 8b: sigap.ops.sync.main")


if __name__ == "__main__":
    import sys

    main(int(sys.argv[1]))
