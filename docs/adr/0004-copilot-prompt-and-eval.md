# ADR 0004 · Copilot prompt versions are chosen by a golden-set evaluation

- Status: proposed
- Date: 2026-10-30

## Context
- A prompt change can fix one answer and break three others. Without a fixed test set, "the new prompt feels
  better" is the only evidence.
- The copilot's answers can be checked automatically on four things: the right tool was called, required words
  appear, forbidden words do not, and every number is grounded in a tool output.

## Options considered
1. **Manual spot checks** after each change: cheap, not repeatable, no record.
2. **LLM-as-judge** scoring free text: flexible, but adds a second model with its own errors and cost.
3. **Golden set with rule-based checks** (`eval/golden.jsonl`, `sigap.copilot.eval.score_case`): 24 cases in six
   categories (kpi, monitoring, case, policy, out_of_scope, injection); every run writes one line per case.

## Evaluation design (fixed before running)
- Same model (`SIGAP_LLM_MODEL`), same graph, tools and guardrails; only the prompt file changes:
  `prompts/v1.md` (short rules) vs `prompts/v2.md` (tool choice per question type, exact numbers, citation
  format, fixed refusal sentences).
- Metrics: pass rate per category and overall, grounded rate, tools_ok rate, p50/p95 latency, total cost.
- Commands: `make copilot-eval PROMPT=v1` and `make copilot-eval PROMPT=v2`.

## Results
`anthropic:claude-haiku-5-5`, 30 Oct 2026, one run per prompt version, 24 cases each
(`reports/copilot_eval/anthropic_claude-haiku-5-5__v1.jsonl` and `__v2.jsonl`).

| Category | n | v1 pass | v2 pass |
|---|---|---|---|
| case | 5 | 0.800 | 1.000 |
| injection | 4 | 0.500 | 1.000 |
| kpi | 5 | 0.600 | 1.000 |
| monitoring | 3 | 0.333 | 1.000 |
| out_of_scope | 3 | 1.000 | 1.000 |
| policy | 4 | 1.000 | 1.000 |
| **all** | **24** | **0.708** | **1.000** |

| Overall | v1 | v2 |
|---|---|---|
| grounded rate | 0.792 | 1.000 |
| tools_ok rate | 1.000 | 1.000 |
| p50 / p95 latency (s) | 6.14 / 12.52 | 4.02 / 6.73 |
| cost of the run (USD) | 0.022 | 0.017 |
| answers that needed the grounding retry | 14 of 24 | 1 of 24 |

- **Paired:** 7 cases passed only with v2, none only with v1. McNemar exact test on the 7 discordant cases:
  p = 2 × 0.5^7 = 0.016.
- **Where v1 failed:** five answers had numbers that were not in any tool output (kpi-03, kpi-05, mon-03,
  case-01, inj-03), mostly rates rewritten in another form rather than invented figures; mon-01 refused after
  the retry and so missed the drifting feature; inj-02 refused the approval request but without the sentence the
  case checks for. v2's rule "copy numbers exactly as the tool returns them" removed almost all retries, which is
  also why it is faster and cheaper.
- **Defect found by the evaluation:** in the v1 run, five answers passed the graph's grounding check after the
  retry but failed the evaluation's check. The retry instruction quotes the ungrounded numbers, and the graph
  counted that message as a source, so a repeated invented number passed. Fixed on 30 Oct (the retry message is
  no longer a source; regression test `test_graph_repeated_ungrounded_number_still_refused`). The evaluation's
  own check was never affected, so the numbers above stand.

**Limits of this comparison:** the golden set and v2 were written by the same author in the same week, and
v2 contains the fixed refusal sentences that two cases check for, so part of the gain is v2 being written to the
test. One run per version, and Claude Haiku 5.5 does not accept a temperature setting, so a rerun can differ by
a case or two. 24 cases cannot show rare failures.

## Decision
The copilot uses prompt v2 (`SIGAP_COPILOT_PROMPT=v2`): it passed all 24 cases against 17 for v1, with the gains
in kpi, monitoring, case and injection coming from exact number copying and explicit refusal rules; before the
next prompt change, 8–10 new cases written after v2 are added as a held-out check.

## Consequences
- A prompt is versioned like code: `prompts/<version>.md`, chosen with `SIGAP_COPILOT_PROMPT`, and changed only
  with a new evaluation run recorded here.
- The rule-based checks miss answers that are correct in substance but worded differently, and accept answers
  that contain the right words for the wrong reason. Failures are read case by case before a decision.
- **Monitor:** rerun the golden set when the model id, a tool, or the warehouse views change.

## References
- Anthropic: Define success criteria and build evaluations,
  https://platform.claude.com/docs/en/test-and-evaluate/develop-tests
