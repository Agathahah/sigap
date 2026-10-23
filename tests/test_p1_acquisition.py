"""Phase 1 · acquisition: checksums, manifest, deterministic ids, landing feeds without label leakage."""

import hashlib

import pandas as pd
import pytest

from sigap.ingest import download, landing, manifest

pytestmark = pytest.mark.p1


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "a.csv"
    f.write_bytes(b"x,y\n1,2\n" * 50_000)
    assert manifest.sha256_file(f, chunk_size=1000) == hashlib.sha256(f.read_bytes()).hexdigest()


def test_count_rows_excludes_header(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x,y\n1,2\n3,4\n")
    e = tmp_path / "empty.csv"
    e.write_text("")
    assert manifest.count_rows(f) == 2
    assert manifest.count_rows(e) == 0


def test_manifest_fields(tmp_path):
    (tmp_path / "b.csv").write_text("x\n1\n")
    (tmp_path / "a.csv").write_text("x\n1\n2\n")
    m = manifest.build_manifest([tmp_path / "b.csv", tmp_path / "a.csv"], "kaggle:x/y", "CC-TEST")
    assert m["source"] == "kaggle:x/y" and m["licence"] == "CC-TEST" and "T" in m["created_at"]
    assert [f["name"] for f in m["files"]] == ["a.csv", "b.csv"]
    assert m["files"][0]["rows"] == 2 and m["files"][0]["bytes"] == 6 and len(m["files"][0]["sha256"]) == 64


def test_verify_detects_change_and_missing(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n")
    (tmp_path / "b.csv").write_text("x\n2\n")
    m = manifest.build_manifest([tmp_path / "a.csv", tmp_path / "b.csv"], "s", "l")
    assert manifest.verify_manifest(m, tmp_path) == []
    (tmp_path / "a.csv").write_text("x\n999\n")
    (tmp_path / "b.csv").unlink()
    assert manifest.verify_manifest(m, tmp_path) == ["changed: a.csv", "missing: b.csv"]


def test_kaggle_cmd_is_a_safe_list(tmp_path):
    cmd = download.kaggle_download_cmd("owner/slug", "Variant I.csv", tmp_path)
    assert isinstance(cmd, list) and all(isinstance(c, str) for c in cmd)
    assert cmd[:3] == ["kaggle", "datasets", "download"]
    assert "Variant I.csv" in cmd and "owner/slug" in cmd and str(tmp_path) in cmd


def _raw(n=10):
    return pd.DataFrame(
        {
            "income": [0.1 * (i % 9 + 1) for i in range(n)],
            "fraud_bool": [i % 5 == 0 for i in range(n)],
            "month": [i % 4 for i in range(n)],
        }
    )


def test_application_id_deterministic_and_unique():
    raw = _raw()
    a = landing.add_application_id(raw, "Variant I")
    b = landing.add_application_id(raw, "Variant I")
    assert list(a.columns)[0] == "application_id"
    assert a["application_id"].tolist() == b["application_id"].tolist()
    assert a["application_id"].is_unique
    assert a["application_id"].iloc[3] == "variant_i-0000003"
    assert "application_id" not in raw.columns  # input untouched


def test_label_feed_is_lagged():
    df = landing.add_application_id(_raw(), "Base")
    feed = landing.make_label_feed(df, lag_months=2)
    assert list(feed.columns) == ["application_id", "is_fraud", "month", "available_month"]
    assert (feed["available_month"] == feed["month"] + 2).all()
    assert set(feed["is_fraud"].unique()) <= {0, 1}


def test_landing_has_no_label_leak(tmp_path):
    df = landing.add_application_id(_raw(12), "Base")
    counts = landing.write_landing(df, tmp_path, lag_months=1)
    assert counts == {"applications": 12, "labels": 12}
    months = sorted(p.name for p in (tmp_path / "applications").iterdir())
    assert months == ["month=00", "month=01", "month=02", "month=03"]
    for p in (tmp_path / "applications").rglob("part.csv"):
        assert "fraud_bool" not in pd.read_csv(p).columns
    assert (tmp_path / "labels" / "available_month=01" / "part.csv").exists()
    landing.write_landing(df, tmp_path, lag_months=1)  # re-run must not duplicate
    total = sum(len(pd.read_csv(p)) for p in (tmp_path / "applications").rglob("part.csv"))
    assert total == 12
