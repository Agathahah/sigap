-- Operations (runs once the scoring API or the replay writes ops.decision_log)
-- Question: Daily review volume vs capacity, approval rate and review rate per month.
-- Business use: can the review team keep up with the decision policy?
-- BAF has no day of application, so the daily queue is the review share x 5,000 applications a day (the volume
-- assumed in configs/business.yaml) against 300 reviews a day of capacity. Only applications that are in the
-- warehouse count (load-test and API test ids are not), and only the latest model version.
WITH latest AS (
    SELECT model_version FROM ops.decision_log ORDER BY decided_at DESC LIMIT 1
), decisions AS (
    SELECT d.month_index AS month, l.decision
    FROM ops.decision_log l
    JOIN latest USING (model_version)
    JOIN gold.fact_application f USING (application_id)
    JOIN gold.dim_month d USING (month_key)
)
SELECT
    month,
    COUNT(*)                                                        AS applications,
    ROUND(100.0 * AVG((decision = 'approve')::int), 2)              AS approve_pct,
    ROUND(100.0 * AVG((decision = 'review')::int), 2)               AS review_pct,
    ROUND(100.0 * AVG((decision = 'decline')::int), 2)              AS decline_pct,
    ROUND(5000 * AVG((decision = 'review')::int))                   AS reviews_per_day,
    300                                                             AS capacity_per_day,
    ROUND(100.0 * 5000 * AVG((decision = 'review')::int) / 300, 1)  AS capacity_used_pct
FROM decisions
GROUP BY month
ORDER BY month;
