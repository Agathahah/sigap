-- Rules
-- Question: How many applications are flagged by 0, 1, 2, 3+ candidate rules, and the fraud rate of each group.
-- Business use: are candidate rules redundant, and how many alerts would they create?
-- Candidate rules (thresholds are provisional and tuned in the rules stage):
--   R1 foreign_request = 1
--   R2 free e-mail whose name barely matches the applicant (name_email_similarity < 0.2)
--   R3 session not kept alive and a device already used with several e-mails
--   R4 no previous address on record
WITH flags AS (
    SELECT
        is_fraud,
        (foreign_request = 1)::int
      + (email_is_free = 1 AND name_email_similarity < 0.2)::int
      + (keep_alive_session = 0 AND device_distinct_emails_8w >= 2)::int
      + (prev_address_months_count = -1)::int AS rules_hit
    FROM eda.applications
)
SELECT
    CASE WHEN rules_hit >= 3 THEN '3+' ELSE rules_hit::text END   AS rules_hit,
    COUNT(*)                                                      AS applications,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)            AS volume_share_pct,
    SUM(is_fraud)::int                                            AS frauds,
    ROUND(100.0 * SUM(is_fraud) / SUM(SUM(is_fraud)) OVER (), 2)  AS fraud_share_pct,
    ROUND(100.0 * AVG(is_fraud), 3)                               AS fraud_rate_pct
FROM flags
GROUP BY 1
ORDER BY 1;
