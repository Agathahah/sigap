-- Phase 9 · What the analyst copilot may read (ADR 0003). Idempotent.
-- Run: make copilot-db   (this file, then sets the role password from SIGAP_COPILOT_DB_PASSWORD in .env)
--
-- The copilot connects as sigap_copilot: LOGIN, SELECT on the copilot schema only, every transaction read-only,
-- statements time out after 5 s. The views below run with their owner's rights, so the role never needs access
-- to gold or ops directly. Protected attributes (age band, income decile, employment status) are not in any view.

CREATE SCHEMA IF NOT EXISTS copilot;
CREATE EXTENSION IF NOT EXISTS vector;

-- One row per application: channel, device, housing and the model inputs an analyst may discuss, plus the label
-- only where it has arrived (NULL otherwise) and whether the month is fully labelled.
CREATE OR REPLACE VIEW copilot.v_application AS
SELECT
    f.application_id,
    m.month_index AS month,
    m.label_complete,
    c.source, c.payment_type,
    d.device_os, d.keep_alive_session, d.email_is_free,
    p.housing_status,
    f.name_email_similarity, f.prev_address_months_count, f.current_address_months_count,
    f.days_since_request, f.intended_balcon_amount, f.zip_count_4w,
    f.velocity_6h, f.velocity_24h, f.velocity_4w, f.bank_branch_count_8w,
    f.date_of_birth_distinct_emails_4w, f.credit_risk_score, f.phone_home_valid, f.phone_mobile_valid,
    f.bank_months_count, f.has_other_cards, f.proposed_credit_limit, f.foreign_request,
    f.session_length_in_minutes, f.device_distinct_emails_8w,
    f.is_fraud
FROM gold.fact_application f
JOIN gold.dim_month m USING (month_key)
JOIN gold.dim_channel c USING (channel_key)
JOIN gold.dim_device d USING (device_key)
JOIN gold.dim_profile p USING (profile_key);

-- The latest scoring decision per application (API or monthly replay).
CREATE OR REPLACE VIEW copilot.v_decision AS
SELECT DISTINCT ON (application_id)
    application_id, model_version, score, decision, reasons, decided_at
FROM ops.decision_log
ORDER BY application_id, decided_at DESC, id DESC;

-- Monthly monitoring (aggregates only) and feature drift with its status.
CREATE OR REPLACE VIEW copilot.v_monthly_kpis AS SELECT * FROM ops.v_monthly_kpis;
CREATE OR REPLACE VIEW copilot.v_feature_drift AS SELECT * FROM ops.v_feature_drift;

-- Review cases (allowlisted columns, the same as the ops API returns).
CREATE OR REPLACE VIEW copilot.v_review_case AS
SELECT case_id, application_id, month, day, score, decision_band, reasons, priority, status
FROM ops.review_case;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigap_copilot') THEN
        CREATE ROLE sigap_copilot LOGIN;
    END IF;
END
$$;
ALTER ROLE sigap_copilot SET default_transaction_read_only = on;
ALTER ROLE sigap_copilot SET statement_timeout = '5s';
REVOKE ALL ON SCHEMA gold, ops FROM sigap_copilot;
GRANT USAGE ON SCHEMA copilot TO sigap_copilot;
GRANT SELECT ON ALL TABLES IN SCHEMA copilot TO sigap_copilot;
ALTER DEFAULT PRIVILEGES IN SCHEMA copilot GRANT SELECT ON TABLES TO sigap_copilot;

-- Check: what the role can see (should be the copilot views and copilot.policy_chunks only).
SELECT table_schema, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'sigap_copilot'
ORDER BY 1, 2;
