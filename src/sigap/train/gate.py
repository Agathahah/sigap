"""Phase 5 · Release gate: a model is promoted only if it passes rules written BEFORE training.

configs/gate.yaml example:
    min:
      test_tpr_at_5fpr: 0.40      # must catch at least 40% of fraud at 5% FPR
      test_fpr_ratio_age: 0.50    # set after you write ADR 0005, not after you see the result
    max:
      test_fpr: 0.06              # threshold chosen on valid must still hold on test
      test_ece: 0.05
"""

from __future__ import annotations


def evaluate_gate(metrics: dict[str, float], gate: dict[str, dict[str, float]]) -> tuple[bool, list[str]]:
    """Phase 5 · TODO(Agatha): check metrics against gate["min"] and gate["max"].

    Return (passed, reasons). One reason per failed check, formatted exactly:
        "<metric> = <value:.4f> < min <limit>"   or   "<metric> = <value:.4f> > max <limit>"
    A metric named in the gate but missing from `metrics` fails with "<metric> missing".
    Either section may be absent.
    Test: tests/test_p5_metrics.py::test_gate
    """
    raise NotImplementedError("TODO(Agatha) phase 5: sigap.train.gate.evaluate_gate")
