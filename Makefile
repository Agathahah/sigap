# SIGAP · every command you run, in phase order. `make help` lists them.
PY := .venv/bin/python
DATASET := sgpjesus/bank-account-fraud-dataset-neurips-2022
FILES ?= Base.csv
P ?= 1
F ?= sql/checks/p3_gold.sql
export PYTHONPATH := src

# Load .env (git-ignored) so every command sees SIGAP_* settings. Keep .env lines simple: KEY=value, no quotes.
ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: help
help:
	@grep -hE '^[a-z0-9-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

# ---------- setup ----------
setup: ## venv (Python 3.12) + dependencies
	$${PYTHON312:-python3.12} -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements-dev.txt && $(PY) -m pip install -e .
db-up: ## start Postgres+pgvector (needs Docker Desktop and .env)
	docker compose up -d postgres
db-down: ## stop Postgres (data kept in a volume)
	docker compose down
db-psql: ## open psql inside the container
	docker compose exec postgres psql -U $${POSTGRES_USER:-sigap} -d $${POSTGRES_DB:-sigap}
db-sql: ## run a SQL file inside the container and print the result: make db-sql F=sql/checks/p3_gold.sql
	docker compose exec -T postgres psql -U $${POSTGRES_USER:-sigap} -d $${POSTGRES_DB:-sigap} -v ON_ERROR_STOP=1 < $(F)
env-secrets: ## replace every change-me value in .env with a random secret (and the Postgres password in the DB)
	@$(PY) scripts/env_secrets.py
doctor: ## check the TOOLS a phase needs (not your code): make doctor P=3 [SPARK=1]
	@P=$(if $(filter command line,$(origin P)),$(P),0) SPARK=$(SPARK) $(PY) scripts/doctor.py
review: ## definition of done for phase P (tests, data, documents): make review P=2
	@$(PY) scripts/review.py $(P)
phase-done: ## after make check P=n is green: add pn to tests/PHASES_DONE so CI protects it
	@$(PY) scripts/phase_done.py $(P)
check: ## acceptance tests of one phase, e.g. make check P=1
	$(PY) -m pytest -m p$(P) -v
test: ## all tests
	$(PY) -m pytest
lint: ## ruff lint + format check
	.venv/bin/ruff check src tests scripts dags && .venv/bin/ruff format --check src tests scripts dags

# ---------- phase 1 · acquisition ----------
data-licence: ## show dataset metadata incl. licence (read it, write it in the data card)
	mkdir -p data/raw && .venv/bin/kaggle datasets metadata -p data/raw $(DATASET) && cat data/raw/dataset-metadata.json
data-download: ## download FILES (default Base.csv) into data/raw
	$(PY) -m sigap.ingest.download --files "$(FILES)"
data-manifest: ## checksums + rows + licence -> data/raw/MANIFEST.json (LICENCE="...")
	$(PY) -m sigap.ingest.manifest build --licence "$(LICENCE)"
data-verify: ## raw files still match the manifest?
	$(PY) -m sigap.ingest.manifest verify
data-land: ## raw CSV -> monthly drops + late label feed in data/landing
	$(PY) -m sigap.ingest.landing
synth: ## synthetic BAF-shaped data for CI / public demo (never for results)
	$(PY) scripts/make_synthetic.py --rows 120000 --out data/raw_synthetic

# ---------- phase 2 · quality + EDA ----------
quality: ## validate every monthly drop against configs/data_contract.yaml
	$(PY) -m sigap.quality.contract
eda-load: ## training months 0-4 + their labels -> Postgres table eda.applications
	$(PY) -m sigap.quality.eda load
eda-sql: ## run sql/analysis/q01-q07 on eda.applications (Q=q03 for one), print and save to reports/eda/
	$(PY) -m sigap.quality.eda run $(Q)
eda: ## JupyterLab for notebooks/01_eda.ipynb
	.venv/bin/jupyter lab notebooks/

# ---------- phase 3 · Spark pipeline + warehouse ----------
bronze: ## landing_valid -> parquet (Spark)
	$(PY) -m sigap.pipeline.bronze
silver: ## clean, sentinels, dedupe (Spark)
	$(PY) -m sigap.pipeline.silver
gold: ## star schema into Postgres
	$(PY) -m sigap.pipeline.gold
pipeline: bronze silver gold ## bronze -> silver -> gold

# ---------- phase 4 · rules + features ----------
rules: ## rule baseline report
	$(PY) -m sigap.rules.engine
features: ## model matrix -> data/gold/features.parquet
	$(PY) -m sigap.features.build

# ---------- phase 5 · model ----------
train: ## train + calibrate + threshold + gate + MLflow
	$(PY) -m sigap.train.train
mlflow: ## MLflow UI on http://127.0.0.1:5050 (port 5000 is taken by AirPlay Receiver on macOS)
	.venv/bin/mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5050

# ---------- phase 6 · decision policy ----------
policy: ## cost-based bands, champion vs challenger, sensitivity
	$(PY) -m sigap.policy.simulate

# ---------- phase 7 · serving ----------
serve-prep: ## prior-rate lookup for the API -> models/current/prior_rates.json
	$(PY) -m sigap.serve.prepare
serve: ## API on http://127.0.0.1:8000/docs
	.venv/bin/uvicorn sigap.serve.app:app --reload --port 8000
load-test: ## p50/p95/p99 latency of the running API (N=500)
	$(PY) scripts/load_test.py
docker-build: ## API image
	docker build -t sigap-api:local .
docker-run: ## run the image with the current model mounted read-only (Postgres reached via host.docker.internal)
	docker run --rm --name sigap-api -p 8000:8000 --env-file .env \
	  -e SIGAP_DB_URL="$(subst localhost,host.docker.internal,$(SIGAP_DB_URL))" \
	  -v "$(CURDIR)/models/current:/app/models/current:ro" sigap-api:local

# ---------- phase 8 · monitoring ----------
replay: ## months 5-7 as if live: score, drift, late labels, retraining rule
	$(PY) -m sigap.monitor.replay
dashboard: ## Metabase on http://localhost:3000 (connect it to Postgres)
	docker compose --profile dashboard up -d

# ---------- phase 8b · ops automation (n8n + WhatsApp) ----------
ops-demo: ## ops API with in-memory demo data on :8001 (build n8n workflows before the model exists)
	SIGAP_OPS_STORE=memory .venv/bin/uvicorn sigap.serve.ops_demo:app --host 0.0.0.0 --port 8001
ops-sync: ## refresh alerts + review cases from the warehouse for month M (e.g. make ops-sync M=6)
	$(PY) -m sigap.ops.sync $(M)
n8n-up: ## n8n on http://localhost:5678 (Docker, profile ops)
	docker compose --profile ops up -d n8n
n8n-down: ## stop n8n (workflows and credentials stay in the n8n_data volume)
	docker compose --profile ops stop n8n
n8n-export: ## workflows -> n8n/workflows/*.json (credentials are NOT exported), then run make check P=8b
	docker compose --profile ops exec n8n n8n export:workflow --all --separate --pretty --output=/backup/workflows/
n8n-import: ## n8n/workflows/*.json -> n8n (e.g. on a new laptop; re-create credentials by hand)
	docker compose --profile ops exec n8n n8n import:workflow --separate --input=/backup/workflows/

# ---------- phase 9 · copilot ----------
llm-setup: ## extra dependencies for the copilot
	$(PY) -m pip install -r requirements-llm.txt
docs-download: ## POJK 12/2024 anti-fraud (public) into docs/policies
	curl -L -o docs/policies/POJK-12-2024-strategi-anti-fraud.pdf "https://ojk.go.id/id/regulasi/Documents/Pages/Penerapan-Strategi-Anti-Fraud-Bagi-Lembaga-Jasa-Keuangan/POJK%2012%20Tahun%202024%20Penerapan%20Strategi%20Anti%20Fraud%20bagi%20Lembaga%20Jasa%20Keuangan.pdf"
rag-index: ## chunk + embed policy docs into pgvector
	$(PY) -m sigap.copilot.rag
mcp: ## MCP server (stdio)
	$(PY) -m sigap.copilot.mcp_server
copilot: ## ask: make copilot Q="..."
	$(PY) -m sigap.copilot.agent "$(Q)"
copilot-eval: ## golden set on MODEL (default SIGAP_LLM_MODEL); anthropic:* costs money, ollama:* is local
	$(PY) -m sigap.copilot.eval $(if $(MODEL),--model "$(MODEL)",)

# ---------- phase 9b · local open-weight model vs API ----------
ollama-pull: ## download a local model, e.g. make ollama-pull OLLAMA_MODEL=hermes3:8b
	ollama pull $(OLLAMA_MODEL)
copilot-compare: ## compare two eval runs: make copilot-compare A=anthropic:claude-haiku-4-5 B=ollama:hermes3:8b
	$(PY) -m sigap.copilot.compare "$(A)" "$(B)"

clean: ## remove generated data (keeps raw downloads)
	rm -rf data/landing data/landing_valid data/quarantine data/bronze data/silver data/gold spark-warehouse metastore_db
