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
    """Scores -> "approve" / "review" / "decline". t_decline may be np.inf (never decline)."""
    if t_review > t_decline:
        raise ValueError(f"t_review ({t_review}) must be <= t_decline ({t_decline})")
    p = np.asarray(p, dtype=float)
    return np.where(p >= t_decline, DECLINE, np.where(p >= t_review, REVIEW, APPROVE))


def cost_of_decisions(y: np.ndarray, decisions: np.ndarray, costs: dict[str, float]) -> dict[str, float]:
    """Money and volumes of a set of decisions under the cost assumptions.

    fraud approved -> fraud_loss; fraud reviewed -> review_catch_rate of it is stopped, the rest is lost;
    fraud declined -> no loss; every review -> review_cost; genuine declined -> good_decline_cost;
    genuine reviewed -> good_review_cost (friction, drop-off).
    """
    y = np.asarray(y).astype(int)
    d = np.asarray(decisions)
    fraud, good = y == 1, y == 0
    a, r, x = d == APPROVE, d == REVIEW, d == DECLINE
    n = float(len(y))
    catch = costs["review_catch_rate"]
    fraud_total = float(fraud.sum())
    fraud_reviewed = float((fraud & r).sum())
    lost = float((fraud & a).sum()) + (1 - catch) * fraud_reviewed
    stopped = float((fraud & x).sum()) + catch * fraud_reviewed
    fraud_loss_cost = lost * costs["fraud_loss"]
    review_ops_cost = float(r.sum()) * costs["review_cost"]
    friction_cost = (
        float((good & x).sum()) * costs["good_decline_cost"] + float((good & r).sum()) * costs["good_review_cost"]
    )
    return {
        "n": n,
        "approve": float(a.sum()),
        "review": float(r.sum()),
        "decline": float(x.sum()),
        "review_rate": float(r.sum()) / n if n else 0.0,
        "fraud_total": fraud_total,
        "fraud_stopped_rate": stopped / fraud_total if fraud_total else 0.0,
        "good_declined": float((good & x).sum()),
        "good_reviewed": float((good & r).sum()),
        "fraud_loss_cost": fraud_loss_cost,
        "review_ops_cost": review_ops_cost,
        "friction_cost": friction_cost,
        "total_cost": fraud_loss_cost + review_ops_cost + friction_cost,
    }


def optimize_policy(
    y: np.ndarray,
    p: np.ndarray,
    costs: dict[str, float],
    max_review_rate: float,
    grid: np.ndarray | None = None,
    max_decline_rate: float | None = None,
) -> dict[str, float]:
    """Cheapest (t_review, t_decline) whose review rate fits the review team's capacity.

    Grid: unique quantiles of p between the 80th and 100th percentile (81 points); t_decline also np.inf.
    Optional guardrail: at most `max_decline_rate` of applications declined automatically.
    Ties on cost go to the lower review rate. Raises ValueError when no pair fits the limits.

    Every pair is priced from cumulative counts on the sorted scores (O(1) per pair), so the full grid and the
    sensitivity runs take seconds on a million rows. The winner is re-priced with cost_of_decisions.
    """
    y, p = np.asarray(y).astype(int), np.asarray(p, dtype=float)
    if grid is None:
        grid = np.unique(np.quantile(p, np.linspace(0.80, 1.0, 81)))
    t_rev = np.sort(np.asarray(grid, dtype=float))
    t_dec = np.append(t_rev, np.inf)

    order = np.argsort(p)
    p_sorted, y_sorted = p[order], y[order]
    n, fraud_total = len(p), int(y.sum())
    frauds_below = np.concatenate([[0], np.cumsum(y_sorted)])  # frauds among the k lowest scores

    def at_or_above(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        k = np.searchsorted(p_sorted, t, side="left")
        return n - k, fraud_total - frauds_below[k]

    n_r, f_r = at_or_above(t_rev)[0][:, None], at_or_above(t_rev)[1][:, None]
    n_d, f_d = at_or_above(t_dec)[0][None, :], at_or_above(t_dec)[1][None, :]
    review, fraud_rev = n_r - n_d, f_r - f_d
    fraud_appr = fraud_total - f_r
    good_dec, good_rev = n_d - f_d, review - fraud_rev
    catch = costs["review_catch_rate"]
    total = (
        (fraud_appr + (1 - catch) * fraud_rev) * costs["fraud_loss"]
        + review * costs["review_cost"]
        + good_dec * costs["good_decline_cost"]
        + good_rev * costs["good_review_cost"]
    )
    rate = review / n
    feasible = (t_rev[:, None] <= t_dec[None, :]) & (rate <= max_review_rate)
    if max_decline_rate is not None:
        feasible &= np.broadcast_to(n_d / n <= max_decline_rate, feasible.shape)
    if not feasible.any():
        raise ValueError(f"no threshold pair keeps the review rate under {max_review_rate}")
    keys = np.where(feasible, total, np.inf)
    best_cost = keys.min()
    cand = np.argwhere(keys == best_cost)
    i, j = min(cand, key=lambda ij: rate[ij[0], ij[1]])
    t_r, t_d = float(t_rev[i]), float(t_dec[j])
    return {**cost_of_decisions(y, decide(p, t_r, t_d), costs), "t_review": t_r, "t_decline": t_d}
