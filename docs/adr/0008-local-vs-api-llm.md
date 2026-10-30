# ADR 0008 · Copilot model: API (Claude) vs local open-weight (Hermes via Ollama)

- Status: proposed
- Date: 2026-10-30
- Hardware for local runs: MacBook Air (Mac15,12), Apple M3, 16 GB RAM · Ollama 0.40.13 · models and licences:
  `claude-haiku-5-5` (Anthropic API, commercial terms) and `hermes3:8b` (Nous Research Hermes 3, a fine-tune of
  Llama 3.1 8B, Llama 3 community licence; 4-bit quantized build from the Ollama library)

## Context
- The copilot sends the analyst's question (masked) and the tools' outputs to the model. The outputs hold
  aggregates, policy passages and application-level model inputs with reason codes: no names, NIK, phone numbers
  or e-mails, but an application id still links them to a person, so under UU 27/2022 (Pelindungan Data
  Pribadi) they are pseudonymous personal data, not anonymous data.
- With an API model that data leaves the bank (vendor assessment, data processing agreement, cross-border
  transfer). A local open-weight model keeps it in-house but needs hardware, monitoring and someone to maintain
  it. The question for the Head of Fraud: what quality and speed do we give up to keep the data in-house?

## Evaluation design (fixed before running)
- Same graph, tools, guardrails and prompt version (`prompts/v2.md`); only `SIGAP_LLM_MODEL` changes.
- Golden set: 24 cases (kpi 5, monitoring 3, case 5, policy 4, out_of_scope 3, injection 4).
- Metrics: pass rate per category, grounded rate, tools_ok rate, p50/p95 latency, cost, whether data leaves the
  laptop.
- Statistics: paired outcomes + McNemar exact test (Dietterich 1998). With small n, "no clear difference" is a
  valid and likely result.

## Results
30 Oct 2026, one run per model, prompt v2 (`reports/copilot_eval/compare.md`).

| Category | n | Claude Haiku 5.5 | Hermes 3 8B (local) |
|---|---|---|---|
| case | 5 | 1.000 | 0.800 |
| injection | 4 | 1.000 | 0.750 |
| kpi | 5 | 1.000 | 0.800 |
| monitoring | 3 | 1.000 | 0.333 |
| out_of_scope | 3 | 1.000 | 0.000 |
| policy | 4 | 1.000 | 0.000 |
| **all** | **24** | **1.000** | **0.500** |

| Overall | Claude Haiku 5.5 | Hermes 3 8B |
|---|---|---|
| grounded rate | 1.000 | 1.000 |
| tools_ok rate | 1.000 | 0.750 |
| p50 / p95 latency (s) | 4.0 / 6.7 | 7.7 / 31.2 |
| cost of 24 questions | USD 0.017 | 0 per token (hardware not counted) |
| data leaves the laptop | yes (masked) | no |

- **Paired:** both pass 12, only Claude 12, only Hermes 0. McNemar exact p = 2 × 0.5^12 ≈ 0.0005.
  **Verdict:** Claude Haiku 5.5 passes more cases than Hermes 3 8B on this set.
- **How Hermes failed:** tool choice (no policy question reached `search_policy`; two questions were answered
  without calling any tool), and instruction following (none of the out-of-scope questions got the scope
  sentence; one was answered and stopped by the grounding guard). It never approved anything and never wrote an
  ungrounded number into a final answer: the read-only tools and the output guard held with a weaker model, so the
  failures cost usefulness, not safety.
- **Cost at bank volume (scenario):** 300 reviews a day × 3 questions ≈ 900 questions a day × USD 0.0007 ≈
  USD 0.63 a day, about USD 14 per month of 22 working days on Claude Haiku 5.5.

**Limits:** one run per model on 24 cases; prompt v2 was tuned while testing on Claude; Hermes 3 8B (2024) is an
older and much smaller model than Claude Haiku 5.5 (2026), so this compares two specific deployments, not
"local vs API" in general. A larger open-weight model (e.g. Hermes 4 14B, about 9 GB, fits in 16 GB RAM) was not
tested.

## Decision
The copilot runs on Claude Haiku 5.5 through the API, with the masking and read-only tools of ADR 0003; Hermes 3
8B is not used for analysts. A local model is re-evaluated on this golden set when either a stronger open-weight
model passes at least 90% of it on bank hardware, or a policy forbids sending even masked case data to an
external API.

## Consequences
- **Before production on the API:** vendor risk assessment and data processing agreement with the model provider,
  a record of the cross-border transfer under UU PDP, and logging of what each question sent (tool names and
  outputs, never stored answers with personal data).
- **Before any local model:** a GPU server sized for the analysts' peak (p95 31 s on a laptop is too slow), model
  and Ollama updates owned by a team, monitoring of latency and pass rate, and a licence review (Llama 3
  community licence vs Apache-2.0 models).
- **Monitor:** golden-set pass rate after every model id change (both providers retire and update models), cost
  per day against the budget, share of answers refused by the grounding guard.

## References
- Teknium et al. (2024). Hermes 3 Technical Report. https://arxiv.org/pdf/2408.11857
- Dietterich (1998). Approximate statistical tests for comparing supervised classification learning algorithms.
  https://web.engr.oregonstate.edu/~tgd/publications/dietterich-approximate-statistical-tests-nc1998.pdf
- Claude Haiku 5.5 overview (model id, pricing): https://platform.claude.com/docs/en/models/haiku-5-5/overview
- Ollama model library, hermes3: https://ollama.com/library/hermes3
- UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (peraturan.bpk.go.id)
