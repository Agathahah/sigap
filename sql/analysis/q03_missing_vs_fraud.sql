-- Data quality as a signal
-- Question: For each sentinel column, the share missing and the fraud rate when missing vs present.
-- Business use: keep a <column>_missing flag as a feature instead of filling the value with an average.
SELECT
    v.column_name,
    ROUND(100.0 * AVG(v.missing::int), 2)                                    AS missing_pct,
    ROUND(100.0 * AVG(a.is_fraud) FILTER (WHERE v.missing), 3)               AS fraud_rate_missing_pct,
    ROUND(100.0 * AVG(a.is_fraud) FILTER (WHERE NOT v.missing), 3)           AS fraud_rate_present_pct,
    ROUND(AVG(a.is_fraud) FILTER (WHERE v.missing)
          / NULLIF(AVG(a.is_fraud) FILTER (WHERE NOT v.missing), 0), 2)      AS ratio_missing_vs_present
FROM eda.applications AS a
CROSS JOIN LATERAL (VALUES
    ('prev_address_months_count',    a.prev_address_months_count = -1),
    ('current_address_months_count', a.current_address_months_count = -1),
    ('intended_balcon_amount',       a.intended_balcon_amount < 0),
    ('bank_months_count',            a.bank_months_count = -1),
    ('session_length_in_minutes',    a.session_length_in_minutes = -1),
    ('device_distinct_emails_8w',    a.device_distinct_emails_8w = -1)
) AS v (column_name, missing)
GROUP BY v.column_name
ORDER BY ratio_missing_vs_present DESC NULLS LAST;
