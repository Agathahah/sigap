-- Share of approve / review / decline per replayed month, in percent.
-- Metabase: Table (approve dominates a stacked bar, so a table reads better).
SELECT month,
       round((approve_rate * 100)::numeric, 2) AS approve_pct,
       round((review_rate * 100)::numeric, 2)  AS review_pct,
       round((decline_rate * 100)::numeric, 2) AS decline_pct
FROM copilot.v_monthly_kpis
WHERE applications IS NOT NULL
ORDER BY month;
