# Monitoring replay · months 5–7 as if live

Months 5–7 of BAF Base were scored one month at a time by the released model (`base-20261028-0433-b4e83b`) with
the chosen bands, as the monthly job would do in production (`make replay`, 28 Oct 2026). Labels were joined only
when they would have arrived, two months later. Results are stored in `ops.monitoring_monthly` and shown by the
views in `sql/warehouse/004_monitoring_views.sql`.

## On arrival of each month

| Month | Applications | Review | Decline | Reviews a day vs capacity 300 | Score PSI | Feature with the highest PSI |
|---|---|---|---|---|---|---|
| 5 | 119,323 | 5.75% | 0.75% | 287 | 0.033 | name_email_similarity 0.168 (watch) |
| 6 | 108,168 | 6.39% | 0.92% | 319 (106.5%) | 0.033 | credit_risk_score 0.253 (alert) |
| 7 | 96,843 | 5.66% | 0.83% | 283 | 0.084 | credit_risk_score 0.293 (alert) |

## When the labels arrived

| Known in month | For month | Recall | FPR | Precision | FPR ratio by age (50+ vs under 50) |
|---|---|---|---|---|---|
| 7 | 5 | 0.518 | 0.050 | 0.110 | 0.65 |
| 8 | 6 | 0.509 | 0.056 | 0.109 | 0.60 |
| 9 | 7 | 0.532 | 0.048 | 0.141 | 0.56 |

## Reading
- **A feature drifted, the score did not.** `credit_risk_score` passed PSI 0.25 in months 6 and 7 while the
  score's PSI stayed between 0.03 and 0.08, and recall held when the labels arrived. This is why the runbook
  investigates single-feature drift before opening a retraining ticket.
- **Recall stayed at 0.51–0.53** while the fraud rate rose from 1.18% to 1.47%.
- **Fairness needs watching:** the age FPR ratio fell from 0.65 to 0.56. It is still above the 0.50 limit, but the
  trend is reported monthly and a fall below 0.50 is a retraining trigger.
- **Capacity:** month 6 needed about 319 reviews a day, 6.5% over capacity. Phase 8b turns this into a
  `queue_over_capacity` alert when the excess passes 10%.
- **No retraining was triggered** by the rule in the [runbook](RUNBOOK.md).
