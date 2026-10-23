"""Phase 9 · Read-only tools the copilot may call. They are the ONLY way it touches data.

Design rules (ADR 0003):
  - Read-only database role (GRANT SELECT only) for the copilot connection.
  - No free-form SQL from the LLM. Each tool runs a parameterized query you wrote; parameters are
    validated (allowed values, ranges) before the query runs.
  - Protected attributes (age, income, employment) and personal fields are never returned to the LLM.
  - Every tool returns small JSON (aggregates, top-k), never thousands of rows.

Tools to implement:
  query_kpi(metric, group_by=None, month_from=None, month_to=None)
      metric in {"fraud_rate", "alert_rate", "review_rate", "approval_rate"}; group_by in an allowlist
      (device_os, payment_type, source, month)
  get_application(application_id)       non-protected fields + score + decision + reasons from decision_log
  similar_cases(application_id, k=5)    nearest past applications (z-scored features, only months before it,
                                        k between 1 and 20) with their known outcome
  search_policy(question, k=4)          rag.retrieve -> chunks with source + page
  monitoring_status(month)              PSI alerts + TPR/FPR for that month from monitoring_monthly
"""

from __future__ import annotations

# TODO(Agatha) phase 9: implement the tools as plain Python functions first (testable without an LLM),
# then expose them through mcp_server.py.
