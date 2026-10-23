"""Shared fixtures. Each test module is marked with its pipeline stage (p1 ... p10), see pyproject.toml."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def spark():
    pytest.importorskip("pyspark")
    from sigap.spark import get_spark

    s = get_spark("sigap-tests", shuffle_partitions=2)
    s.sparkContext.setLogLevel("ERROR")
    yield s
