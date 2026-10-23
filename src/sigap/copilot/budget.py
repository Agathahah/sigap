"""Phase 9 · Cost control for the copilot.

A copilot that loops on tools can burn the API budget in minutes. Two controls (ADR 0003/0004):
  - a step limit per question (agent.py: route_after_agent)
  - a daily budget in USD (this file): the agent stops politely when the day's budget is used up

Prices live in configs/llm.yaml (USD per million tokens). A local model (Ollama/Hermes) has price 0 here:
its cost is hardware and electricity, which you discuss in ADR 0008, not tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

from sigap.config import load_yaml


def price_for(model_spec: str) -> dict:
    """Provided. {"input_per_mtok": float, "output_per_mtok": float} for a spec like "anthropic:claude-haiku-4-5".
    Unknown models raise KeyError: add them to configs/llm.yaml with the price from the provider's pricing page."""
    return load_yaml("llm")["models"][model_spec]["price"]


def estimate_cost(usage: dict | None, price: dict) -> float:
    """Phase 9 · TODO(Agatha): USD cost of one LLM call.

    usage: LangChain `AIMessage.usage_metadata`, e.g. {"input_tokens": 1200, "output_tokens": 300, ...};
           None or missing keys count as 0 tokens.
    price: {"input_per_mtok": 1.0, "output_per_mtok": 5.0}  (USD per 1,000,000 tokens)
    cost = input_tokens / 1e6 * input_per_mtok + output_tokens / 1e6 * output_per_mtok
    Negative token counts -> ValueError.
    Test: tests/test_p9_agent.py::test_estimate_cost
    """
    raise NotImplementedError("TODO(Agatha) phase 9: sigap.copilot.budget.estimate_cost")


@dataclass
class CostMeter:
    """Phase 9 · TODO(Agatha): running total of today's spend.

    - add(cost): add a non-negative cost (ValueError if negative)
    - remaining: max(0, daily_budget_usd - spent_usd)
    - exceeded: True when spent_usd > daily_budget_usd (equal is still allowed)
    In production the spent amount would be read from the request log at startup; here it starts at spent_usd.
    Test: tests/test_p9_agent.py::test_cost_meter
    """

    daily_budget_usd: float
    spent_usd: float = 0.0

    def add(self, cost: float) -> None:
        raise NotImplementedError("TODO(Agatha) phase 9: CostMeter.add")

    @property
    def remaining(self) -> float:
        raise NotImplementedError("TODO(Agatha) phase 9: CostMeter.remaining")

    @property
    def exceeded(self) -> bool:
        raise NotImplementedError("TODO(Agatha) phase 9: CostMeter.exceeded")
