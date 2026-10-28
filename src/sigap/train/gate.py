"""Release gate: a model is promoted only if it passes limits written BEFORE training (configs/gate.yaml)."""

from __future__ import annotations

import math


def evaluate_gate(metrics: dict[str, float], gate: dict[str, dict[str, float]]) -> tuple[bool, list[str]]:
    """Check metrics against gate["min"] and gate["max"]; returns (passed, one reason per failed check)."""
    reasons = []
    for section, fails, sign in (("min", lambda v, lim: v < lim, "<"), ("max", lambda v, lim: v > lim, ">")):
        for name, limit in (gate.get(section) or {}).items():
            value = metrics.get(name)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                reasons.append(f"{name} missing")
            elif fails(value, limit):
                reasons.append(f"{name} = {value:.4f} {sign} {section} {limit}")
    return (not reasons), reasons
