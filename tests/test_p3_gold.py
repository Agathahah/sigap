"""Phase 3 · gold star schema: point-in-time labels and derived dimension attributes (no Postgres needed)."""

import pandas as pd
import pytest

pytestmark = pytest.mark.p3


def test_labels_as_of_hides_labels_that_have_not_arrived():
    from sigap.pipeline.gold import labels_as_of

    labels = pd.DataFrame(
        {"application_id": ["a", "b", "c"], "is_fraud": [1, 0, 1], "month": [3, 4, 5], "available_month": [5, 6, 7]}
    )
    assert set(labels_as_of(labels, 6)["application_id"]) == {"a", "b"}
    assert labels_as_of(labels, 4).empty


def test_month_dimension_marks_label_complete_with_lag():
    from sigap.pipeline.gold import month_dimension

    dim = month_dimension(list(range(8)), as_of=7, lag=2).set_index("month_index")["label_complete"]
    assert dim.loc[5] and not dim.loc[6] and not dim.loc[7]


def test_age_band_and_income_decile():
    from sigap.pipeline.gold import age_band, income_decile

    assert age_band(pd.Series([10, 20, 30, 40, 50, 60, 90])).tolist() == [
        "<30",
        "<30",
        "30-39",
        "40-49",
        "50-59",
        "60+",
        "60+",
    ]
    assert income_decile(pd.Series([0.1, 0.5, 0.9])).tolist() == [1, 5, 9]


def test_fact_frame_keeps_one_row_per_application_and_null_labels():
    from sigap.pipeline.gold import MEASURES, build_fact_frame

    row = {c: 0 for c in MEASURES}
    row.update(
        application_id="a",
        month=7,
        customer_age=50,
        income=0.3,
        source="INTERNET",
        payment_type="AA",
        device_os="linux",
        keep_alive_session=1,
        email_is_free=0,
        employment_status="CA",
        housing_status="BA",
    )
    apps = pd.DataFrame([row, {**row, "application_id": "b", "month": 3}])
    labels = pd.DataFrame(
        {"application_id": ["a", "b"], "is_fraud": [1, 0], "month": [7, 3], "available_month": [9, 5]}
    )
    fact = build_fact_frame(apps, labels, as_of=7).set_index("application_id")
    assert len(fact) == 2
    assert pd.isna(fact.loc["a", "is_fraud"]) and fact.loc["b", "is_fraud"] == 0
    assert fact.loc["a", "age_band"] == "50-59" and fact.loc["a", "income_decile"] == 3
