# ADR 0008 · Copilot model: API (Claude) vs local open-weight (Hermes via Ollama)

- Status: accepted
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

## Addendum 9b+ · 3 Nov 2026: held-out set, tool router, Hermes 4 14B
The limits above left three open questions. Each was set up before running:

- **Held-out set:** 10 new cases (`eval/heldout.jsonl`: kpi, monitoring, case and policy 2 each, out-of-scope and
  injection 1 each), written after prompt v2 was frozen and never used to change it.
- **Tool router** (optional, `SIGAP_COPILOT_ROUTER`): one extra model call puts the question in a category and only
  that category's tools are bound, so a small model has fewer tools to choose from.
- **Hermes 4 14B** (Nous Research, a fine-tune of Qwen3 14B, Apache-2.0), community 4-bit build
  `hf.co/bartowski/NousResearch_Hermes-4-14B-GGUF:Q4_K_M` (about 9 GB). To fit 16 GB without swapping: Ollama
  with flash attention and an 8-bit KV cache (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`), context
  8192, replies capped at 1,024 tokens (`OLLAMA_NUM_PREDICT`), Docker limited to 4 GB. Claude and Hermes 3 ran
  without these settings.

### Results (prompt v2, one run per model and set)

| Run | Golden (24) | Held-out (10) | All (34) | p50 / p95 latency, golden (s) | p50, held-out (s) |
|---|---|---|---|---|---|
| Claude Haiku 5.5 | 24 | 9 | 33 | 4.0 / 6.7 | 5.7 |
| Claude Haiku 5.5 + router | 24 | 9 | 33 | 5.2 / 11.6 | 5.8 |
| Hermes 3 8B | 12 | 4 | 16 | 7.7 / 31.2 | 12.5 |
| Hermes 3 8B + router | 16 | 8 | 24 | 18.9 / 41.0 | 14.2 |
| Hermes 4 14B | 17 | 9 | 26 | 161.2 / 348.5 | 173.4 |

| Paired, all 34 cases (A vs B) | only A passes | only B passes | McNemar exact p |
|---|---|---|---|
| Claude vs Hermes 4 14B | 7 | 0 | 0.016 |
| Hermes 3 vs Hermes 4 14B | 0 | 10 | 0.002 |
| Hermes 3 vs Hermes 3 + router | 4 | 12 | 0.077 |
| Hermes 3 + router vs Hermes 4 14B | 3 | 5 | 0.73 |
| Claude vs Claude + router | 0 | 0 | 1.0 |

Golden-set comparisons are in `reports/copilot_eval/compare__*.md`; the 34-case counts join the golden and held-out
run files of the same model.

### What the runs show
- **Hermes 4 14B is the strongest local model tested:** 26/34 vs 16/34 for Hermes 3 8B (p = 0.002). On the held-out
  set it matched Claude (9/10, the same failed case); on the golden set Claude passes 7 cases it fails (p = 0.016).
- **How Hermes 4 failed (golden):** it answered without calling a tool three times (mon-03, pol-02, pol-04; the two
  policy answers held numbers from no tool output and were refused by the grounding guard) and four answers missed
  required content (mon-01, case-04, inj-02, and oos-02 without the scope sentence). Grounded rate 1.000 and nothing
  approved: the guardrails held again.
- **Latency is the blocker:** p50 161 s per question, the slowest 495 s. The 34 cases took about 98 minutes against
  about 3 minutes on Claude. The first full run made the laptop swap and restart, which is why the evaluation now
  writes every finished case at once and can resume (`SIGAP_EVAL_RESUME=1`).
- **Router:** it fixes tool choice where that was the small model's problem (every golden policy case now reaches
  `search_policy`; held-out 4 to 8), but it breaks other cases (kpi-04 and kpi-05 answered without a tool, kpi-h2
  routed to monitoring), adds a model call (Hermes 3 p50 7.7 to 18.9 s) and changes nothing for Claude. Over 34
  cases the gain is 12 against 4 discordant cases, p = 0.077: not shown at the 5% level.
- **pol-h1 fails for every model and setting.** The answer ("OTP", with PIN and password) is in the SOP, so a
  failure shared by all models points at retrieval or at the case, not at the model. It stays open and is not
  fixed against the held-out set; a fix needs new held-out cases.
- **Run-to-run variance:** kpi-01 failed for Hermes 4 in two earlier partial runs and passed in the full run, at
  temperature 0. One run per model limits every number in this ADR.

### Decision (9b+)
Unchanged: the copilot stays on Claude Haiku 5.5. The router stays off by default and is kept as an option for local
models. Hermes 4 14B passes 76% (26/34), below the 90% re-evaluation bar, and needs minutes per answer on this
laptop; it is the first candidate to re-run on a GPU server if a policy requires in-house processing.

## References
- Teknium et al. (2024). Hermes 3 Technical Report. https://arxiv.org/pdf/2408.11857
- Teknium et al. (2025). Hermes 4 Technical Report. https://arxiv.org/pdf/2508.18255
- Dietterich (1998). Approximate statistical tests for comparing supervised classification learning algorithms.
  https://web.engr.oregonstate.edu/~tgd/publications/dietterich-approximate-statistical-tests-nc1998.pdf
- Claude Haiku 5.5 overview (model id, pricing): https://platform.claude.com/docs/en/models/haiku-5-5/overview
- Ollama model library, hermes3: https://ollama.com/library/hermes3
- Hermes 4 14B model card: https://huggingface.co/NousResearch/Hermes-4-14B
- Ollama FAQ (flash attention, KV cache quantization): https://docs.ollama.com/faq
- UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (peraturan.bpk.go.id)
