"""Phase 6 · From a score to a decision the business can defend.

A model gives a probability. The bank needs one of three actions per application:
    approve   open the account instantly
    review    send to a fraud analyst / step-up verification (video KYC); costs money and time
    decline   reject (or ask the customer to come to a branch)
Two thresholds make three bands:
    p < t_review -> approve;  t_review <= p < t_decline -> review;  p >= t_decline -> decline.

The thresholds are chosen by COST, under the CAPACITY of the review team, not by "0.5".
Every money value comes from configs/business.yaml, where each number is labelled as an assumption
with its reasoning (BAF has no amounts: say so, and show a sensitivity table instead of one magic number).

Run:  make policy   -> reports/policy/<variant>.json + sensitivity table
"""

from __future__ import annotations

import numpy as np

APPROVE, REVIEW, DECLINE = "approve", "review", "decline"


def decide(p: np.ndarray, t_review: float, t_decline: float) -> np.ndarray:
    """Phase 6 · TODO(Agatha): map scores to "approve" / "review" / "decline".

    Requires t_review <= t_decline (raise ValueError otherwise). t_decline may be np.inf (never decline).
    Return a numpy array of str.
    Test: tests/test_p6_policy.py::test_decide_bands
    """
    raise NotImplementedError("TODO(Agatha) phase 6: sigap.policy.cost.decide")


def cost_of_decisions(y: np.ndarray, decisions: np.ndarray, costs: dict[str, float]) -> dict[str, float]:
    """Phase 6 · TODO(Agatha): money and volumes of a set of decisions.

    costs keys: fraud_loss, review_cost, review_catch_rate, good_decline_cost, good_review_cost
    Rules:
      fraud approved                         -> fraud_loss each
      fraud reviewed: caught share = review_catch_rate (no loss); the rest -> fraud_loss each
      fraud declined                         -> no loss
      every review                           -> review_cost
      good customer declined                 -> good_decline_cost
      good customer reviewed                 -> good_review_cost (drop-off / friction)
    Return (floats):
      n, approve, review, decline, review_rate (= review / n),
      fraud_total, fraud_stopped_rate (= (declined fraud + caught reviewed fraud) / fraud_total, 0 if none),
      fraud_loss_cost, review_ops_cost, friction_cost, total_cost
    Test: tests/test_p6_policy.py::test_cost_by_hand
    """
    raise NotImplementedError("TODO(Agatha) phase 6: sigap.policy.cost.cost_of_decisions")


def optimize_policy(
    y: np.ndarray,
    p: np.ndarray,
    costs: dict[str, float],
    max_review_rate: float,
    grid: np.ndarray | None = None,
) -> dict[str, float]:
    """Phase 6 · TODO(Agatha): cheapest (t_review, t_decline) the review team can handle.

    Candidates: t_review from `grid` (default: unique quantiles of p at np.linspace(0.80, 1.0, 81));
    t_decline from the same grid PLUS np.inf; only pairs with t_review <= t_decline.
    Feasible: review_rate <= max_review_rate. Pick the lowest total_cost; on ties the lower review_rate.
    Return cost_of_decisions(...) of the winner plus keys "t_review" and "t_decline".
    Raise ValueError if no pair is feasible.
    Tests: tests/test_p6_policy.py::test_optimize_respects_capacity, ::test_optimize_beats_approve_all
    """
    raise NotImplementedError("TODO(Agatha) phase 6: sigap.policy.cost.optimize_policy")
