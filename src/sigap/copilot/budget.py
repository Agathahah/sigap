"""Phase 9 · Cost control for the copilot.

A copilot that loops on tools can burn the API budget in minutes. Two controls (ADR 0003/0004):
  - a step limit per question (agent.py: route_after_agent)
  - a daily budget in USD (this file): the agent stops politely when the day's budget is used up

Prices live in configs/llm.yaml (USD per million tokens). A local model (Ollama/Hermes) has price 0 here:
its cost is hardware and electricity, discussed in ADR 0008, not tokens.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from sigap.config import load_yaml


def price_for(model_spec: str) -> dict:
    """Provided. {"input_per_mtok": float, "output_per_mtok": float} for a spec like "anthropic:claude-haiku-4-5".
    Unknown models raise KeyError: add them to configs/llm.yaml with the price from the provider's pricing page."""
    return load_yaml("llm")["models"][model_spec]["price"]


def estimate_cost(usage: dict | None, price: dict) -> float:
    """USD cost of one LLM call from LangChain `AIMessage.usage_metadata` and a price in USD per 1M tokens.

    None or missing keys count as 0 tokens; negative counts raise ValueError.
    """
    usage = usage or {}
    tin, tout = usage.get("input_tokens", 0) or 0, usage.get("output_tokens", 0) or 0
    if tin < 0 or tout < 0:
        raise ValueError(f"negative token count in {usage}")
    return tin / 1e6 * price["input_per_mtok"] + tout / 1e6 * price["output_per_mtok"]


@dataclass
class CostMeter:
    """Running total of today's spend. Spending exactly the budget is allowed; going over it is not."""

    daily_budget_usd: float
    spent_usd: float = 0.0

    def add(self, cost: float) -> None:
        if cost < 0:
            raise ValueError(f"cost must be >= 0, got {cost}")
        self.spent_usd += cost

    @property
    def remaining(self) -> float:
        return max(0.0, self.daily_budget_usd - self.spent_usd)

    @property
    def exceeded(self) -> bool:
        return self.spent_usd > self.daily_budget_usd + 1e-12


def spent_today(ledger: Path, today: dt.date | None = None) -> float:
    """Today's spend from a small JSON ledger {"YYYY-MM-DD": usd}, so the budget holds across CLI runs."""
    day = (today or dt.date.today()).isoformat()
    try:
        return float(json.loads(ledger.read_text(encoding="utf-8")).get(day, 0.0))
    except (FileNotFoundError, ValueError):
        return 0.0


def record_spend(ledger: Path, cost: float, today: dt.date | None = None) -> None:
    """Add `cost` to today's entry in the ledger (keeps the last 31 days)."""
    if cost <= 0:
        return
    day = (today or dt.date.today()).isoformat()
    try:
        book = json.loads(ledger.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        book = {}
    book[day] = round(float(book.get(day, 0.0)) + cost, 6)
    book = dict(sorted(book.items())[-31:])
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(book, indent=1) + "\n", encoding="utf-8")
