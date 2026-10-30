"""Phase 9 · Evaluating the copilot like a model: a golden set, a score, a version.

eval/golden.jsonl, one case per line:
  {"id": "kpi-01", "category": "kpi|case|policy|monitoring|out_of_scope|injection", "question": "...",
   "expected_tools": ["query_kpi"], "must_contain": ["device_os"], "must_not_contain": ["sudah disetujui"]}

A run produces, per case, the tools called, the answer, latency and cost; score_case turns that into four
checks. Prompt versions (prompts/v1.md, v2.md) are compared on the same set (ADR 0004); models are compared in
phase 9b (ADR 0008).

Run:  make copilot-eval                                   (model from SIGAP_LLM_MODEL, prompt v1)
      make copilot-eval MODEL=ollama:hermes3:8b PROMPT=v2
Results: reports/copilot_eval/<model>__<prompt>.jsonl  (no answers or tool outputs are written: they may hold data)
"""

from __future__ import annotations

import argparse
import json
import os
import re

from sigap import config
from sigap.copilot.guardrails import ungrounded_numbers

GOLDEN = config.ROOT / "eval" / "golden.jsonl"
OUT_DIR = config.ROOT / "reports" / "copilot_eval"


def score_case(case: dict, result: dict) -> dict:
    """Four checks for one case and their conjunction.

    tools_ok      every tool in expected_tools was called (order ignored; [] means none required)
    contains_ok   every must_contain string appears in the answer (case-insensitive)
    forbidden_ok  no must_not_contain string appears in the answer (case-insensitive)
    grounded_ok   every number in the answer appears in a tool output (result["tool_outputs"])
    """
    answer = result.get("answer", "").lower()
    called = set(result.get("tools_called", []))
    checks = {
        "tools_ok": set(case.get("expected_tools", [])) <= called,
        "contains_ok": all(s.lower() in answer for s in case.get("must_contain", [])),
        "forbidden_ok": not any(s.lower() in answer for s in case.get("must_not_contain", [])),
        "grounded_ok": not ungrounded_numbers(result.get("answer", ""), result.get("tool_outputs", [])),
    }
    checks["passed"] = all(checks.values())
    return checks


def load_golden(path=GOLDEN) -> list[dict]:  # noqa: ANN001
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids in the golden set")
    return cases


def run_file(spec: str, prompt_version: str):  # noqa: ANN201
    return OUT_DIR / f"{re.sub(r'[^A-Za-z0-9._-]+', '_', spec)}__{prompt_version}.jsonl"


def main() -> None:
    from sigap.copilot.agent import ask, build_copilot
    from sigap.copilot.budget import record_spend
    from sigap.copilot.compare import summarize_run

    parser = argparse.ArgumentParser(description="Run the golden set through the copilot")
    parser.add_argument("--model", default=os.getenv("SIGAP_LLM_MODEL", "anthropic:claude-haiku-5-5"))
    parser.add_argument("--prompt", default=os.getenv("SIGAP_COPILOT_PROMPT", "v1"))
    parser.add_argument("--only", default="", help="comma-separated case ids (debugging)")
    args = parser.parse_args()

    from sigap.copilot.agent import LEDGER

    cases = load_golden()
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    graph, meter, spec, version = build_copilot(args.model, args.prompt)
    out = run_file(spec, version)
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with out.open("w", encoding="utf-8") as fh:
        for case in cases:
            state, latency = ask(graph, case["question"])
            record_spend(LEDGER, state.get("cost_usd", 0.0))
            # the question counts as a source: echoing "bulan 5" or an application id is not invented
            scored = score_case(
                case,
                {
                    "answer": state.get("answer", ""),
                    "tools_called": state.get("tools_called", []),
                    "tool_outputs": [*state.get("tool_outputs", []), case["question"]],
                },
            )
            row = {
                "id": case["id"],
                "category": case["category"],
                "model": spec,
                "prompt_version": version,
                "tools_called": state.get("tools_called", []),
                **scored,
                "stopped_reason": state.get("stopped_reason"),
                "steps": state.get("steps", 0),
                "retries": state.get("retries", 0),
                "latency_s": round(latency, 3),
                "cost_usd": round(state.get("cost_usd", 0.0), 6),
            }
            results.append(row)
            fh.write(json.dumps(row) + "\n")
            mark = "PASS" if row["passed"] else "fail"
            failed = [k for k in ("tools_ok", "contains_ok", "forbidden_ok", "grounded_ok") if not row[k]]
            reason = row["stopped_reason"] or ""
            print(f"  {mark}  {case['id']:<10} {reason:<10} {row['latency_s']:>6.2f}s  {' '.join(failed)}")
            if meter.exceeded:
                print("daily budget used up: stopping the run early")
                break
    summary = summarize_run(results)
    print(f"\n{spec} · prompt {version} · {len(results)} cases -> {out.relative_to(config.ROOT)}\n")
    print(summary.to_string(float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
