# ADR 0007 · Ops automation with n8n and WhatsApp (human-in-the-loop)

- Status: proposed
- Date: 2026-10-28
- n8n version used: 2.44.6 (Docker image `docker.n8n.io/n8nio/n8n:2.44.6`)

## Context
- Four kinds of events need a person, each a different person: score drift → data science; a review queue over
  capacity → the fraud operations lead; a quarantine spike → the source-system owner; individual review cases →
  analysts. A dashboard shows all of them but only to whoever happens to open it.
- In the replay, month 6 needed about 319 reviews a day against a capacity of 300, and `credit_risk_score` drifted
  past PSI 0.25 in months 6–7 while the score stayed stable. Both are things someone should hear about the same
  day, once, with the runbook link.
- An alert nobody reads costs as much as no alert; the same alert sent every 15 minutes trains people to mute it.
- Analyst decisions must be auditable and must not bypass the API's rules (state machine, validation).

## Options considered
1. **Airflow for everything** (tasks that send messages) — one tool, but Airflow is a batch scheduler: no forms,
   no retries per message, no place for an analyst to answer.
2. **n8n for human workflows, Airflow for the data pipeline** — n8n polls the ops API, sends messages, hosts the
   decision form, and keeps an execution log; the pipeline stays in Airflow and `make`.
3. **Channel:** WhatsApp Business Platform (official Cloud API) vs Telegram, email or Slack. WhatsApp is where
   Indonesian operations teams already are. Constraints of the official API: free-form text only inside the
   24-hour customer-service window opened by the recipient's last message; outside it, only pre-approved template
   messages, priced per message since 1 July 2025 (Meta pricing documentation). Email (Gmail) is the fallback.
4. **Unofficial WhatsApp Web gateways** — rejected: against WhatsApp's terms, numbers get banned, no audit trail.
5. **n8n writing to Postgres directly vs through the ops API** — rejected direct access: n8n would hold database
   credentials and could skip the validation and the case state machine.

## Decision
n8n delivers alerts and review summaries over the official WhatsApp Cloud API and collects analyst decisions with
an n8n form, talking to SIGAP only through `/v1/ops/*` with its own API key; Airflow and `make` keep the data
pipeline.

## Consequences
- **What n8n can see:** alert texts (aggregates: a feature, a day, a month) and an allowlisted case payload
  (case id, application id, day, score, decision band, top 3 reason codes). No protected attributes, no raw
  features, no database credentials. The ops key cannot score applications.
- **Once, not 96 times:** each alert has a stable `alert_key`; it is acknowledged only after WhatsApp accepted the
  message, so a failed send is retried at the next poll and a delivered one is never repeated.
- **Audit:** every analyst decision is a row in `ops.review_decision` (append-only); closed cases cannot be
  reopened; an exact retry from n8n is recognised and not written twice.
- **Selective labels:** analyst outcomes are early labels for reviewed cases only. They are reported as such and
  never written into `gold.fact_application.is_fraud`, because training on them alone would teach the model only
  about applications the previous policy chose to review (Lakkaraju et al., 2017).
- **Monitor:** alerts per day, duplicate alerts (should be 0), open backlog, time from case creation to decision.
- **In a real bank:** an internal chat tool instead of a consumer messenger, and customer data kept in-country
  (UU 27/2022 tentang Pelindungan Data Pribadi). The demo sends no customer data, only ids and reason codes.

## References
- WhatsApp Cloud API, get started: https://developers.facebook.com/docs/whatsapp/cloud-api/get-started
- WhatsApp pricing: https://developers.facebook.com/docs/whatsapp/pricing
- n8n WhatsApp Business Cloud node: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.whatsapp/
- n8n Form Trigger: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.formtrigger/
- Lakkaraju et al. (2017). The Selective Labels Problem. KDD. https://doi.org/10.1145/3097983.3098066
