-- Fairness context
-- Question: Applications and fraud rate for customers aged 50+ vs under 50, per month.
-- Business use: why the model's false-positive rate must be compared across age groups.
SELECT
    month,
    CASE WHEN customer_age >= 50 THEN '50+' ELSE '<50' END   AS age_group,
    COUNT(*)                                                 AS applications,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY month), 2) AS volume_share_pct,
    ROUND(100.0 * AVG(is_fraud), 3)                          AS fraud_rate_pct
FROM eda.applications
GROUP BY month, age_group
ORDER BY month, age_group;
