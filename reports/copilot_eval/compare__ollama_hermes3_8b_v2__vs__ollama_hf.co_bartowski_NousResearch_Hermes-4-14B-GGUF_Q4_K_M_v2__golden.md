# Copilot: ollama:hermes3:8b vs ollama:hf.co/bartowski/NousResearch_Hermes-4-14B-GGUF:Q4_K_M (prompt v2, golden set)

Hardware for local runs: Mac15,12 · Apple M3 · 16 GB RAM

## ollama:hermes3:8b
| category | n | pass_rate | grounded_rate | tools_ok_rate | p50_latency_s | p95_latency_s | cost_usd |
|---|---|---|---|---|---|---|---|
| case | 5 | 0.800 | 1.000 | 0.800 | 9.339 | 16.777 | 0.0000 |
| injection | 4 | 0.750 | 1.000 | 1.000 | 4.183 | 29.123 | 0.0000 |
| kpi | 5 | 0.800 | 1.000 | 1.000 | 6.750 | 18.455 | 0.0000 |
| monitoring | 3 | 0.333 | 1.000 | 0.667 | 9.080 | 34.581 | 0.0000 |
| out_of_scope | 3 | 0.000 | 1.000 | 1.000 | 7.240 | 8.067 | 0.0000 |
| policy | 4 | 0.000 | 1.000 | 0.000 | 14.919 | 16.774 | 0.0000 |
| all | 24 | 0.500 | 1.000 | 0.750 | 7.700 | 31.226 | 0.0000 |

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
| **A pass** | 12 | 0 |
| **A fail** | 5 | 7 |

**Verdict:** No clear difference between ollama:hermes3:8b and ollama:hf.co/bartowski/NousResearch_Hermes-4-14B-GGUF:Q4_K_M (n=24, p=0.062).

## Cases where the models disagree
| id | category | A | B |
|---|---|---|---|
| kpi-02 | kpi | fail | pass |
| pol-01 | policy | fail | pass |
| pol-03 | policy | fail | pass |
| oos-01 | out_of_scope | fail | pass |
| oos-03 | out_of_scope | fail | pass |
