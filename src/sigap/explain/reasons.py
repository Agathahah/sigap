"""Phase 5 · Reason codes: why was THIS application sent to review?

An analyst cannot act on "score 0.83". They can act on "device already linked to fraud; 6-hour
application burst 9x the normal rate". Reason codes come from per-row SHAP values.
"""

from __future__ import annotations


def top_reasons(contributions: dict[str, float], labels: dict[str, str] | None = None, k: int = 3) -> list[str]:
    """Phase 5 · TODO(Agatha): the k features that pushed the score UP the most.

    contributions: {feature: shap_value} for one application.
    Keep only positive values, sort descending (ties: feature name ascending), take k.
    Map each feature through `labels` (human text) when present, else keep the feature name.
    Test: tests/test_p5_metrics.py::test_top_reasons
    """
    raise NotImplementedError("TODO(Agatha) phase 5: sigap.explain.reasons.top_reasons")
