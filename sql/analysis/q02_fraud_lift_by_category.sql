-- Segments
-- Question: Fraud rate, volume share and lift (segment rate / overall rate) by payment_type, device_os, source, housing_status.
-- Business use: where rules should look first; a high lift on a tiny segment catches little fraud.
WITH overall AS (
    SELECT AVG(is_fraud) AS rate FROM eda.applications
),
segments AS (
    SELECT 'payment_type' AS dimension, payment_type AS segment, is_fraud FROM eda.applications
    UNION ALL SELECT 'device_os', device_os, is_fraud FROM eda.applications
    UNION ALL SELECT 'source', source, is_fraud FROM eda.applications
    UNION ALL SELECT 'housing_status', housing_status, is_fraud FROM eda.applications
)
SELECT
    dimension,
    segment,
    COUNT(*)                                                                  AS applications,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY dimension), 2)  AS volume_share_pct,
    ROUND(100.0 * AVG(is_fraud), 3)                                           AS fraud_rate_pct,
    ROUND(AVG(is_fraud) / (SELECT rate FROM overall), 2)                      AS lift,
    ROUND(100.0 * SUM(is_fraud) / SUM(SUM(is_fraud)) OVER (PARTITION BY dimension), 2) AS fraud_share_pct
FROM segments
GROUP BY dimension, segment
ORDER BY dimension, lift DESC;
