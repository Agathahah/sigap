"""Phase 8 · public monitoring page: snapshot shaping, page content, and committed page == committed snapshot."""

import json
import re

import pytest

from sigap.monitor import site

pytestmark = pytest.mark.p8

BUSINESS = {"review_capacity_per_day": 300, "applications_per_day": 5000}
GATE = {"min": {"test_tpr_at_5fpr": 0.40, "test_fpr_ratio_age": 0.50}}
OPS = {"psi_alert": 0.25, "queue_tolerance": 0.10}
META = {"model_version": "base-test", "max_decline_rate": 0.01}


def kpi(month, apps, review, psi_f, recall=None, ratio=None):
    return {
        "month": month,
        "applications": apps,
        "approve_rate": 1 - review - 0.008,
        "review_rate": review,
        "decline_rate": 0.008,
        "reviews_per_day": review * 5000,
        "score_psi": 0.03,
        "max_feature_psi": psi_f,
        "recall_at_threshold": recall,
        "fpr": None if recall is None else 0.05,
        "fpr_ratio_age": ratio,
        "fraud_rate_labelled": None if recall is None else 0.012,
        "retrain_flag": 0.0,
    }


@pytest.fixture()
def snap():
    kpis = [
        kpi(5, 119323, 0.0575, 0.168, 0.518, 0.65),
        kpi(6, 108168, 0.06387, 0.253, 0.509, 0.60),
        kpi(7, 96843, 0.0566, 0.293, 0.532, 0.56),
        {"month": 4, "applications": None},  # a month that only holds labels is not shown
    ]
    drift = [{"month": 6, "feature": f"f{i}", "psi": 0.01 * i, "status": "stable"} for i in range(1, 9)] + [
        {"month": 6, "feature": "credit_risk_score", "psi": 0.253, "status": "alert"},
        {"month": 6, "feature": "score", "psi": 0.033, "status": "stable"},
        {"month": 5, "feature": "name_email_similarity", "psi": 0.168, "status": "watch"},
    ]
    policy = [
        {
            "arm": "champion_rules",
            "n": "205011.0",
            "review_rate": "0.0823",
            "decline": "0.0",
            "fraud_stopped_rate": "0.3186",
            "good_declined": "0.0",
            "cost_per_10k": "1297918160.5",
            "analysts_needed": "14.0",
        },
        {
            "arm": "challenger_model",
            "n": "205011.0",
            "review_rate": "0.0605",
            "decline": "1793.0",
            "fraud_stopped_rate": "0.4461",
            "good_declined": "1272.0",
            "cost_per_10k": "1081458068.1",
            "analysts_needed": "11.0",
        },
        {
            "arm": "approve_all",
            "n": "205011.0",
            "review_rate": "0",
            "decline": "0",
            "fraud_stopped_rate": "0",
            "good_declined": "0",
            "cost_per_10k": "0",
            "analysts_needed": "0",
        },
    ]
    return site.shape_snapshot(kpis, drift, policy, META, BUSINESS, GATE, OPS, generated="2026-11-03")


def test_snapshot_keeps_replayed_months_top_features_and_known_arms(snap):
    assert [m["month"] for m in snap["months"]] == [5, 6, 7]
    six = [d for d in snap["drift"] if d["month"] == 6]
    assert len(six) == site.TOP_DRIFT and six[0]["feature"] == "credit_risk_score"
    assert all(d["feature"] != "score" for d in snap["drift"])
    assert [p["arm"] for p in snap["policy"]] == ["champion_rules", "challenger_model"]
    assert snap["policy"][1]["good_declined_per_10k"] == pytest.approx(62.04, abs=0.01)
    assert snap["thresholds"]["fpr_ratio_age_min"] == 0.50
    json.dumps(snap)  # the snapshot must be plain JSON


def test_page_shows_the_numbers_and_states(snap):
    page = site.build_page(snap)
    assert "<title>SIGAP monitoring</title>" in page
    assert "324,334" in page  # applications replayed in months 5-7
    assert "319/day" in page and "over capacity" in page  # month 6 above 300 reviews a day
    assert "credit_risk_score" in page and 'class="pill alert"' in page
    assert "0.56" in page and "near limit" in page  # age FPR ratio within 0.10 of the 0.50 limit
    assert "44.6%" in page and "Rp 1,081.5 m" in page
    assert site.build_page(snap) == page  # deterministic


def test_page_is_self_contained(snap):
    page = site.build_page(snap)
    assert "<script" not in page
    assert not re.search(r'(src|href)="https?://(?!github\.com/Agathahah/sigap)', page)
    assert page.count("<svg") == 4 and "limit-label" not in page


def test_committed_page_matches_committed_snapshot():
    if not site.SNAPSHOT.exists():
        pytest.skip("no snapshot yet: run make site-data && make site")
    snap = json.loads(site.SNAPSHOT.read_text(encoding="utf-8"))
    assert site.PAGE.exists(), "run make site"
    assert site.PAGE.read_text(encoding="utf-8") == site.build_page(snap), "page is stale: run make site"
