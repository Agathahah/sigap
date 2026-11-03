-- Reviews per day against the review capacity (300 a day, configs/business.yaml).
-- Metabase: Bar chart, x = month, y = reviews_per_day; Display -> Goal line at 300.
SELECT month, round(reviews_per_day::numeric, 0) AS reviews_per_day, 300 AS capacity
FROM copilot.v_monthly_kpis
WHERE applications IS NOT NULL
ORDER BY month;
