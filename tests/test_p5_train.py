"""Phase 5 · training helpers: fairness reweighing, comparison with rules, the saved scoring artefact."""

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.p5


def test_reweigh_only_genuine_50_plus():
    from sigap.train.train import reweigh

    w = reweigh(np.array([0, 0, 1, 1]), np.array([60, 30, 60, 30]), 4.0)
    assert w.tolist() == [4.0, 1.0, 1.0, 1.0]


def test_recall_at_alert_rate():
    from sigap.train.train import recall_at_alert_rate

    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.1, 0.2, 0.3, 0.05, 0.01, 0.02, 0.03, 0.04])
    assert recall_at_alert_rate(y, p, 0.2) == pytest.approx(0.5)  # top 2 = 0.9 (fraud) and 0.8 (genuine)
    assert recall_at_alert_rate(y, p, 0.0) == 0.0


def test_evaluate_has_every_gate_metric():
    from sigap import config
    from sigap.train.train import evaluate

    rng = np.random.default_rng(0)
    y = (rng.uniform(size=2000) < 0.1).astype(int)
    p = np.clip(0.1 + 0.5 * y + rng.normal(0, 0.2, 2000), 0, 1)
    m = evaluate(y, p, 0.5, rng.integers(10, 90, 2000), "test")
    m["score_psi_test_vs_train"] = 0.0
    gate = config.load_yaml("gate")
    assert set(gate["min"]) | set(gate["max"]) <= set(m)


def test_model_artefact_roundtrip(tmp_path):
    xgb = pytest.importorskip("xgboost")
    from sigap.train.model import SigapModel, load_model
    from sigap.train.train import calibrate

    rng = np.random.default_rng(1)
    X = pd.DataFrame({"a": rng.normal(size=600), "b": rng.normal(size=600)}).astype("float32")
    y = (X["a"] + rng.normal(0, 0.5, 600) > 1).astype(int).to_numpy()
    booster = xgb.XGBClassifier(n_estimators=20, max_depth=2).fit(X, y)
    model = SigapModel(calibrate(booster, X, y), booster, ["a", "b"], 0.5, "test-v1")
    model.save(tmp_path)
    loaded = load_model(tmp_path)
    np.testing.assert_allclose(loaded.score(X[["b", "a"]]), model.score(X))  # column order does not matter
    assert loaded.contributions(X.head(3)).shape == (3, 2)
    assert (tmp_path / "metadata.json").exists()


def test_analyst_reasons_hide_protected_and_read_well():
    from sigap.explain.reasons import analyst_reasons

    c = {"customer_age": 2.0, "employment_status__CA": 1.5, "payment_type__AC": 0.9, "days_since_request": 0.5}
    assert analyst_reasons(c) == ["payment type = AC", "days between request and application"]
