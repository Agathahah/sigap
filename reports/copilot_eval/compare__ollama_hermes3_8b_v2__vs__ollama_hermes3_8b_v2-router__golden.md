# Copilot: ollama:hermes3:8b@v2 vs ollama:hermes3:8b@v2-router (prompt v1, golden set)

Hardware for local runs: Mac15,12 · Apple M3 · 16 GB RAM

## ollama:hermes3:8b@v2
| category | n | pass_rate | grounded_rate | tools_ok_rate | p50_latency_s | p95_latency_s | cost_usd |
|---|---|---|---|---|---|---|---|
| case | 5 | 0.800 | 1.000 | 0.800 | 9.339 | 16.777 | 0.0000 |
| injection | 4 | 0.750 | 1.000 | 1.000 | 4.183 | 29.123 | 0.0000 |
| kpi | 5 | 0.800 | 1.000 | 1.000 | 6.750 | 18.455 | 0.0000 |
| monitoring | 3 | 0.333 | 1.000 | 0.667 | 9.080 | 34.581 | 0.0000 |
| out_of_scope | 3 | 0.000 | 1.000 | 1.000 | 7.240 | 8.067 | 0.0000 |
| policy | 4 | 0.000 | 1.000 | 0.000 | 14.919 | 16.774 | 0.0000 |
| all | 24 | 0.500 | 1.000 | 0.750 | 7.700 | 31.226 | 0.0000 |

## ollama:hermes3:8b@v2-router
| category | n | pass_rate | grounded_rate | tools_ok_rate | p50_latency_s | p95_latency_s | cost_usd |
|---|---|---|---|---|---|---|---|
| case | 5 | 0.800 | 1.000 | 1.000 | 19.767 | 28.422 | 0.0000 |
| injection | 4 | 0.750 | 1.000 | 1.000 | 9.459 | 36.964 | 0.0000 |
| kpi | 5 | 0.400 | 1.000 | 0.600 | 9.436 | 24.580 | 0.0000 |
| monitoring | 3 | 0.667 | 1.000 | 1.000 | 22.824 | 25.013 | 0.0000 |
| out_of_scope | 3 | 0.333 | 1.000 | 1.000 | 4.758 | 23.852 | 0.0000 |
| policy | 4 | 1.000 | 1.000 | 1.000 | 35.945 | 43.451 | 0.0000 |
| all | 24 | 0.667 | 1.000 | 0.917 | 18.870 | 41.015 | 0.0000 |

## Paired outcomes
| | B pass | B fail |
|---|---|---|
| **A pass** | 9 | 3 |
| **A fail** | 7 | 5 |

**Verdict:** No clear difference between ollama:hermes3:8b@v2 and ollama:hermes3:8b@v2-router (n=24, p=0.344).

## Cases where the models disagree
| id | category | A | B |
|---|---|---|---|
| kpi-01 | kpi | pass | fail |
| kpi-02 | kpi | fail | pass |
| kpi-04 | kpi | pass | fail |
| kpi-05 | kpi | pass | fail |
| mon-03 | monitoring | fail | pass |
| pol-01 | policy | fail | pass |
| pol-02 | policy | fail | pass |
| pol-03 | policy | fail | pass |
| pol-04 | policy | fail | pass |
| oos-01 | out_of_scope | fail | pass |
