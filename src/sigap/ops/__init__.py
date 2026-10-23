"""Phase 8b · Fraud operations: alerts, review cases and analyst decisions (human-in-the-loop).

Boundary (ADR 0007):
  - Airflow runs the DATA pipeline (monthly, batch). n8n runs the HUMAN workflow (events, people, messages).
  - All logic lives here in Python and is tested. n8n only moves messages: it calls the SIGAP ops API with an
    API key and sends WhatsApp messages. n8n has NO database credentials.
  - Analyst decisions are written back through the API, which validates them and keeps an audit trail.
"""
