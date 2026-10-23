"""Phase 9b · comparing two models on the same golden set (pure Python, no LLM)."""

import pytest

from sigap.copilot.compare import mcnemar_exact, paired_outcomes, summarize_run, verdict

pytestmark = pytest.mark.p9b


def _r(i, cat, passed, lat, cost=0.0, grounded=True, tools=True):
    return {
        "id": i,
        "category": cat,
        "passed": passed,
        "grounded_ok": grounded,
        "tools_ok": tools,
        "latency_s": lat,
        "cost_usd": cost,
    }


RUN_A = [
    _r("k1", "kpi", True, 1.0, 0.001),
    _r("k2", "kpi", True, 3.0, 0.002),
    _r("p1", "policy", False, 2.0, 0.003, grounded=False),
    _r("i1", "injection", True, 1.5, 0.001),
]
RUN_B = [
    _r("k1", "kpi", True, 6.0),
    _r("k2", "kpi", False, 8.0, tools=False),
    _r("p1", "policy", False, 7.0),
    _r("i1", "injection", False, 5.0),
]


def test_summarize_run():
    s = summarize_run(RUN_A)
    assert list(s.index) == ["injection", "kpi", "policy", "all"]
    assert list(s.columns) == [
        "n",
        "pass_rate",
        "grounded_rate",
        "tools_ok_rate",
        "p50_latency_s",
        "p95_latency_s",
        "cost_usd",
    ]
    assert s.loc["kpi", "n"] == 2 and s.loc["kpi", "p50_latency_s"] == pytest.approx(2.0)
    assert s.loc["all", "pass_rate"] == pytest.approx(0.75) and s.loc["all", "grounded_rate"] == pytest.approx(0.75)
    assert s.loc["all", "p95_latency_s"] == pytest.approx(2.85) and s.loc["all", "cost_usd"] == pytest.approx(0.007)
    with pytest.raises(ValueError):
        summarize_run([])


def test_paired_outcomes():
    assert paired_outcomes(RUN_A, RUN_B) == {"both_pass": 1, "a_only": 2, "b_only": 0, "both_fail": 1}
    with pytest.raises(ValueError):
        paired_outcomes(RUN_A, RUN_B[:3])
    with pytest.raises(ValueError):
        paired_outcomes(RUN_A + [RUN_A[0]], RUN_B + [RUN_B[0]])


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(0, 5) == pytest.approx(0.0625)
    assert mcnemar_exact(9, 1) == pytest.approx(0.021484375)
    assert mcnemar_exact(5, 5) == 1.0
    with pytest.raises(ValueError):
        mcnemar_exact(-1, 2)


def test_verdict():
    assert verdict("claude", "hermes", {"both_pass": 1, "a_only": 2, "b_only": 0, "both_fail": 1}) == (
        "No clear difference between claude and hermes (n=4, p=0.500)."
    )
    big = {"both_pass": 10, "a_only": 9, "b_only": 1, "both_fail": 2}
    assert verdict("claude", "hermes", big) == "claude passes more cases than hermes (n=22, p=0.021)."
    assert (
        verdict("hermes", "claude", {**big, "a_only": 1, "b_only": 9})
        == "claude passes more cases than hermes (n=22, p=0.021)."
    )
