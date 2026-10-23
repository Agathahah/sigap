# ADR 0008 · Copilot model: API (Claude) vs local open-weight (Hermes via Ollama)

- Status: proposed
- Date:
- Hardware for local runs: _(Mac model, chip, RAM)_ · Ollama version: _ · models and licences: _

## Context
_Business question: can the analyst copilot run on our own hardware so case data never leaves the bank?
What would we give up (quality, latency, maintenance)? Why does this matter for a bank (data residency,
vendor dependency, cost at scale)?_

## Evaluation design (fixed before running)
- Same graph, tools, prompt version and guardrails; only `SIGAP_LLM_MODEL` changes.
- Golden set: _n_ cases (kpi / case / policy / out_of_scope / injection).
- Metrics: pass rate per category, grounded rate, tools_ok rate, p50/p95 latency, cost per 100 questions,
  data leaves laptop (yes/no).
- Statistics: paired outcomes + McNemar exact test (Dietterich 1998). With small n, "no clear difference" is a
  valid and likely result.

## Results
_Paste the table from reports/copilot_eval/compare.md and the verdict sentence. Every number links to that file._

## Decision
_One sentence (e.g. which model for which use, or "API for now, revisit when ...")._

## Consequences
_What you would need before running a local model in production (GPU server, monitoring, model updates,
licence review: Llama 3 Community License vs Apache-2.0)._
