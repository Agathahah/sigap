-- Performance once the labels arrived (two months later). Release limits: recall >= 0.40, age FPR ratio >= 0.50.
-- Metabase: Line chart, x = month, y = recall and fpr_ratio_age; Goal line at 0.50.
SELECT month,
       round(recall_at_threshold::numeric, 3) AS recall,
       round(fpr::numeric, 3)                 AS fpr,
       round(fpr_ratio_age::numeric, 2)       AS fpr_ratio_age,
       round((fraud_rate_labelled * 100)::numeric, 2) AS fraud_rate_pct
FROM copilot.v_monthly_kpis
WHERE recall_at_threshold IS NOT NULL
ORDER BY month;
