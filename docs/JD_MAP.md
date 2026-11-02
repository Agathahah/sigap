# Job description map

The page to open in an interview when asked "have you done X?". Each row points to the code or document that
shows it, and the result it produced.

| Requirement seen in job descriptions | Roles | Evidence in this repo | Result |
|---|---|---|---|
| Translate a business problem into model objectives and success metrics | DS, risk | [PRD](00_PRD.md) | targets fixed before modelling: recall ≥ 0.40 at 5% FPR, PR-AUC ≥ 0.10, review ≤ capacity |
| Data acquisition, licence check, lineage | DS, data eng | `src/sigap/ingest/`, [data card](02_DATA_CARD.md) | checksummed manifest, CC BY-NC-SA licence respected (no raw rows published) |
| Data quality at the door | DS, data eng | `src/sigap/quality/contract.py`, `configs/data_contract.yaml` | contract with 6 sentinel rules, quarantine with reasons |
| EDA and feature engineering without leakage | DS | [EDA findings](03_EDA_FINDINGS.md), `src/sigap/features/build.py` | point-in-time prior rates (labels known at t−2 only) |
| Advanced SQL (CTE, window functions) | DA fraud, risk | `sql/analysis/`, `sql/warehouse/004_monitoring_views.sql` | EDA queries, review queue, monitoring views |
| PySpark ETL, orchestration | data eng, DS | `src/sigap/pipeline/`, `dags/sigap_monthly.py`, [ADR 0001](adr/0001-spark-local-postgres-warehouse.md) | idempotent bronze → silver → gold, Airflow 3 DAG |
| Star schema in Postgres | data eng | [ERD](01_ERD.md), `sql/warehouse/001_schemas.sql` | 1,000,000-row fact, upsert without truncate |
| Fraud rules: hit rate, false positives, tuning | DA fraud | `src/sigap/rules/`, `configs/rules.yaml`, [decision policy](04_DECISION_POLICY.md) | 5 rules, 45.2% recall at 7.86% alerts (month 5) |
| Model building, temporal validation, calibration | DS, MLE | `src/sigap/train/`, [ADR 0002](adr/0002-temporal-split-label-lag-threshold.md), [model card](MODEL_CARD.md) | recall 0.521 at FPR 0.053 on later months, ECE 0.0034 |
| Explainability | DS | `src/sigap/explain/reasons.py` | top-3 reason codes from TreeSHAP, protected attributes never shown |
| Responsible AI, bias testing, model card | DS | `src/sigap/train/fairness.py`, [ADR 0005](adr/0005-fairness-age-predictive-equality.md), [model card](MODEL_CARD.md) | age FPR ratio 0.32 → 0.58 with reweighing, cost stated |
| Business impact, expected loss, champion–challenger | risk, lending DS | `src/sigap/policy/`, [ADR 0006](adr/0006-decision-bands-cost-capacity.md), [business memo](05_BUSINESS_MEMO.md) | 44.6% vs 31.9% fraud stopped with fewer reviews; sensitivity in every assumption |
| Stakeholder communication | all | [business memo](05_BUSINESS_MEMO.md) | one-page recommendation with asks and risks |
| MLflow tracking, registry, release gate | MLE, MLOps | `src/sigap/train/gate.py`, `configs/gate.yaml` | champion alias only after the written gate passes |
| API, Docker, CI | MLE, AI eng | `src/sigap/serve/`, `Dockerfile`, `.github/workflows/ci.yml` | p95 12.3 ms, tests of every finished phase in CI |
| Drift monitoring, late labels, retraining rule | MLE | `src/sigap/monitor/`, [monitoring replay](06_MONITORING_REPLAY.md), [runbook](RUNBOOK.md) | feature drift detected while the score stayed stable |
| Workflow automation, human in the loop | AI eng, ops | `src/sigap/ops/`, `n8n/workflows/`, [ADR 0007](adr/0007-ops-automation-n8n-whatsapp.md) | alerts sent once, decisions validated and auditable; delivery failure found and handled |
| Chat-based operations, bots, human in the loop on mobile | AI eng, ops | `src/sigap/telegram/`, `sql/warehouse/006_alert_delivery.sql`, [ADR 0009](adr/0009-telegram-bot-channel.md) | Telegram bot without a public address, per-channel receipts, decisions by button with confirmation |
| RAG, vector database, embeddings | AI eng | `src/sigap/copilot/rag.py` | POJK 12/2024 + SOP, local multilingual embeddings in pgvector, cited by page |
| Agents (LangGraph), tool calling, MCP | AI eng | `src/sigap/copilot/agent.py`, `tools.py`, `mcp_server.py`, [ADR 0003](adr/0003-copilot-read-only-tools.md) | explicit graph, 5 read-only tools, read-only database role |
| LLM evaluation, guardrails, prompt injection, PII | AI eng | `src/sigap/copilot/eval.py`, `guardrails.py`, `eval/golden.jsonl`, [ADR 0004](adr/0004-copilot-prompt-and-eval.md) | 24-case golden set, v2 24/24, eval caught a guardrail bug |
| LLM cost, latency, data residency trade-offs | AI eng | `src/sigap/copilot/budget.py`, `compare.py`, [ADR 0008](adr/0008-local-vs-api-llm.md) | API vs local model with a paired test, cost at bank volume |
| Regulation awareness (Indonesia) | risk, compliance | [SOP](policies/sop_review_pembukaan_rekening.md), ADR 0003, 0008 | POJK 12/2024 anti-fraud, UU 27/2022 PDP considered in design |
