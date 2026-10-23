"""Phase 5 · metrics, fairness, gate, reason codes."""

import math

import numpy as np
import pytest

from sigap.explain.reasons import top_reasons
from sigap.train.fairness import fpr_by_group, fpr_ratio
from sigap.train.gate import evaluate_gate
from sigap.train.metrics import confusion_at, expected_calibration_error, threshold_at_fpr

pytestmark = pytest.mark.p5


def test_threshold_at_fpr():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(20_000), np.ones(200)]
    p = np.r_[rng.beta(2, 8, 20_000), rng.beta(6, 3, 200)]
    thr = threshold_at_fpr(y, p, 0.05)
    assert confusion_at(y, p, thr)["fpr"] == pytest.approx(0.05, abs=0.002)
    assert threshold_at_fpr(y, p, 0.01) > thr


def test_confusion_at():
    y = np.array([1, 1, 0, 0, 0])
    p = np.array([0.9, 0.2, 0.8, 0.1, 0.5])
    c = confusion_at(y, p, 0.5)
    assert (c["tp"], c["fp"], c["tn"], c["fn"]) == (1, 2, 1, 1)
    assert c["tpr"] == pytest.approx(0.5) and c["fpr"] == pytest.approx(2 / 3)
    assert c["precision"] == pytest.approx(1 / 3) and c["alert_rate"] == pytest.approx(0.6)
    assert confusion_at(np.zeros(3), np.zeros(3), 0.5)["precision"] == 0.0


def test_ece_perfect_and_bad():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 200_000)
    y = rng.uniform(0, 1, 200_000) < p
    assert expected_calibration_error(y, p) < 0.01
    assert expected_calibration_error(np.zeros(10), np.full(10, 0.9)) == pytest.approx(0.9)
    assert expected_calibration_error(np.array([1]), np.array([1.0])) == pytest.approx(0.0)


def test_fpr_by_group():
    y = np.array([0, 0, 0, 0, 1, 0])
    p = np.array([0.9, 0.1, 0.9, 0.9, 0.9, 0.1])
    g = np.array(["<50", "<50", ">=50", ">=50", "x", "<50"])
    out = fpr_by_group(y, p, 0.5, g)
    assert out["<50"] == pytest.approx(1 / 3) and out[">=50"] == pytest.approx(1.0)
    assert math.isnan(out["x"])


def test_fpr_ratio():
    assert fpr_ratio({"a": 0.02, "b": 0.04}) == pytest.approx(0.5)
    assert fpr_ratio({"a": 0.0, "b": 0.0}) == 1.0
    assert math.isnan(fpr_ratio({"a": 0.1, "b": float("nan")}))


def test_gate():
    gate = {"min": {"tpr": 0.4, "ratio": 0.5}, "max": {"fpr": 0.06}}
    assert evaluate_gate({"tpr": 0.5, "ratio": 0.8, "fpr": 0.05}, gate) == (True, [])
    ok, reasons = evaluate_gate({"tpr": 0.3, "fpr": 0.07}, gate)
    assert not ok
    assert reasons == ["tpr = 0.3000 < min 0.4", "ratio missing", "fpr = 0.0700 > max 0.06"]
    assert evaluate_gate({"x": 1}, {"min": {"x": 0}}) == (True, [])


def test_top_reasons():
    c = {"velocity_ratio": 0.8, "device_fraud_count": 1.2, "income": -0.5, "email_is_free": 0.8, "zip": 0.1}
    assert top_reasons(c, {"device_fraud_count": "device linked to fraud"}, k=3) == [
        "device linked to fraud",
        "email_is_free",
        "velocity_ratio",
    ]
    assert top_reasons({"a": -1.0}) == []
