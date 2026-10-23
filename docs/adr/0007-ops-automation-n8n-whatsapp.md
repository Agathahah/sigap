# ADR 0007 · Ops automation with n8n and WhatsApp (human-in-the-loop)

- Status: proposed
- Date:
- n8n version used: _(n8n --version)_

## Context
_Who needs to act on what, and how fast? (drift alert → data science; queue over capacity → fraud ops lead;
quarantine spike → source-system owner; review cases → analysts). Why is a dashboard alone not enough?
What is the cost of an alert nobody reads, and of an alert sent 96 times a day?_

## Options considered
1. Airflow for everything (tasks that send messages) — _pros / cons_
2. n8n for human workflows, Airflow for the data pipeline — _pros / cons_
3. Channel: WhatsApp Business Platform (official Cloud API) / Telegram / email / Slack — _pros / cons, cost,
   24-hour window, templates, where the data goes_
4. Unofficial WhatsApp Web gateways — _why rejected (terms of service, ban risk, no audit trail)_
5. n8n writes to Postgres directly vs. through the ops API — _pros / cons_

## Decision
_One sentence._

## Consequences
- _What n8n can and cannot see (allowlisted case payload, no protected attributes, no DB credentials)._
- _Analyst decisions are early labels for reviewed cases only (selective labels): how you will and will not
  use them (Lakkaraju et al. 2017)._
- _What you monitor: decision latency, backlog, alerts per day, duplicate alerts (should be 0)._
- _In a real bank: internal chat instead of a consumer app; data residency (UU PDP 27/2022)._
