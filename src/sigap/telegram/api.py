"""Thin clients for the two HTTP APIs the bot talks to: Telegram's Bot API and SIGAP's ops API.

Both take an httpx client so tests can pass a fake transport (or FastAPI's TestClient) instead of the network.
The bot token is part of every Telegram URL, so it is masked in every error this module raises.
"""

from __future__ import annotations

from typing import Any

import httpx

TELEGRAM_BASE = "https://api.telegram.org"
MAX_TEXT = 4096  # Telegram's limit for one message


class TelegramError(RuntimeError):
    """A Bot API call failed; the message never contains the token."""


class TelegramAPI:
    """The Bot API methods the bot uses. Plain text messages (no parse mode, so nothing needs escaping)."""

    def __init__(self, token: str, http: httpx.Client | None = None, base_url: str = TELEGRAM_BASE) -> None:
        if not token:
            raise ValueError(
                "SIGAP_TELEGRAM_BOT_TOKEN is empty: create a bot with @BotFather and put the token in .env"
            )
        self._token = token
        self._base = f"{base_url}/bot{token}"
        self.http = http or httpx.Client(timeout=40)

    def call(self, method: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        try:
            r = self.http.post(f"{self._base}/{method}", json=params)
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramError(f"{method}: {type(exc).__name__}: {exc}".replace(self._token, "***")) from None
        if not data.get("ok"):
            raise TelegramError(f"{method}: {data.get('description', 'unknown error')}".replace(self._token, "***"))
        return data["result"]

    def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        return self.call("getUpdates", offset=offset, timeout=timeout, allowed_updates=["message", "callback_query"])

    def send_message(self, chat_id: int, text: str, buttons: list[list[dict]] | None = None) -> dict:
        markup = {"inline_keyboard": buttons} if buttons else None
        return self.call("sendMessage", chat_id=chat_id, text=text[:MAX_TEXT], reply_markup=markup)

    def edit_message(self, chat_id: int, message_id: int, text: str, buttons: list[list[dict]] | None = None) -> dict:
        markup = {"inline_keyboard": buttons} if buttons else None
        return self.call(
            "editMessageText", chat_id=chat_id, message_id=message_id, text=text[:MAX_TEXT], reply_markup=markup
        )

    def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)

    def typing(self, chat_id: int) -> None:
        self.call("sendChatAction", chat_id=chat_id, action="typing")


class OpsAPIError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"ops API {status}: {detail}")
        self.status = status


class OpsClient:
    """SIGAP's ops API (/v1/ops/*) with the ops key: the same door n8n uses (ADR 0007)."""

    def __init__(self, base_url: str, api_key: str, http: httpx.Client | None = None) -> None:
        self.base = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key}
        self.http = http or httpx.Client(timeout=15)

    def _check(self, r: httpx.Response) -> Any:
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise OpsAPIError(r.status_code, str(detail)[:300])
        return r.json()

    def alerts(self, channel: str) -> list[dict]:
        return self._check(
            self.http.get(f"{self.base}/v1/ops/alerts", params={"channel": channel}, headers=self.headers)
        )

    def ack(self, alert_key: str, channel: str) -> dict:
        return self._check(
            self.http.post(
                f"{self.base}/v1/ops/alerts/{alert_key}/ack", json={"channel": channel}, headers=self.headers
            )
        )

    def cases(self, status: str = "assigned", limit: int = 5) -> list[dict]:
        return self._check(
            self.http.get(f"{self.base}/v1/ops/cases", params={"status": status, "limit": limit}, headers=self.headers)
        )

    def decide(self, case_id: str, outcome: str, analyst_id: str, note: str | None = None) -> dict:
        body = {"outcome": outcome, "analyst_id": analyst_id, "note": note}
        return self._check(
            self.http.post(f"{self.base}/v1/ops/cases/{case_id}/decision", json=body, headers=self.headers)
        )
