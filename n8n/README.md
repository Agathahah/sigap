# n8n · fraud-ops automation (phase 8b)

n8n moves messages between SIGAP and people. It never decides anything and never touches the warehouse:
it calls the SIGAP ops API with an API key (`SIGAP_OPS_API_KEY`) and sends WhatsApp messages.
Why this boundary: ADR 0007.

```
alert-router   Schedule (15 min) -> GET /v1/ops/alerts -> WhatsApp text -> POST /v1/ops/alerts/{key}/ack
review-case    Schedule (30 min) -> GET /v1/ops/cases?status=assigned&limit=5 -> loop:
                 WhatsApp "send and wait" (custom form: outcome + note) -> POST /v1/ops/cases/{id}/decision
```

## Run

```bash
make ops-demo        # terminal 1: ops API with demo data on :8001 (needs your phase 8b functions)
make n8n-up          # n8n on http://localhost:5678 (first visit: create the owner account)
```

Credentials (created in the n8n UI, stored encrypted in the `n8n_data` volume, never exported):

| Credential | Type | Value |
|---|---|---|
| `SIGAP ops key` | Header Auth | Name `X-API-Key`, Value = `SIGAP_OPS_API_KEY` from `.env` |
| `WhatsApp SIGAP` | WhatsApp API | Access token (system-user token) + WhatsApp Business Account ID from Meta |

Values the workflows read with `{{ $env.* }}` (set in `.env`, passed by docker-compose):
`SIGAP_API_URL`, `SIGAP_ANALYST_WHATSAPP`, `SIGAP_WA_PHONE_NUMBER_ID`. Your phone number therefore never
appears in the exported JSON.

## WhatsApp rules that shape the design

- Official WhatsApp Business Platform (Cloud API) only. Unofficial "WhatsApp Web" gateways break WhatsApp's
  terms and can get the number banned. A bank would never accept them, so this project does not use them.
- Business-initiated messages outside the 24-hour customer-service window need an approved template.
  For the demo, open the window each working day by sending any message (e.g. "mulai shift") from your phone to
  the business test number. Pricing changed on 1 Oct 2026 (service messages: 1,000 free per number per month).
  Check Meta's pricing page before relying on any number.
- "Send and wait for response" replies through a form link served by n8n. Your phone must be able to reach
  n8n: set `N8N_WEBHOOK_URL=http://<your Mac's LAN IP>:5678/` and keep the phone on the same Wi-Fi.
  Never expose this n8n to the internet (it runs with `N8N_SECURE_COOKIE=false`).
- Fallback if Meta setup is blocked: replace the WhatsApp nodes with a Gmail node. The API, the messages
  and the tests stay the same (`test_workflows_use_ops_api_and_a_channel` accepts email too).

## Export (workflows are code)

```bash
make n8n-export      # writes n8n/workflows/<id>.json
make check P=8b      # no tokens, no phone numbers, no pinned data, API key via credential, no Postgres node
git add n8n/workflows && git commit -m "Phase 8b: n8n workflows"
```
