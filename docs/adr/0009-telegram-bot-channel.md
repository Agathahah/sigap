# ADR 0009 · Telegram as a second channel: one long-polling bot for alerts, review decisions and the copilot

- Status: proposed
- Date: 2026-11-02

## Context
- Alerts and review summaries reach the analyst by e-mail (ADR 0007; WhatsApp from the Meta test number cannot
  reach Indonesian numbers, error 130497). E-mail is reliable but slow to act on from a phone, and deciding a case
  needs a separate web form that only works on the laptop.
- The analyst also wants to ask the copilot (phase 9) from the phone.
- Constraint: everything runs on one laptop without a public address.

## Options considered
1. **n8n Telegram nodes:** sending works, but receiving button presses or chat messages needs the Telegram Trigger,
   which registers a webhook and so needs a public HTTPS address (a tunnel that exposes the local n8n).
2. **A small Python bot with long polling (`getUpdates`):** the bot asks Telegram for new updates, so nothing
   has to be reachable from the internet; it reuses the ops API (like n8n) and the copilot graph in-process.
3. **Slack or Microsoft Teams:** closer to what a bank uses internally, but needs a workspace and app approval;
   not available for this project.

## Decision
A single SIGAP bot (`src/sigap/telegram/`, `make telegram-bot`) uses long polling to send alerts and the daily
review cases to an allowlist of chats, takes case decisions through inline buttons with a confirmation step, and
relays other messages to the read-only copilot; n8n keeps the e-mail channel. Each channel keeps its own delivery
receipt (`ops.alert_delivery`), so an alert is sent once per channel and a failure in one channel never blocks or
duplicates the other.

## Consequences
- **Who can use it:** only chat ids in `SIGAP_TELEGRAM_CHAT_IDS`; any other chat is told its id and nothing else.
  A decision records `analyst_id = tg.<telegram user id>` in the append-only audit table, and the same state machine
  and idempotency rules apply as for the form (409 for a conflicting second decision).
- **Two taps, not one:** a case decision is final, so every button asks for confirmation before calling the API.
- **Secrets:** the bot token lives in `.env` (git-ignored) because the bot is a separate process, not an n8n
  credential; it is masked in every error the bot logs.
- **Data on Telegram:** alert texts are aggregates; case messages carry the allowlisted payload (case id, score,
  day, reason codes); copilot answers can include application-level model inputs. Telegram cloud chats are not
  end-to-end encrypted and are stored on Telegram's servers, so in a bank this channel would be an internal chat
  tool (or Telegram limited to alerts), decided with the data protection officer under UU 27/2022.
- **Receipts:** `ops.alert.acked_at` keeps meaning "acknowledged on the primary channel" (n8n); Telegram only
  writes a receipt. Existing acknowledgements were backfilled as e-mail receipts, so the bot's first run sends
  every existing alert once to Telegram.
- **Monitor:** bot errors in its log, alerts with an e-mail receipt but no Telegram receipt after an hour,
  decisions per channel.

## References
- Telegram Bot API (getUpdates, inline keyboards, callback queries): https://core.telegram.org/bots/api
- Telegram FAQ on cloud chats vs secret chats: https://telegram.org/faq#q-how-secure-is-telegram
