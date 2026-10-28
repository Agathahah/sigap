-- Monitoring views for the dashboard (Metabase) and the copilot. Idempotent: CREATE OR REPLACE.
-- Run: make db-sql F=sql/warehouse/004_monitoring_views.sql  (after make replay)

-- One row per month: volumes and decision rates from the replay, drift, and performance once labels arrived.
CREATE OR REPLACE VIEW ops.v_monthly_kpis AS
SELECT
    m.month,
    max(m.value) FILTER (WHERE m.metric = 'applications')                       AS applications,
    max(m.value) FILTER (WHERE m.metric = 'approve_rate')                       AS approve_rate,
    max(m.value) FILTER (WHERE m.metric = 'review_rate')                        AS review_rate,
    max(m.value) FILTER (WHERE m.metric = 'decline_rate')                       AS decline_rate,
    max(m.value) FILTER (WHERE m.metric = 'reviews_per_day')                    AS reviews_per_day,
    max(m.value) FILTER (WHERE m.metric = 'psi' AND m.feature = 'score')        AS score_psi,
    max(m.value) FILTER (WHERE m.metric = 'psi' AND m.feature <> 'score')       AS max_feature_psi,
    max(m.value) FILTER (WHERE m.metric = 'tpr')                                AS recall_at_threshold,
    max(m.value) FILTER (WHERE m.metric = 'fpr')                                AS fpr,
    max(m.value) FILTER (WHERE m.metric = 'fpr_ratio_age')                      AS fpr_ratio_age,
    max(m.value) FILTER (WHERE m.metric = 'fraud_rate')                         AS fraud_rate_labelled,
    max(m.value) FILTER (WHERE m.metric = 'retrain_flag')                       AS retrain_flag
FROM ops.monitoring_monthly m
GROUP BY m.month;

-- Feature drift in long form (for a bar chart per month).
CREATE OR REPLACE VIEW ops.v_feature_drift AS
SELECT month, feature, value AS psi,
       CASE WHEN value >= 0.25 THEN 'alert' WHEN value >= 0.10 THEN 'watch' ELSE 'stable' END AS status
FROM ops.monitoring_monthly
WHERE metric = 'psi';

-- Fraud rate per month, only where every label has arrived (never report a month that only looks clean).
CREATE OR REPLACE VIEW ops.v_fraud_rate_labelled AS
SELECT d.month_index AS month, count(*) AS applications, avg(f.is_fraud) AS fraud_rate
FROM gold.fact_application f
JOIN gold.dim_month d USING (month_key)
WHERE d.label_complete
GROUP BY d.month_index;
