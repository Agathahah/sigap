-- PSI of the model score vs the largest single-feature PSI. Watch from 0.10, alert from 0.25.
-- Metabase: Bar chart, x = month, y = score_psi and max_feature_psi (two series); Goal line at 0.25.
SELECT month,
       round(score_psi::numeric, 3)       AS score_psi,
       round(max_feature_psi::numeric, 3) AS max_feature_psi
FROM copilot.v_monthly_kpis
WHERE applications IS NOT NULL
ORDER BY month;
