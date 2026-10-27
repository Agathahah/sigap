-- Behaviour
-- Question: Fraud rate by decile of velocity_6h and velocity_4w (NTILE window function).
-- Business use: is "many applications in a short time" a usable rule, and from which level?
WITH ranked AS (
    SELECT 'velocity_6h' AS feature, velocity_6h AS value, is_fraud,
           NTILE(10) OVER (ORDER BY velocity_6h) AS decile
    FROM eda.applications
    UNION ALL
    SELECT 'velocity_4w', velocity_4w, is_fraud,
           NTILE(10) OVER (ORDER BY velocity_4w)
    FROM eda.applications
)
SELECT
    feature,
    decile,
    ROUND(MIN(value)::numeric, 0)       AS from_value,
    ROUND(MAX(value)::numeric, 0)       AS to_value,
    COUNT(*)                            AS applications,
    ROUND(100.0 * AVG(is_fraud), 3)     AS fraud_rate_pct
FROM ranked
GROUP BY feature, decile
ORDER BY feature, decile;
