"""Paths, column names and YAML loading. Plumbing only: no business logic lives here."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.getenv("SIGAP_ROOT", Path(__file__).resolve().parents[2]))
CONFIGS = ROOT / "configs"
DATA = Path(os.getenv("SIGAP_DATA", ROOT / "data"))

RAW = Path(os.getenv("SIGAP_RAW", DATA / "raw"))  # files exactly as downloaded, never edited
LANDING = DATA / "landing"  # monthly drops, the way a source system would deliver them
BRONZE = DATA / "bronze"  # landing -> parquet, typed loosely, with ingestion metadata
SILVER = DATA / "silver"  # clean, deduplicated, validated against the data contract
QUARANTINE = DATA / "quarantine"  # rows rejected by the contract, with the reason
GOLD = DATA / "gold"  # star schema + feature table
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"

KAGGLE_DATASET = "sgpjesus/bank-account-fraud-dataset-neurips-2022"
VARIANT = os.getenv("SIGAP_VARIANT", "Base")  # Base, Variant I ... Variant V

ID = "application_id"
LABEL = "is_fraud"  # renamed from BAF's fraud_bool in silver
RAW_LABEL = "fraud_bool"
MONTH = "month"

# Evaluation protocol (ADR 0002): temporal split, never random.
TRAIN_MONTHS = (0, 1, 2, 3, 4)
VALID_MONTHS = (5,)
TEST_MONTHS = (6, 7)

# Fraud is confirmed weeks after the application (chargebacks, investigations).
# In landing, a label for month m becomes available at month m + LABEL_LAG_MONTHS.
LABEL_LAG_MONTHS = int(os.getenv("SIGAP_LABEL_LAG", "2"))


def load_yaml(name: str) -> dict[str, Any]:
    """Load configs/<name>.yaml."""
    with open(CONFIGS / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def database_url() -> str:
    """Postgres URL from .env / environment (see .env.example)."""
    return os.getenv("SIGAP_DB_URL", "postgresql+psycopg://sigap:sigap@localhost:5433/sigap")
