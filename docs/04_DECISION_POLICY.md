# Decision policy (phase 4 rules + phase 6 bands)

## Rule baseline log
Measured on training months 0-4 (675,666 applications, fraud 1.00%); month 5 is checked once per version.
Alerts = share of applications flagged by any rule.

| Date | Change in rules.yaml | Alerts | Hit rate | Recall | Note |
|---|---|---|---|---|---|
| 2026-10-28 | v0: template rules `device_seen_with_fraud`, `application_burst` | 0% / 0.21% | – / 0.43% | 0% / 0.1% | both retired: `device_fraud_count` is always 0; the burst rule flags traffic that is less risky than average (EDA F5) |
| 2026-10-28 | v1: five rules from EDA F1–F3 and F6 (combinations, no protected attributes) | 8.76% | 5.40% | 47.4% | month 5: 7.86% alerts, 6.80% hit rate, 45.2% recall; `ba_windows_no_history` alone gives 33.9% recall at 5.11% alerts |

## Cost assumptions (from configs/business.yaml)
| Assumption | Value | Reasoning / reference |
|---|---|---|

## Chosen policy
| t_review | t_decline | review rate | fraud stopped | expected cost / 10k apps |
|---|---|---|---|---|

## Champion (rules) vs challenger (model + bands), months 6-7 replay
_table from reports/policy/champion_challenger_<variant>.csv_

## Sensitivity
| Assumption changed | low | base | high | Does the recommendation change? |
|---|---|---|---|---|
