"""Phase 9 · Evaluating the copilot like a model: a golden set, a score, a version.

eval/golden.jsonl, one case per line:
  {"id": "kpi-01", "question": "...", "expected_tools": ["query_kpi"], "must_contain": ["device_os"],
   "must_not_contain": ["approve"], "category": "kpi|case|policy|out_of_scope|injection"}

A run produces, per case: which tools were called, the final answer, the tool outputs, latency and cost.
score_case turns that into pass/fail checks. Compare prompt versions (prompts/v1.md vs v2.md) on the same set
and record the table in docs/adr/0004-copilot-prompt.md.

Run:  make copilot-eval   (calls the LLM API: costs money, keep the set small, ~30 cases)
"""

from __future__ import annotations

from sigap.copilot.guardrails import ungrounded_numbers  # noqa: F401


def score_case(case: dict, result: dict) -> dict:
    """Phase 9 · TODO(Agatha): checks for one case.

    result has: "tools_called" (list[str]), "answer" (str), "tool_outputs" (list[str]).
    Return:
      tools_ok      every tool in case["expected_tools"] was called (order ignored; [] means "no tool required")
      contains_ok   every string in case.get("must_contain", []) appears in answer (case-insensitive)
      forbidden_ok  no string in case.get("must_not_contain", []) appears in answer (case-insensitive)
      grounded_ok   ungrounded_numbers(answer, tool_outputs) is empty
      passed        all four are True
    Test: tests/test_p9_copilot.py::test_score_case
    """
    raise NotImplementedError("TODO(Agatha) phase 9: sigap.copilot.eval.score_case")


def main() -> None:
    """Phase 9 · TODO(Agatha): run every golden case through the agent, score, print a table.

    - Model from `--model` (default env SIGAP_LLM_MODEL), e.g. anthropic:claude-haiku-4-5 or ollama:hermes3:8b.
      Same graph, tools and prompt for every model: only the spec changes (phase 9b compares them).
    - For each case write one JSON line to reports/copilot_eval/<model spec with ":" replaced by "_">.jsonl:
      id, category, model, prompt_version, tools_called, passed, tools_ok, contains_ok, forbidden_ok,
      grounded_ok, stopped_reason, latency_s, cost_usd. Never write the raw tool outputs (they may hold data).
    - Print pass rate per category, p50/p95 latency and total cost (sigap.copilot.compare.summarize_run).
    """
    raise NotImplementedError("TODO(Agatha) phase 9: copilot.eval.main")


if __name__ == "__main__":
    main()
