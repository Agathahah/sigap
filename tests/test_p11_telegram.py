"""Phase 11 · Telegram channel: per-channel alert receipts, the bot's commands, decision buttons and copilot relay.

No network: Telegram is a fake that records calls, the ops API is the real router on an in-memory store behind
FastAPI's TestClient, and the copilot is a function.
"""

import datetime as dt
import json

import httpx
import pandas as pd
import pytest

from sigap.ops.alerts import Alert
from sigap.ops.store import InMemoryStore
from sigap.telegram.api import OpsClient, TelegramAPI, TelegramError
from sigap.telegram.bot import (
    HELP,
    SigapBot,
    decision_buttons,
    parse_chat_ids,
    split_text,
)

pytestmark = pytest.mark.p11

KEY = "ops-test-key"
ME, STRANGER, USER = 111, 999, 4242


class FakeTelegram:
    def __init__(self):
        self.sent, self.edits, self.answers, self.typed = [], [], [], []
        self._mid = 0

    def send_message(self, chat_id, text, buttons=None):
        self._mid += 1
        self.sent.append({"chat": chat_id, "text": text, "buttons": buttons, "message_id": self._mid})
        return {"message_id": self._mid}

    def edit_message(self, chat_id, message_id, text, buttons=None):
        self.edits.append({"chat": chat_id, "message_id": message_id, "text": text, "buttons": buttons})

    def answer_callback(self, callback_id, text=None):
        self.answers.append(text)

    def typing(self, chat_id):
        self.typed.append(chat_id)


@pytest.fixture()
def env(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sigap.serve.ops import get_store, router

    monkeypatch.setenv("SIGAP_OPS_API_KEY", KEY)
    store = InMemoryStore()
    store.add_cases(
        pd.DataFrame(
            {
                "case_id": ["case-a", "case-b"],
                "application_id": ["app-a", "app-b"],
                "month": [5, 5],
                "day": ["2026-06-01", "2026-06-01"],
                "score": [0.0612, 0.0581],
                "decision_band": "review",
                "reasons": [["device type with a high fraud rate", "r2"], ["r3"]],
                "priority": [1, 2],
                "status": "assigned",
            }
        )
    )
    store.add_alerts([Alert("k-drift-6", "drift", "medium", 6, "credit_risk_score", 0.253, 0.25)])
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_store] = lambda: store
    http = TestClient(app)
    tg = FakeTelegram()
    asked = []

    def ask(q):
        asked.append(q)
        return "Jawaban copilot."

    bot = SigapBot(
        tg,
        OpsClient("http://testserver", KEY, http=http),
        {ME},
        ask=ask,
        status=lambda m: json.dumps({"month": m, "error": "no monitoring"}),
        state_path=tmp_path / "state.json",
        log=lambda s: None,
    )
    return {"bot": bot, "tg": tg, "store": store, "http": http, "asked": asked}


def msg(chat, text):
    return {"update_id": 1, "message": {"chat": {"id": chat}, "text": text, "from": {"id": USER}}}


def button(data, text="Kasus case-a\nSkor 0.06", chat=ME):
    return {
        "update_id": 2,
        "callback_query": {
            "id": "cb1",
            "data": data,
            "from": {"id": USER},
            "message": {"chat": {"id": chat}, "message_id": 7, "text": text},
        },
    }


# ---------- helpers ----------
def test_parse_chat_ids_and_split():
    assert parse_chat_ids(" 123, -456 ") == {123, -456} and parse_chat_ids("") == set()
    with pytest.raises(ValueError):
        parse_chat_ids("@agatha")
    parts = split_text("a" * 3000 + "\n\n" + "b" * 3000)
    assert len(parts) == 2 and all(len(p) <= 4000 for p in parts)
    assert all(len(b["callback_data"].encode()) <= 64 for b in decision_buttons("case-base-0761240")[0])


# ---------- per-channel receipts ----------
def test_channels_are_independent(env):
    http, h = env["http"], {"X-API-Key": KEY}
    assert len(http.get("/v1/ops/alerts?channel=telegram", headers=h).json()) == 1
    assert http.post("/v1/ops/alerts/k-drift-6/ack", json={"channel": "telegram"}, headers=h).status_code == 200
    assert http.get("/v1/ops/alerts?channel=telegram", headers=h).json() == []
    assert len(http.get("/v1/ops/alerts", headers=h).json()) == 1  # telegram is a mirror: n8n still sends it
    http.post("/v1/ops/alerts/k-drift-6/ack", json={"channel": "email"}, headers=h)
    assert http.get("/v1/ops/alerts", headers=h).json() == []
    assert http.get("/v1/ops/alerts?channel=sms", headers=h).status_code == 422


def test_push_alerts_once_per_channel(env):
    bot, tg = env["bot"], env["tg"]
    assert bot.push_alerts() == 1 and tg.sent[0]["chat"] == ME and tg.sent[0]["text"].startswith("[SIGAP]")
    assert bot.push_alerts() == 0 and len(tg.sent) == 1


# ---------- messages ----------
def test_unknown_chat_only_learns_its_id(env):
    env["bot"].handle_update(msg(STRANGER, "berapa fraud rate?"))
    assert env["asked"] == [] and str(STRANGER) in env["tg"].sent[0]["text"]


def test_commands_and_copilot(env):
    bot, tg = env["bot"], env["tg"]
    bot.handle_update(msg(ME, "/help"))
    assert tg.sent[-1]["text"] == HELP
    bot.handle_update(msg(ME, "/kasus"))
    assert "2 kasus" in tg.sent[-3]["text"] and tg.sent[-2]["buttons"] == decision_buttons("case-a")
    assert "device type with a high fraud rate" in tg.sent[-2]["text"]
    bot.handle_update(msg(ME, "/status 3"))
    assert tg.sent[-1]["text"].startswith("Bulan 3")
    bot.handle_update(msg(ME, "/status"))
    assert tg.sent[-1]["text"].startswith("Pakai")
    bot.handle_update(msg(ME, "Kenapa base-0761240 masuk review?"))
    assert env["asked"] == ["Kenapa base-0761240 masuk review?"] and tg.sent[-1]["text"] == "Jawaban copilot."
    assert tg.typed == [ME]


# ---------- decision buttons ----------
def test_decision_needs_confirmation(env):
    bot, tg, store = env["bot"], env["tg"], env["store"]
    bot.handle_update(button("d|case-a|l"))
    assert store.get_case("case-a")["status"] == "assigned"  # nothing written yet
    confirm = tg.edits[-1]["buttons"][0]
    assert [b["callback_data"] for b in confirm] == ["c|case-a|l", "x|case-a|l"]
    bot.handle_update(button("c|case-a|l", text=tg.edits[-1]["text"]))
    assert store.get_case("case-a")["status"] == "closed_legit"
    assert store.last_decision("case-a")["analyst_id"] == f"tg.{USER}"
    assert "✓ Legit tersimpan" in tg.edits[-1]["text"] and "Simpan keputusan" not in tg.edits[-1]["text"]
    bot.handle_update(button("c|case-a|l"))
    assert "sudah tercatat" in tg.edits[-1]["text"] and len(store.decisions) == 1
    bot.handle_update(button("c|case-a|f"))
    assert "sudah diputuskan" in tg.edits[-1]["text"] and len(store.decisions) == 1


def test_cancel_and_bad_buttons(env):
    bot, tg, store = env["bot"], env["tg"], env["store"]
    bot.handle_update(button("x|case-b|f"))
    assert tg.edits[-1]["buttons"] == decision_buttons("case-b")
    for data in ["c|case-b|z", "c|case b|l", "approve", "c|case-b"]:
        bot.handle_update(button(data))
        assert tg.answers[-1] == "Tombol tidak dikenal."
    bot.handle_update(button("c|case-b|l", chat=STRANGER))
    assert tg.answers[-1] == "Chat ini tidak diizinkan." and store.decisions == []


# ---------- schedule ----------
def test_cases_due_once_per_weekday(env):
    bot = env["bot"]
    wib = dt.timezone(dt.timedelta(hours=7))
    monday = dt.datetime(2026, 11, 2, 8, 29, tzinfo=wib)
    assert not bot.cases_due(monday)
    assert bot.push_cases_if_due(monday.replace(minute=31))
    assert not bot.push_cases_if_due(monday.replace(hour=15))  # already sent today
    assert not bot.cases_due(dt.datetime(2026, 11, 7, 9, 0, tzinfo=wib))  # Saturday


# ---------- Telegram client ----------
def test_telegram_errors_never_show_the_token():
    token = "123456:SECRET-token-value"  # noqa: S105 - fake token

    def handler(request):
        assert request.url.path == f"/bot{token}/sendMessage"
        return httpx.Response(200, json={"ok": False, "description": f"bad request for {token}"})

    api = TelegramAPI(token, http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(TelegramError) as err:
        api.send_message(1, "x")
    assert token not in str(err.value) and "***" in str(err.value)
    with pytest.raises(ValueError):
        TelegramAPI("")
