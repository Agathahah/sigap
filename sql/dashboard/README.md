# Metabase dashboard

Six saved questions for a local Metabase dashboard over the monitoring views. Metabase connects with the read-only
role `sigap_copilot` (phase 9, `make copilot-db`), which only sees the `copilot.*` views: a dashboard cannot change
data, and it sees the same allowlisted columns as the copilot.

| File | Question | Visualization |
|---|---|---|
| `q1_review_load.sql` | Reviews per day vs capacity | bar chart, goal line 300 |
| `q2_decision_mix.sql` | Approve / review / decline share | table |
| `q3_score_vs_feature_psi.sql` | Score PSI vs largest feature PSI | bar chart, goal line 0.25 |
| `q4_feature_drift_top5.sql` | Five most-shifted features per month | table with conditional formatting |
| `q5_late_labels.sql` | Recall, FPR and age FPR ratio once labels arrived | line chart, goal line 0.50 |
| `q6_review_queue.sql` | Review cases by month, band and status | table or bar chart |

## Run

```bash
make db-up && make dashboard          # Metabase on http://localhost:3000 (first start takes 1-2 minutes)
```

Database connection in Metabase (Admin settings -> Databases -> Add database -> PostgreSQL):

| Field | Value |
|---|---|
| Host | `postgres` (the service name inside Docker Compose, not localhost) |
| Port | `5432` (the port inside the network; 5433 is only the Mac side) |
| Database name | `sigap` (`POSTGRES_DB` in `.env`) |
| Username | `sigap_copilot` |
| Password | `SIGAP_COPILOT_DB_PASSWORD` from `.env` (typed into Metabase, never committed) |

Metabase keeps its own settings and dashboards in the `metabase_data` volume, so they survive `docker compose down`.
They are not in git; the screenshot in `docs/img/metabase-monitoring.png` is the record, and these SQL files rebuild
the questions on another laptop.
