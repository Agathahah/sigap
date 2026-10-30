"""Phase 9b · Claude vs a local open-weight model (Hermes via Ollama) on the SAME golden set.

The business question: can the copilot run on our own hardware so case data never leaves the bank, and what do
we give up? Measured per model: pass rate per category, grounded rate, correct tool use, latency, cost.

Honesty rules (ADR 0008):
  - 20-30 cases is a small sample. Paired outcomes (same case, two models) and McNemar's exact test
    (Dietterich 1998), not "model A is better" from two percentages.
  - Same graph, tools, prompt and guardrails: only the model spec changes.
  - The hardware (Mac model, RAM) is reported next to local latency.

Run:  make copilot-eval MODEL=anthropic:claude-haiku-5-5
      make copilot-eval MODEL=ollama:hermes3:8b
      make copilot-compare A=anthropic:claude-haiku-5-5 B=ollama:hermes3:8b   -> reports/copilot_eval/compare.md
"""

from __future__ import annotations

import json
import math
import platform
import subprocess

import numpy as np
import pandas as pd

COLUMNS = ["n", "pass_rate", "grounded_rate", "tools_ok_rate", "p50_latency_s", "p95_latency_s", "cost_usd"]


def _summary(df: pd.DataFrame) -> dict:
    lat = df["latency_s"].to_numpy(dtype=float)
    return {
        "n": len(df),
        "pass_rate": df["passed"].mean(),
        "grounded_rate": df["grounded_ok"].mean(),
        "tools_ok_rate": df["tools_ok"].mean(),
        "p50_latency_s": float(np.percentile(lat, 50)),
        "p95_latency_s": float(np.percentile(lat, 95)),
        "cost_usd": df["cost_usd"].sum(),
    }


def summarize_run(results: list[dict]) -> pd.DataFrame:
    """One row per category (alphabetical) plus "all": n, rates, p50/p95 latency (linear), total cost."""
    if not results:
        raise ValueError("no results to summarize")
    df = pd.DataFrame(results)
    rows = {cat: _summary(g) for cat, g in sorted(df.groupby("category"), key=lambda kv: kv[0])}
    rows["all"] = _summary(df)
    return pd.DataFrame.from_dict(rows, orient="index")[COLUMNS]


def paired_outcomes(run_a: list[dict], run_b: list[dict]) -> dict:
    """Counts of both_pass / a_only / b_only / both_fail over cases matched by id."""
    a = {r["id"]: bool(r["passed"]) for r in run_a}
    b = {r["id"]: bool(r["passed"]) for r in run_b}
    if len(a) != len(run_a) or len(b) != len(run_b):
        raise ValueError("an id appears twice in one run")
    if set(a) != set(b):
        raise ValueError(f"runs cover different cases: {sorted(set(a) ^ set(b))}")
    cells = {"both_pass": 0, "a_only": 0, "b_only": 0, "both_fail": 0}
    for i in a:
        key = {(True, True): "both_pass", (True, False): "a_only", (False, True): "b_only", (False, False): "both_fail"}
        cells[key[(a[i], b[i])]] += 1
    return cells


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant counts: each discordant case is a fair coin under H0."""
    if b < 0 or c < 0:
        raise ValueError("counts must be >= 0")
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) * 0.5**n
    return min(1.0, 2 * tail)


def verdict(name_a: str, name_b: str, paired: dict, alpha: float = 0.05) -> str:
    """One sentence for the memo: a difference is claimed only when McNemar's p < alpha."""
    n = sum(paired.values())
    p = mcnemar_exact(paired["a_only"], paired["b_only"])
    shown = "p<0.001" if p < 0.001 else f"p={p:.3f}"
    if p >= alpha:
        return f"No clear difference between {name_a} and {name_b} (n={n}, {shown})."
    winner, loser = (name_a, name_b) if paired["a_only"] > paired["b_only"] else (name_b, name_a)
    return f"{winner} passes more cases than {loser} (n={n}, {shown})."


def hardware() -> str:
    """Mac model, chip and RAM (best effort) for the latency line."""
    try:
        out = subprocess.run(  # noqa: S603 - fixed command, no user input
            ["/usr/sbin/sysctl", "-n", "hw.model", "machdep.cpu.brand_string", "hw.memsize"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\n")
        return f"{out[0]} · {out[1]} · {int(out[2]) / 2**30:.0f} GB RAM"
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        return f"{platform.system()} {platform.machine()}"


def _md_table(df: pd.DataFrame) -> str:
    """Markdown table without extra dependencies (rates and latencies to 3 decimals, cost to 4)."""

    def cell(col: str, v: object) -> str:
        if col == "n":
            return str(int(v))
        return f"{v:.4f}" if col == "cost_usd" else f"{v:.3f}"

    lines = ["| category | " + " | ".join(df.columns) + " |", "|---" * (len(df.columns) + 1) + "|"]
    lines += [f"| {idx} | " + " | ".join(cell(c, row[c]) for c in df.columns) + " |" for idx, row in df.iterrows()]
    return "\n".join(lines)


def _load(path) -> list[dict]:  # noqa: ANN001
    if not path.exists():
        raise SystemExit(f"{path} not found: run make copilot-eval for that model first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(spec_a: str, spec_b: str, prompt_version: str = "v1") -> None:
    """Write reports/copilot_eval/compare.md from the two eval runs (same prompt version)."""
    from sigap.copilot.eval import OUT_DIR, run_file

    run_a, run_b = _load(run_file(spec_a, prompt_version)), _load(run_file(spec_b, prompt_version))
    paired = paired_outcomes(run_a, run_b)
    a_pass = {r["id"]: r for r in run_a}
    disagree = [
        f"| {r['id']} | {r['category']} | {'pass' if a_pass[r['id']]['passed'] else 'fail'} | "
        f"{'pass' if r['passed'] else 'fail'} |"
        for r in run_b
        if bool(r["passed"]) != bool(a_pass[r["id"]]["passed"])
    ]
    md = [
        f"# Copilot: {spec_a} vs {spec_b} (prompt {prompt_version})",
        "",
        f"Hardware for local runs: {hardware()}",
        "",
        f"## {spec_a}",
        _md_table(summarize_run(run_a)),
        "",
        f"## {spec_b}",
        _md_table(summarize_run(run_b)),
        "",
        "## Paired outcomes",
        "| | B pass | B fail |",
        "|---|---|---|",
        f"| **A pass** | {paired['both_pass']} | {paired['a_only']} |",
        f"| **A fail** | {paired['b_only']} | {paired['both_fail']} |",
        "",
        f"**Verdict:** {verdict(spec_a, spec_b, paired)}",
        "",
        "## Cases where the models disagree",
        "| id | category | A | B |",
        "|---|---|---|---|",
        *(disagree or ["| none | | | |"]),
        "",
    ]
    out = OUT_DIR / "compare.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"-> {out}")


if __name__ == "__main__":
    import sys

    main(*sys.argv[1:4])
