# SIGAP · Sistem Identifikasi Gejala Anomali Pengajuan

SIGAP decides what to do with each online account-opening application at a fictional Indonesian digital bank,
**approve, send to review, or decline**, keeps the fraud team informed when something needs attention, and helps
the analyst who reviews a case.

The decision is made the way a fraud team would defend it: rules are the baseline to beat, thresholds come from
the cost of fraud versus the cost of friction under the review team's capacity, labels arrive two months late,
and every model passes a written release gate before it is used.

**Status:** in development (October–November 2026). Results are added as each stage is measured on the real data,
and every number links to its MLflow run or report file.

| Layer | What it does | Built with |
|---|---|---|
| Data acquisition | Kaggle download with licence check, checksummed manifest, monthly drops, labels that arrive 2 months late | Python, Kaggle API |
| Data quality | Data contract at the door, quarantine with reasons, monthly quality report | pandas, YAML |
| Pipeline + warehouse | Bronze → silver → gold (star schema), loaded into Postgres | PySpark, Postgres, SQL |
| Rules → model | Rule baseline measured like a fraud team does, then gradient boosting with calibration, reason codes, fairness by age, release gate | scikit-learn, XGBoost, SHAP, MLflow |
| Decision policy | Approve / review / decline bands chosen by expected cost under review-team capacity; champion vs challenger replay | NumPy, pandas |
| Serving | Scoring API with validation, API key, decision log, latency budget; Docker; CI | FastAPI, Pydantic, Docker, GitHub Actions |
| Monitoring | Monthly replay: drift (PSI), late-label performance, retraining rule; orchestration; dashboard | Airflow, Postgres, Metabase |
| Fraud-ops automation | Alerts (drift, review queue over capacity, data incidents) and review cases sent to analysts; decisions written back through a validated API (human-in-the-loop) | n8n, WhatsApp Business Platform, FastAPI |
| Analyst copilot | Read-only tools over the warehouse, RAG over POJK 12/2024 and a fictional review SOP, guardrails, step and cost limits, golden-set evaluation | LangGraph, MCP, pgvector, sentence-transformers |
| Model choice | Same golden set on an API model and a local open-weight model: quality, latency, cost, data residency | Claude, Hermes (Nous Research) via Ollama |

## Data

[Bank Account Fraud (BAF) suite](https://github.com/feedzai/bank-account-fraud), Jesus et al. (2022),
*Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for ML Evaluation*, NeurIPS Datasets and Benchmarks.
Raw rows are not in this repository (see `docs/02_DATA_CARD.md` for the licence check). CI and the public demo use
BAF-shaped synthetic data from `scripts/make_synthetic.py`, which is never used to report results.

## Run

```bash
make setup            # Python 3.12 venv; Java 17 needed for Spark
cp .env.example .env  # then edit passwords
make doctor P=0       # tools ready? (P=3 adds Java 17/Spark, P=8b n8n, P=9b Ollama)
make check P=1        # acceptance tests of one phase
make help             # every command, in phase order
```

## Documents

PRD · ERD · data card · EDA findings · decision policy · business memo · model card · runbook · ADRs, in `docs/`.
