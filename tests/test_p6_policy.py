"""Phase 6 · decision bands, cost, capacity, champion vs challenger."""

import numpy as np
import pytest

from sigap.policy.cost import cost_of_decisions, decide, optimize_policy
from sigap.policy.simulate import compare_arms

pytestmark = pytest.mark.p6

COSTS = {
    "fraud_loss": 1000.0,
    "review_cost": 10.0,
    "review_catch_rate": 0.8,
    "good_decline_cost": 50.0,
    "good_review_cost": 2.0,
}


def test_decide_bands():
    d = decide(np.array([0.1, 0.5, 0.7, 0.95]), 0.5, 0.9)
    assert d.tolist() == ["approve", "review", "review", "decline"]
    assert decide(np.array([0.99]), 0.5, np.inf).tolist() == ["review"]
    with pytest.raises(ValueError):
        decide(np.array([0.1]), 0.9, 0.5)


def test_cost_by_hand():
    y = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    d = np.array(["approve", "review", "decline", "approve", "review", "review", "decline", "approve"])
    r = cost_of_decisions(y, d, COSTS)
    assert r["fraud_loss_cost"] == pytest.approx(1000 * (1 + 1 - 0.8))
    assert r["review_ops_cost"] == pytest.approx(30)
    assert r["friction_cost"] == pytest.approx(50 + 2 * 2)
    assert r["total_cost"] == pytest.approx(1200 + 30 + 54)
    assert r["review_rate"] == pytest.approx(3 / 8)
    assert r["fraud_stopped_rate"] == pytest.approx((1 + 0.8) / 3)


def _scores():
    rng = np.random.default_rng(7)
    y = np.r_[np.zeros(5000), np.ones(60)]
    p = np.r_[rng.beta(2, 12, 5000), rng.beta(5, 3, 60)]
    return y, p


def test_optimize_respects_capacity():
    y, p = _scores()
    res = optimize_policy(y, p, COSTS, max_review_rate=0.03)
    assert res["review_rate"] <= 0.03 and res["t_review"] <= res["t_decline"]
    with pytest.raises(ValueError):
        optimize_policy(y, p, COSTS, max_review_rate=-1)


def test_optimize_beats_approve_all():
    y, p = _scores()
    res = optimize_policy(y, p, COSTS, max_review_rate=0.05)
    approve_all = cost_of_decisions(y, np.full(len(y), "approve"), COSTS)["total_cost"]
    assert res["total_cost"] < approve_all


def test_compare_arms():
    y = np.array([1, 0, 0])
    arms = {
        "champion": np.array(["approve", "approve", "approve"]),
        "challenger": np.array(["review", "approve", "approve"]),
    }
    df = compare_arms(y, arms, COSTS)
    assert df["arm"].tolist() == ["champion", "challenger"]
    assert df["saving_vs_first"].tolist()[0] == 0
    assert df["saving_vs_first"].tolist()[1] == pytest.approx(1000 - (200 + 10))
