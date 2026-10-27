-- Trend
-- Question: Monthly and 3-month rolling fraud rate per device_os.
-- Business use: is a segment getting worse month after month?
WITH monthly AS (
    SELECT device_os, month, COUNT(*) AS applications, SUM(is_fraud) AS frauds
    FROM eda.applications
    GROUP BY device_os, month
)
SELECT
    device_os,
    month,
    applications,
    ROUND(100.0 * frauds / applications, 3) AS fraud_rate_pct,
    ROUND(100.0 * SUM(frauds) OVER w / SUM(applications) OVER w, 3) AS rolling_3m_rate_pct
FROM monthly
WINDOW w AS (PARTITION BY device_os ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
ORDER BY device_os, month;
