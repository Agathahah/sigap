"""Phase 9b · Claude vs a local open-weight model (Hermes via Ollama) on the SAME golden set.

The business question: can the copilot run on our own hardware so case data never leaves the bank, and what do
we give up? Measure, per model: pass rate per category, grounded rate, correct tool use, latency, cost.

Honesty rules (write them in ADR 0008):
  - 20-30 cases is a small sample. Compare PAIRED outcomes (same case, two models) and report McNemar's exact
    test (Dietterich 1998), not "model A is better" from two percentages.
  - Same graph, same tools, same prompts, same guardrails: only the model spec changes.
  - Report the hardware (Mac model, RAM) next to local latency.

Run:  make copilot-eval MODEL=anthropic:claude-haiku-4-5
      make copilot-eval MODEL=ollama:hermes3:8b
      make copilot-compare A=anthropic:claude-haiku-4-5 B=ollama:hermes3:8b   -> reports/copilot_eval/compare.md
"""

from __future__ import annotations

import pandas as pd


def summarize_run(results: list[dict]) -> pd.DataFrame:
    """Phase 9b · TODO(Agatha): one row per category plus a last row "all".

    results: one dict per golden case with id, category, passed, grounded_ok, tools_ok (bools),
             latency_s (float), cost_usd (float).
    Index: category names sorted alphabetically, then "all".
    Columns: n, pass_rate, grounded_rate, tools_ok_rate, p50_latency_s, p95_latency_s, cost_usd (sum)
    Percentiles with numpy's default (linear) method. Empty results -> ValueError.
    Test: tests/test_p9b_compare.py::test_summarize_run
    """
    raise NotImplementedError("TODO(Agatha) phase 9b: compare.summarize_run")


def paired_outcomes(run_a: list[dict], run_b: list[dict]) -> dict:
    """Phase 9b · TODO(Agatha): match cases by id and count the four cells.

    Return {"both_pass": int, "a_only": int, "b_only": int, "both_fail": int}
    ValueError if the two runs do not contain exactly the same ids, or if an id appears twice in one run.
    Test: tests/test_p9b_compare.py::test_paired_outcomes
    """
    raise NotImplementedError("TODO(Agatha) phase 9b: compare.paired_outcomes")


def mcnemar_exact(b: int, c: int) -> float:
    """Phase 9b · TODO(Agatha): two-sided exact McNemar p-value from the discordant counts.

    b = cases only model A passed, c = cases only model B passed, n = b + c.
    Under H0 each discordant case is a fair coin: p = min(1, 2 * sum_{k=0}^{min(b,c)} C(n, k) * 0.5**n).
    n == 0 -> 1.0. Negative counts -> ValueError. Use math.comb (no scipy needed).
    Test: tests/test_p9b_compare.py::test_mcnemar_exact
    """
    raise NotImplementedError("TODO(Agatha) phase 9b: compare.mcnemar_exact")


def verdict(name_a: str, name_b: str, paired: dict, alpha: float = 0.05) -> str:
    """Phase 9b · TODO(Agatha): one honest sentence for the memo.

    p = mcnemar_exact(paired["a_only"], paired["b_only"]), n = total cases.
    p >= alpha -> f"No clear difference between {name_a} and {name_b} (n={n}, p={p:.3f})."
    p <  alpha -> f"{winner} passes more cases than {loser} (n={n}, p={p:.3f})." where the winner has more
                  "only" passes.
    Test: tests/test_p9b_compare.py::test_verdict
    """
    raise NotImplementedError("TODO(Agatha) phase 9b: compare.verdict")


def main(spec_a: str, spec_b: str) -> None:
    """Phase 9b · TODO(Agatha): read reports/copilot_eval/<spec>.jsonl for both models (written by eval.main),
    write reports/copilot_eval/compare.md: the two summaries side by side, the paired table, the verdict,
    the cases where the models disagree (id + category), and the hardware line."""
    raise NotImplementedError("TODO(Agatha) phase 9b: compare.main")


if __name__ == "__main__":
    import sys

    main(sys.argv[1], sys.argv[2])
