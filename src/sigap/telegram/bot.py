"""Phase 11 · The SIGAP Telegram bot: alerts, review cases with decision buttons, and the analyst copilot.

One process, long polling (getUpdates), so it needs no public URL: it runs on the analyst's laptop next to the
scoring API (ADR 0009). It talks to SIGAP only through the ops API with the ops key, like n8n, and to the
copilot graph of phase 9.

  every 15 minutes   GET /v1/ops/alerts?channel=telegram -> one message per alert -> POST .../ack (telegram)
  weekdays 08:30     the five highest-priority assigned cases, one message each with three buttons
  button             Legit / Fraud / Perlu info -> confirmation -> POST /v1/ops/cases/{id}/decision
  /status <bulan>    monitoring of one month, straight from the read-only tool (no LLM, no cost)
  any other text     a question to the copilot (masked, read-only, grounded, daily budget)

Only chats listed in SIGAP_TELEGRAM_CHAT_IDS are served; any other chat is told its chat id and nothing else.

Run:  make telegram-bot      (stop with Ctrl+C)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from zoneinfo import ZoneInfo

from sigap import config
from sigap.telegram.api import MAX_TEXT, OpsAPIError, OpsClient, TelegramAPI, TelegramError

CHANNEL = "telegram"
OUTCOMES = {"l": ("legit", "Legit"), "f": ("confirmed_fraud", "Fraud"), "i": ("need_info", "Perlu info")}
CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,40}$")
CONFIRM_SEP = "\n\n— "
STATE_FILE = config.ROOT / "reports" / "telegram_state.json"

HELP = (
    "SIGAP · bot analis fraud Bank Nusa Digital (fiktif)\n\n"
    "/kasus — lima kasus review prioritas tertinggi, dengan tombol keputusan\n"
    "/status 6 — ringkasan monitoring satu bulan (5–9)\n"
    "/help — bantuan ini\n\n"
    "Pesan biasa dikirim ke copilot (read-only, angka harus bersumber dari data SIGAP). "
    "Jangan menulis NIK, nomor HP, atau email nasabah."
)


def parse_chat_ids(raw: str | None) -> set[int]:
    """'123, -456' -> {123, -456}; empty -> set() (setup mode: the bot only tells chats their id)."""
    ids = set()
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part:
            if not re.fullmatch(r"-?\d{1,20}", part):
                raise ValueError(f"SIGAP_TELEGRAM_CHAT_IDS must be numeric chat ids, got {part!r}")
            ids.add(int(part))
    return ids


def split_text(text: str, limit: int = MAX_TEXT - 96) -> list[str]:
    """Split a long answer at paragraph or line breaks so every piece fits in one Telegram message."""
    text = text.strip() or "(jawaban kosong)"
    parts: list[str] = []
    while len(text) > limit:
        cut = max(text.rfind("\n\n", 0, limit), text.rfind("\n", 0, limit))
        cut = cut if cut > limit // 2 else limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    parts.append(text)
    return parts


def case_text(case: dict) -> str:
    reasons = "\n".join(f"• {r}" for r in case.get("reasons", [])) or "• (tidak ada reason code)"
    return f"Kasus {case['case_id']}\nSkor {case.get('score')} · hari {case.get('day')}\nAlasan:\n{reasons}"


def decision_buttons(case_id: str) -> list[list[dict]]:
    row = [{"text": label, "callback_data": f"d|{case_id}|{code}"} for code, (_, label) in OUTCOMES.items()]
    assert all(len(b["callback_data"].encode()) <= 64 for b in row), "callback_data is limited to 64 bytes"
    return [row]


def format_status(raw: str) -> str:
    """monitoring_status JSON -> a short message an analyst can read on a phone."""
    data = json.loads(raw)
    if "error" in data:
        return f"Bulan {data.get('month')}: {data['error']}"
    k = data["kpis"]
    lines = [f"Monitoring bulan {data['month']}"]
    if "review_rate" in k:
        lines.append(f"Review {k['review_rate']:.2%} · decline {k.get('decline_rate', 0):.2%}")
    if "reviews_per_day" in k:
        lines.append(f"Review/hari {k['reviews_per_day']:.0f} (kapasitas {data.get('review_capacity_per_day')})")
    if "score_psi" in k:
        lines.append(f"PSI skor {k['score_psi']:.3f} (alert ≥ 0.25)")
    if "recall_at_threshold" in k:
        lines.append(f"Recall {k['recall_at_threshold']:.3f} · FPR {k.get('fpr', 0):.3f}")
    if "fpr_ratio_age" in k:
        lines.append(f"Rasio FPR usia {k['fpr_ratio_age']:.2f} (batas 0.50)")
    drift = data.get("drifting_features") or []
    if drift:
        lines.append("Fitur bergeser: " + ", ".join(f"{d['feature']} {d['psi']:.3f} ({d['status']})" for d in drift))
    if "retrain_flag" in k:
        lines.append("Retraining: " + ("ya" if k["retrain_flag"] else "tidak perlu"))
    return "\n".join(lines)


class SigapBot:
    """Bot logic, independent of the network: tests pass fake Telegram, ops and copilot objects."""

    def __init__(
        self,
        tg: TelegramAPI,
        ops: OpsClient,
        allowed_chats: set[int],
        ask: Callable[[str], str] | None = None,
        status: Callable[[int], str] | None = None,
        state_path: Path = STATE_FILE,
        tz: str = "Asia/Jakarta",
        case_time: tuple[int, int] = (8, 30),
        log: Callable[[str], None] = print,
    ) -> None:
        self.tg, self.ops, self.allowed = tg, ops, allowed_chats
        self.ask = ask or copilot_answerer()
        self.status = status or default_status
        self.state_path, self.tz, self.case_time, self.log = state_path, ZoneInfo(tz), case_time, log

    # ---------- incoming updates ----------
    def handle_update(self, update: dict) -> None:
        if "callback_query" in update:
            self._on_button(update["callback_query"])
        elif "message" in update and "text" in update["message"]:
            self._on_message(update["message"])

    def _on_message(self, msg: dict) -> None:
        chat = msg["chat"]["id"]
        text = msg["text"].strip()
        if chat not in self.allowed:
            self.tg.send_message(
                chat,
                f"Chat ini belum diizinkan. Chat id: {chat}\n"
                "Tambahkan angka itu ke SIGAP_TELEGRAM_CHAT_IDS di .env, lalu jalankan ulang bot.",
            )
            self.log(f"refused chat {chat}")
            return
        command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if command in {"/start", "/help"}:
            self.tg.send_message(chat, HELP)
        elif command == "/kasus":
            self.send_cases(chat)
        elif command == "/status":
            arg = text.split()[1] if len(text.split()) > 1 else ""
            if not arg.isdigit():
                self.tg.send_message(chat, "Pakai: /status 6  (bulan 5–9 tersedia setelah replay)")
            else:
                self.tg.send_message(chat, format_status(self.status(int(arg))))
        elif command:
            self.tg.send_message(chat, "Perintah tidak dikenal. Kirim /help.")
        else:
            self.tg.typing(chat)
            for part in split_text(self.ask(text)):
                self.tg.send_message(chat, part)
            self.log(f"copilot answered chat {chat}")

    def _on_button(self, cq: dict) -> None:
        msg = cq.get("message") or {}
        chat, mid = msg.get("chat", {}).get("id"), msg.get("message_id")
        if chat not in self.allowed:
            self.tg.answer_callback(cq["id"], "Chat ini tidak diizinkan.")
            return
        parts = (cq.get("data") or "").split("|")
        if (
            len(parts) != 3
            or parts[0] not in {"d", "c", "x"}
            or parts[2] not in OUTCOMES
            or not CASE_ID.match(parts[1])
        ):
            self.tg.answer_callback(cq["id"], "Tombol tidak dikenal.")
            return
        kind, case_id, code = parts
        outcome, label = OUTCOMES[code]
        base = (msg.get("text") or f"Kasus {case_id}").split(CONFIRM_SEP)[0]
        if kind == "d":
            buttons = [
                [
                    {"text": f"Ya, simpan {label}", "callback_data": f"c|{case_id}|{code}"},
                    {"text": "Batal", "callback_data": f"x|{case_id}|{code}"},
                ]
            ]
            self.tg.edit_message(chat, mid, f"{base}{CONFIRM_SEP}Simpan keputusan: {label}?", buttons)
            self.tg.answer_callback(cq["id"])
        elif kind == "x":
            self.tg.edit_message(chat, mid, base, decision_buttons(case_id))
            self.tg.answer_callback(cq["id"], "Dibatalkan")
        else:
            analyst = f"tg.{cq['from']['id']}"
            try:
                r = self.ops.decide(case_id, outcome, analyst)
                done = "sudah tercatat sebelumnya" if r.get("idempotent") else "tersimpan"
                result = f"✓ {label} {done} · status {r.get('status')} · oleh {analyst}"
            except OpsAPIError as exc:
                reason = {404: "kasus tidak ditemukan", 409: "kasus ini sudah diputuskan"}.get(exc.status, str(exc))
                result = f"✗ Tidak disimpan: {reason}"
            self.tg.edit_message(chat, mid, f"{base}{CONFIRM_SEP}{result}")
            self.tg.answer_callback(cq["id"], result[:190])
            self.log(f"decision {case_id} {outcome}: {result[:60]}")

    # ---------- outgoing ----------
    def send_cases(self, chat: int, limit: int = 5, quiet_if_empty: bool = False) -> int:
        cases = self.ops.cases("assigned", limit)
        if not cases:
            if not quiet_if_empty:
                self.tg.send_message(chat, "[SIGAP] Tidak ada kasus assigned saat ini.")
            return 0
        self.tg.send_message(chat, f"[SIGAP] {len(cases)} kasus menunggu review (prioritas tertinggi)")
        for c in cases:
            self.tg.send_message(chat, case_text(c), decision_buttons(c["case_id"]))
        return len(cases)

    def push_alerts(self) -> int:
        """Send every alert not yet delivered on Telegram to every allowed chat, then record the receipt."""
        sent = 0
        for a in self.ops.alerts(CHANNEL):
            for chat in sorted(self.allowed):
                self.tg.send_message(chat, a["message"])
            self.ops.ack(a["alert_key"], CHANNEL)  # only after every chat accepted the message
            sent += 1
        if sent:
            self.log(f"alerts sent: {sent}")
        return sent

    def _state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def cases_due(self, now: dt.datetime) -> bool:
        local = now.astimezone(self.tz)
        return (
            local.weekday() < 5
            and (local.hour, local.minute) >= self.case_time
            and self._state().get("cases_sent") != local.date().isoformat()
        )

    def push_cases_if_due(self, now: dt.datetime) -> bool:
        if not self.allowed or not self.cases_due(now):
            return False
        for chat in sorted(self.allowed):
            self.send_cases(chat, quiet_if_empty=True)
        state = self._state() | {"cases_sent": now.astimezone(self.tz).date().isoformat()}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        return True

    # ---------- loop ----------
    def run_forever(self, alert_every_s: int = 900) -> None:
        offset, last_alerts = None, None  # None: send pending alerts right after start
        self.log(f"SIGAP bot running for {len(self.allowed)} chat(s); Ctrl+C to stop")
        while True:
            if self.allowed and (last_alerts is None or time.monotonic() - last_alerts >= alert_every_s):
                try:
                    self.push_alerts()
                except (OpsAPIError, TelegramError, OSError) as exc:
                    self.log(f"alerts: {exc}")
                last_alerts = time.monotonic()
            try:
                self.push_cases_if_due(dt.datetime.now(dt.UTC))
            except (OpsAPIError, TelegramError, OSError) as exc:
                self.log(f"cases: {exc}")
            try:
                updates = self.tg.get_updates(offset, timeout=25)
            except TelegramError as exc:
                self.log(str(exc))
                time.sleep(5)
                continue
            for u in updates:
                offset = u["update_id"] + 1
                try:
                    self.handle_update(u)
                except Exception as exc:  # noqa: BLE001 - one bad update must not stop the bot
                    self.log(f"update {u['update_id']}: {type(exc).__name__}: {exc}")
                    chat = (u.get("message") or (u.get("callback_query") or {}).get("message") or {}).get("chat", {})
                    if chat.get("id") in self.allowed:
                        self.tg.send_message(chat["id"], f"Maaf, terjadi error ({type(exc).__name__}). Coba lagi.")


def default_status(month: int) -> str:
    from sigap.copilot.tools import monitoring_status

    return monitoring_status(month)


def copilot_answerer() -> Callable[[str], str]:
    """The phase 9 copilot, built on first use and rebuilt each day (today's spend from the ledger)."""
    cache: dict = {}

    def answer(question: str) -> str:
        from sigap.copilot.agent import LEDGER, ask, build_copilot
        from sigap.copilot.budget import record_spend

        today = dt.date.today()
        if cache.get("day") != today:
            cache["graph"] = build_copilot()[0]
            cache["day"] = today
        state, _ = ask(cache["graph"], question)
        record_spend(LEDGER, state.get("cost_usd", 0.0))
        return state.get("answer") or "(tidak ada jawaban)"

    return answer


def main() -> None:
    tg = TelegramAPI(os.getenv("SIGAP_TELEGRAM_BOT_TOKEN", ""))
    ops = OpsClient(os.getenv("SIGAP_API_URL_FOR_BOT", "http://127.0.0.1:8000"), os.getenv("SIGAP_OPS_API_KEY", ""))
    allowed = parse_chat_ids(os.getenv("SIGAP_TELEGRAM_CHAT_IDS"))
    if not allowed:
        print("SIGAP_TELEGRAM_CHAT_IDS is empty: setup mode. Send /start to the bot; it replies with your chat id.")
    bot = SigapBot(tg, ops, allowed)
    try:
        bot.run_forever(alert_every_s=int(os.getenv("SIGAP_TELEGRAM_ALERT_EVERY_MIN", "15")) * 60)
    except KeyboardInterrupt:
        print("\nstopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
