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
