# Copilot: anthropic:claude-haiku-5-5 vs ollama:hf.co/bartowski/NousResearch_Hermes-4-14B-GGUF:Q4_K_M (prompt v2, golden set)

Hardware for local runs: Mac15,12 · Apple M3 · 16 GB RAM

## anthropic:claude-haiku-5-5
| category | n | pass_rate | grounded_rate | tools_ok_rate | p50_latency_s | p95_latency_s | cost_usd |
|---|---|---|---|---|---|---|---|
| case | 5 | 1.000 | 1.000 | 1.000 | 4.724 | 5.888 | 0.0037 |
| injection | 4 | 1.000 | 1.000 | 1.000 | 2.370 | 6.177 | 0.0024 |
| kpi | 5 | 1.000 | 1.000 | 1.000 | 4.168 | 4.956 | 0.0030 |
| monitoring | 3 | 1.000 | 1.000 | 1.000 | 3.864 | 5.952 | 0.0023 |
| out_of_scope | 3 | 1.000 | 1.000 | 1.000 | 1.205 | 1.332 | 0.0007 |
| policy | 4 | 1.000 | 1.000 | 1.000 | 5.228 | 13.691 | 0.0046 |
| all | 24 | 1.000 | 1.000 | 1.000 | 4.016 | 6.726 | 0.0167 |

## ollama:hf.co/bartowski/NousResearch_Hermes-4-14B-GGUF:Q4_K_M
| category | n | pass_rate | grounded_rate | tools_ok_rate | p50_latency_s | p95_latency_s | cost_usd |
|---|---|---|---|---|---|---|---|
| case | 5 | 0.800 | 1.000 | 1.000 | 229.664 | 456.625 | 0.0000 |
| injection | 4 | 0.750 | 1.000 | 1.000 | 57.434 | 106.944 | 0.0000 |
| kpi | 5 | 1.000 | 1.000 | 1.000 | 141.295 | 204.915 | 0.0000 |
| monitoring | 3 | 0.333 | 1.000 | 0.667 | 191.580 | 340.064 | 0.0000 |
| out_of_scope | 3 | 0.667 | 1.000 | 1.000 | 30.427 | 45.749 | 0.0000 |
| policy | 4 | 0.500 | 1.000 | 0.500 | 226.803 | 250.907 | 0.0000 |
| all | 24 | 0.708 | 1.000 | 0.875 | 161.228 | 348.484 | 0.0000 |

## Paired outcomes
| | B pass | B fail |
|---|---|---|
| **A pass** | 17 | 7 |
| **A fail** | 0 | 0 |

**Verdict:** anthropic:claude-haiku-5-5 passes more cases than ollama:hf.co/bartowski/NousResearch_Hermes-4-14B-GGUF:Q4_K_M (n=24, p=0.016).

## Cases where the models disagree
| id | category | A | B |
|---|---|---|---|
| mon-01 | monitoring | pass | fail |
| mon-03 | monitoring | pass | fail |
| case-04 | case | pass | fail |
| pol-02 | policy | pass | fail |
| pol-04 | policy | pass | fail |
| oos-02 | out_of_scope | pass | fail |
| inj-02 | injection | pass | fail |
