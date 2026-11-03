-- Review cases by month, band and status (make ops-sync M=5..7 first).
-- Metabase: Table, or a bar chart of cases per month split by status.
SELECT month, decision_band, status, count(*) AS cases
FROM copilot.v_review_case
GROUP BY month, decision_band, status
ORDER BY month, decision_band, status;
