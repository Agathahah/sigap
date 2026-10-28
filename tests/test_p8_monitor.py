"""Phase 8 · drift."""

import numpy as np
import pandas as pd
import pytest

from sigap.monitor.psi import drift_report, psi

pytestmark = pytest.mark.p8


def test_psi_identical_is_zero():
    x = np.random.default_rng(0).normal(size=50_000)
    assert psi(x, x) == pytest.approx(0.0, abs=1e-9)


def test_psi_grows_with_shift_and_handles_nan():
    rng = np.random.default_rng(1)
    ref = rng.normal(size=50_000)
    small = psi(ref, rng.normal(0.1, 1, 50_000))
    big = psi(ref, rng.normal(1.0, 1, 50_000))
    assert 0 <= small < 0.05 < 0.25 < big
    assert np.isfinite(psi(np.r_[ref, np.nan], np.r_[rng.normal(5, 1, 1000), np.nan]))


def test_drift_report_status():
    rng = np.random.default_rng(2)
    ref = pd.DataFrame({"a": rng.normal(size=20_000), "b": rng.normal(size=20_000)})
    cur = pd.DataFrame({"a": rng.normal(size=20_000), "b": rng.normal(1.5, 1, 20_000)})
    rep = drift_report(ref, cur, ["a", "b"])
    assert rep["feature"].tolist() == ["b", "a"]
    assert rep["status"].tolist() == ["alert", "stable"]


def test_psi_sees_shift_in_binary_flags():
    rng = np.random.default_rng(3)
    ref = (rng.uniform(size=20_000) < 0.30).astype(float)
    same = (rng.uniform(size=20_000) < 0.30).astype(float)
    moved = (rng.uniform(size=20_000) < 0.60).astype(float)
    assert psi(ref, same) < 0.01 and psi(ref, moved) > 0.25


def test_dag_runs_the_monthly_chain():
    """The DAG file defines the pipeline in order (parsed without importing Airflow)."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "dags" / "sigap_monthly.py").read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "make"]
    task_ids = [c.args[0].value for c in calls]
    assert task_ids == ["quality", "bronze", "silver", "gold", "features", "replay", "ops_sync"]
    assert "quality >> bronze >> silver >> gold >> features >> replay >> ops_sync" in src


def test_replay_skips_prior_rate_lookups_in_drift():
    from types import SimpleNamespace

    from sigap.monitor.replay import top_features

    model = SimpleNamespace(features=["prior_rate_device_os", "a", "b", "prior_rate_payment_type", "c"])
    assert top_features(model, "no-such-variant", k=2) == ["a", "b"]
