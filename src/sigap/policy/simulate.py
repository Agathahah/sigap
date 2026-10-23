"""Phase 6 · Champion vs challenger on months the model never saw.

Champion  = today's rules (phase 4) used as a two-band policy (rule hit -> review, else approve).
Challenger = model + optimized bands (phase 6).
Replay test months 6-7 through both and compare money, review load and fraud stopped.
In a real bank this would be a live split (e.g. 90/10 traffic); here it is an offline replay, and the
business memo must say so.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sigap.policy.cost import cost_of_decisions  # noqa: F401


def compare_arms(y: np.ndarray, arms: dict[str, np.ndarray], costs: dict[str, float]) -> pd.DataFrame:
    """Phase 6 · TODO(Agatha): one row per arm with cost_of_decisions(...) plus an "arm" column first.

    Add "saving_vs_first" = total_cost of the FIRST arm minus this arm's total_cost (first arm = 0).
    Test: tests/test_p6_policy.py::test_compare_arms
    """
    raise NotImplementedError("TODO(Agatha) phase 6: sigap.policy.simulate.compare_arms")


def main() -> None:
    """Phase 6 · TODO(Agatha): run the replay, save reports/policy/champion_challenger_<variant>.csv,
    and a sensitivity table: re-run optimize_policy for low / base / high values of each assumption in
    configs/business.yaml. If the recommendation flips under a plausible assumption, that goes in the memo.
    """
    raise NotImplementedError("TODO(Agatha) phase 6: policy.simulate.main")


if __name__ == "__main__":
    main()
