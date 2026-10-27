-- Volume and fraud
-- Question: Applications, frauds and fraud rate per month (training months 0-4).
-- Business use: baseline prevalence and its trend; dashboard tile.
SELECT
    month,
    COUNT(*)                              AS applications,
    SUM(is_fraud)::int                    AS frauds,
    ROUND(100.0 * AVG(is_fraud), 3)       AS fraud_rate_pct
FROM eda.applications
GROUP BY month
ORDER BY month;
