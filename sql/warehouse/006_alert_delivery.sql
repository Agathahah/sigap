-- Phase 11 · One delivery receipt per alert and channel, so several channels (e-mail through n8n, Telegram through
-- the SIGAP bot) each send an alert once, independently. Idempotent. Run after 003_ops.sql:
--   make db-sql F=sql/warehouse/006_alert_delivery.sql
--
-- ops.alert.acked_at keeps its meaning: acknowledged on the primary channel (n8n: e-mail or WhatsApp).
-- Mirror channels (Telegram) only write a receipt here.

CREATE TABLE IF NOT EXISTS ops.alert_delivery (
    alert_key    TEXT NOT NULL REFERENCES ops.alert (alert_key),
    channel      TEXT NOT NULL CHECK (channel IN ('email', 'whatsapp', 'telegram')),
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (alert_key, channel)
);

-- Receipts for alerts acknowledged before this table existed.
INSERT INTO ops.alert_delivery (alert_key, channel, delivered_at)
SELECT alert_key, coalesce(channel, 'email'), acked_at
FROM ops.alert
WHERE acked_at IS NOT NULL AND coalesce(channel, 'email') IN ('email', 'whatsapp', 'telegram')
ON CONFLICT DO NOTHING;

SELECT channel, count(*) AS delivered FROM ops.alert_delivery GROUP BY channel ORDER BY channel;
