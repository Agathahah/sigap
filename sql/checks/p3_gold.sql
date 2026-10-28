-- Warehouse checks after `make gold`. Run: make db-sql F=sql/checks/p3_gold.sql
-- Every check prints a number that must be 0, or a table to compare with the ERD and the data card.

\echo '== 1. Tables in gold and ops (compare with docs/01_ERD.md) =='
\dt gold.*
\dt ops.*

\echo '== 2. Structure of the fact table: columns, types, NULL allowed, keys =='
\d gold.fact_application

\echo '== 3. Row counts per table =='
SELECT 'dim_month' AS table_name, count(*) AS n FROM gold.dim_month
UNION ALL SELECT 'dim_channel', count(*) FROM gold.dim_channel
UNION ALL SELECT 'dim_device', count(*) FROM gold.dim_device
UNION ALL SELECT 'dim_profile', count(*) FROM gold.dim_profile
UNION ALL SELECT 'fact_application', count(*) FROM gold.fact_application
UNION ALL SELECT 'ops.decision_log', count(*) FROM ops.decision_log
UNION ALL SELECT 'ops.monitoring_monthly', count(*) FROM ops.monitoring_monthly;

\echo '== 4. Grain: one row per application (must be 0) =='
SELECT count(*) - count(DISTINCT application_id) AS duplicate_applications FROM gold.fact_application;

\echo '== 5. Foreign keys declared on the fact (expect 4) and orphan rows (must be 0) =='
SELECT conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'gold.fact_application'::regclass AND contype = 'f'
ORDER BY conname;
SELECT count(*) AS orphan_rows
FROM gold.fact_application f
LEFT JOIN gold.dim_channel c USING (channel_key)
LEFT JOIN gold.dim_device d USING (device_key)
LEFT JOIN gold.dim_profile p USING (profile_key)
LEFT JOIN gold.dim_month m USING (month_key)
WHERE c.channel_key IS NULL OR d.device_key IS NULL OR p.profile_key IS NULL OR m.month_key IS NULL;

\echo '== 6. Point in time: labels per month (months 6-7 must have 0 labelled, fraud_pct as in the data card) =='
SELECT m.month_index AS month, m.label_complete, count(*) AS applications, count(f.is_fraud) AS labelled,
       round(100.0 * avg(f.is_fraud), 2) AS fraud_pct
FROM gold.fact_application f JOIN gold.dim_month m USING (month_key)
GROUP BY 1, 2 ORDER BY 1;

\echo '== 7. Sentinels: NULL value <=> missing flag = 1 (every mismatch column must be 0) =='
SELECT
  count(*) FILTER (WHERE (prev_address_months_count IS NULL) <> (prev_address_months_count_missing = 1)) AS prev_address,
  count(*) FILTER (WHERE (current_address_months_count IS NULL) <> (current_address_months_count_missing = 1)) AS current_address,
  count(*) FILTER (WHERE (intended_balcon_amount IS NULL) <> (intended_balcon_amount_missing = 1)) AS intended_balcon,
  count(*) FILTER (WHERE (bank_months_count IS NULL) <> (bank_months_count_missing = 1)) AS bank_months,
  count(*) FILTER (WHERE (session_length_in_minutes IS NULL) <> (session_length_in_minutes_missing = 1)) AS session_length,
  count(*) FILTER (WHERE (device_distinct_emails_8w IS NULL) <> (device_distinct_emails_8w_missing = 1)) AS device_emails
FROM gold.fact_application;

\echo '== 8. Star-schema query: fraud rate per device and channel, labelled months only (segments >= 1000) =='
SELECT d.device_os, c.source, count(*) AS n, round(100.0 * avg(f.is_fraud), 2) AS fraud_pct
FROM gold.fact_application f
JOIN gold.dim_device d USING (device_key)
JOIN gold.dim_channel c USING (channel_key)
JOIN gold.dim_month m USING (month_key)
WHERE m.label_complete
GROUP BY 1, 2
HAVING count(*) >= 1000          -- tiny segments give noisy rates
ORDER BY fraud_pct DESC;
