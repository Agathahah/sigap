-- Ops tables for alerts, review cases and analyst decisions (written by sigap.ops.sync and the ops API).
-- Idempotent (CREATE ... IF NOT EXISTS). Run after 001_schemas.sql: make db-sql F=sql/warehouse/003_ops.sql

CREATE TABLE IF NOT EXISTS ops.alert (
    alert_key   TEXT PRIMARY KEY,                          -- sigap.ops.alerts.alert_key: one row per event
    kind        TEXT NOT NULL CHECK (kind IN ('drift', 'queue_over_capacity', 'data_incident')),
    severity    TEXT NOT NULL CHECK (severity IN ('high', 'medium')),
    month       SMALLINT NOT NULL,
    subject     TEXT NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    threshold   DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    acked_at    TIMESTAMPTZ NULL,                          -- set once, by POST /v1/ops/alerts/{key}/ack
    channel     TEXT NULL
);
CREATE INDEX IF NOT EXISTS ix_alert_open ON ops.alert (acked_at) WHERE acked_at IS NULL;

CREATE TABLE IF NOT EXISTS ops.review_case (
    case_id        TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES gold.fact_application (application_id),
    month          SMALLINT NOT NULL,
    day            DATE NOT NULL,
    score          DOUBLE PRECISION NOT NULL,
    decision_band  TEXT NOT NULL,
    reasons        TEXT[] NOT NULL DEFAULT '{}',           -- reason codes, never raw values
    priority       INTEGER NOT NULL,
    status         TEXT NOT NULL
        CHECK (status IN ('assigned', 'backlog', 'pending_info', 'closed_fraud', 'closed_legit')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_case_queue ON ops.review_case (status, day, priority);

-- Append-only audit trail: rows are never updated or deleted. Analyst outcomes are early labels for reviewed
-- cases only (selective labels) and never overwrite gold.fact_application.is_fraud.
CREATE TABLE IF NOT EXISTS ops.review_decision (
    decision_id  BIGSERIAL PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES ops.review_case (case_id),
    outcome      TEXT NOT NULL CHECK (outcome IN ('confirmed_fraud', 'legit', 'need_info')),
    analyst_id   TEXT NOT NULL,
    note         TEXT NULL CHECK (char_length(note) <= 500),
    status_after TEXT NOT NULL,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_decision_case ON ops.review_decision (case_id, decided_at);
