"""Phase 7 · latency check for the running API. TODO(Agatha).

Send N=500 requests (one application each, taken from test months) to http://127.0.0.1:8000/v1/score
with httpx, measure latency per request, print p50 / p95 / p99 and the error count.
Write the numbers and your Mac's spec into docs/RUNBOOK.md. Target: p95 < 100 ms.
"""
