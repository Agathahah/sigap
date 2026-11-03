-- The five most-shifted features each month (window function: rank inside each month).
-- Metabase: Table; Conditional formatting on status (alert red, watch amber).
SELECT month, feature, round(psi::numeric, 3) AS psi, status
FROM (
    SELECT month, feature, psi, status,
           row_number() OVER (PARTITION BY month ORDER BY psi DESC) AS rank_in_month
    FROM copilot.v_feature_drift
    WHERE feature <> 'score'
) ranked
WHERE rank_in_month <= 5
ORDER BY month, psi DESC;
