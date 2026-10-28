"""Definition-of-done check for one stage: `make review P=2`.

Each line checks one deliverable of the stage (tests, data artefacts, documents) and prints OK or MISSING with
what to do. Exit code 1 when something is missing.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"(?<![\w*`])_[A-Za-z][^_\n]{2,}_(?![\w*`])")  # template prompts written as _..._
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, what: str, fix: str = "") -> None:
    RESULTS.append((bool(ok), what, fix))


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def tests_pass(marker: str) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-m", marker, "-q", "-p", "no:cacheprovider"]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode == 0  # noqa: S603


def phase_done(marker: str) -> bool:
    lines = [ln for ln in read("tests/PHASES_DONE").splitlines() if not ln.lstrip().startswith("#")]
    return marker in re.findall(r"p\d+b?", " ".join(lines))


def doc_filled(rel: str, min_chars: int = 400) -> bool:
    text = read(rel)
    return len(text) >= min_chars and not PLACEHOLDER.search(text)


def review_p0() -> None:
    check(doc_filled("docs/00_PRD.md"), "PRD filled (no template prompts left)", "edit docs/00_PRD.md")
    erd = read("docs/01_ERD.md")
    check("erDiagram" in erd and "Grain" in erd, "ERD draft with the grain of the fact table", "edit docs/01_ERD.md")


def review_p1() -> None:
    check(tests_pass("p1"), "make check P=1 green", "make check P=1 and read the failing test")
    mpath = ROOT / "data" / "raw" / "MANIFEST.json"
    m = json.loads(mpath.read_text()) if mpath.exists() else {}
    files = m.get("files", [])
    check(
        bool(m.get("licence")) and files and all(f.get("rows") and len(f.get("sha256", "")) == 64 for f in files),
        "MANIFEST.json has licence, rows and sha256",
        'make data-manifest LICENCE="CC-BY-NC-SA-4.0"',
    )
    landing = ROOT / "data" / "landing" / "base"
    check(
        len(list((landing / "applications").glob("month=*/part.csv"))) == 8,
        "8 monthly drops in data/landing",
        "make data-land",
    )
    card = read("docs/02_DATA_CARD.md")
    check(
        "CC BY-NC-SA" in card and "1,000,000 rows" in card,
        "data card: source, licence and file filled",
        "update docs/02_DATA_CARD.md",
    )
    check(phase_done("p1"), "p1 in tests/PHASES_DONE", "make phase-done P=1")


def review_p2() -> None:
    check(tests_pass("p2"), "make check P=2 green", "make check P=2")
    c = yaml.safe_load(read("configs/data_contract.yaml") or "{}") or {}
    cols, sentinels = c.get("columns", {}), c.get("sentinels", {})
    n_sent = len(sentinels)
    check(n_sent == 6, f"contract lists 6 sentinel columns (found {n_sent})", "configs/data_contract.yaml")
    numeric = {k: v for k, v in cols.items() if v.get("type") in ("int", "float")}
    unbounded = [k for k, v in numeric.items() if not ({"min", "max"} <= set(v) or "allowed" in v)]
    check(
        not unbounded,
        f"every numeric column has a range or allowed values ({len(numeric)} columns)",
        f"add min/max for: {', '.join(unbounded)}",
    )
    raw_yaml = read("configs/data_contract.yaml")
    has_source_note = "Ranges:" in raw_yaml or "datasheet" in raw_yaml
    check(has_source_note, "contract explains where the ranges come from", "add a comment on the source of ranges")
    bad_sentinel = [k for k, rule in sentinels.items() if cols.get(k, {}).get("min", -1) > -1 and rule == "eq_-1"]
    check(not bad_sentinel, "sentinel columns allow -1 in their range", f"set min: -1 for {', '.join(bad_sentinel)}")
    quality = ROOT / "reports" / "quality" / "base.csv"
    n_months = max(len(quality.read_text().splitlines()) - 1, 0) if quality.exists() else 0
    check(n_months == 8, f"quality report for 8 months (found {n_months})", "make quality")
    sql = sorted((ROOT / "sql" / "analysis").glob("q0[1-7]_*.sql"))
    with_select = [p for p in sql if "SELECT" in p.read_text().upper()]
    check(len(with_select) == 7, f"7 analysis queries written (found {len(with_select)})", "sql/analysis/q01-q07")
    csvs = list((ROOT / "reports" / "eda").glob("q0[1-7]_*.csv"))
    check(len(csvs) == 7, f"7 query results saved in reports/eda (found {len(csvs)})", "make eda-load && make eda-sql")
    findings = read("docs/03_EDA_FINDINGS.md")
    n_f = len(re.findall(r"^### F\d+", findings, flags=re.M))
    complete = all(k in findings for k in ("**Evidence", "**So what:**", "**Action:**"))
    check(
        5 <= n_f <= 8 and complete and not PLACEHOLDER.search(findings),
        f"5-8 findings with evidence, so-what and action (found {n_f})",
        "docs/03_EDA_FINDINGS.md",
    )
    check(phase_done("p2"), "p2 in tests/PHASES_DONE", "make phase-done P=2")


def gold_counts() -> dict[str, object]:
    """Fact rows and month completeness from Postgres; empty dict when the database is unreachable."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        import psycopg

        from sigap import config

        dsn = config.database_url().replace("postgresql+psycopg://", "postgresql://", 1)
        with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM gold.fact_application")
            fact = cur.fetchone()[0]
            cur.execute("SELECT month_index FROM gold.dim_month WHERE NOT label_complete ORDER BY 1")
            open_months = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT count(*) FROM gold.fact_application f JOIN gold.dim_month m USING (month_key) "
                "WHERE NOT m.label_complete AND f.is_fraud IS NOT NULL"
            )
            leaked = cur.fetchone()[0]
        return {"fact": fact, "open_months": open_months, "leaked": leaked}
    except Exception as exc:  # noqa: BLE001 - report, do not crash the review
        return {"error": str(exc).splitlines()[0]}


def review_p3() -> None:
    check(tests_pass("p3"), "make check P=3 green (needs Java 17)", "make check P=3")
    bronze = ROOT / "data" / "bronze" / "base"
    n_bronze = len(list((bronze / "applications").glob("month=*")))
    check(n_bronze == 8, f"bronze applications partitioned by month (found {n_bronze})", "make bronze")
    silver = ROOT / "data" / "silver" / "base" / "applications"
    n_silver = len(list(silver.glob("month=*")))
    check(n_silver == 8, f"silver applications partitioned by month (found {n_silver})", "make silver")
    silver_rows = 0
    if n_silver:
        import pyarrow.parquet as pq

        silver_rows = pq.ParquetDataset(str(silver)).read(columns=["application_id"]).num_rows
    ddl = read("sql/warehouse/001_schemas.sql")
    tables = ("gold.dim_month", "gold.fact_application", "ops.decision_log", "ops.monitoring_monthly")
    check(
        all(f"CREATE TABLE IF NOT EXISTS {t}" in ddl for t in tables) and "TODO" not in ddl,
        "warehouse DDL written (gold star schema + ops tables)",
        "sql/warehouse/001_schemas.sql",
    )
    g = gold_counts()
    if "error" in g:
        check(False, "gold reachable in Postgres", f"make db-up, then make gold ({g['error']})")
    else:
        check(
            g["fact"] == silver_rows and silver_rows > 0,
            f"fact rows = silver rows ({g['fact']:,} vs {silver_rows:,})",
            "make gold",
        )
        check(
            g["open_months"] == [6, 7],
            f"months without complete labels: {g['open_months']} (expect [6, 7])",
            "make gold",
        )
        check(g["leaked"] == 0, "no label in months whose labels have not arrived", "check labels_as_of in gold.py")
    erd = read("docs/01_ERD.md")
    check("Draft" not in erd and "label_complete" in erd, "ERD final (matches the DDL)", "docs/01_ERD.md")
    adr = read("docs/adr/0001-spark-local-postgres-warehouse.md")
    check(
        "## Decision" in adr and not PLACEHOLDER.search(adr),
        "ADR 0001 written (Spark local + Postgres)",
        "docs/adr/0001-spark-local-postgres-warehouse.md",
    )
    check(phase_done("p3"), "p3 in tests/PHASES_DONE", "make phase-done P=3")


def review_p4() -> None:
    check(tests_pass("p4"), "make check P=4 green", "make check P=4")
    rules = (yaml.safe_load(read("configs/rules.yaml") or "{}") or {}).get("rules", [])
    check(
        5 <= len(rules) <= 8 and all(r.get("rationale") for r in rules) and "TODO" not in read("configs/rules.yaml"),
        f"5-8 rules with a rationale in configs/rules.yaml (found {len(rules)})",
        "configs/rules.yaml",
    )
    reports = [ROOT / "reports" / "rules" / f"base_{p}.csv" for p in ("train", "valid")]
    ok = all(p.exists() and "any_rule" in p.read_text() for p in reports)
    check(ok, "rule reports for train (0-4) and valid (5)", "make rules")
    log = read("docs/04_DECISION_POLICY.md").split("## Cost assumptions")[0]
    n_log = len(re.findall(r"^\| 20\d\d-", log, flags=re.M))
    check(n_log >= 1, f"rule tuning log in 04_DECISION_POLICY.md ({n_log} entries)", "add a row per rules.yaml change")
    gold = ROOT / "data" / "gold" / "base"
    feats, labels = gold / "features.parquet", gold / "labels.parquet"
    if not (feats.exists() and labels.exists()):
        check(False, "features.parquet and labels.parquet written", "make features")
    else:
        import pyarrow.parquet as pq

        cols = pq.read_schema(feats).names
        check(
            not {"is_fraud", "fraud_bool"} & set(cols),
            f"features.parquet has no label column ({len(cols)} columns)",
            "the label belongs in labels.parquet",
        )
        silver = ROOT / "data" / "silver" / "base" / "applications"
        n_silver = pq.ParquetDataset(str(silver)).read(columns=["application_id"]).num_rows if silver.exists() else -1
        t = pq.read_table(feats, columns=["month", "prior_rate_device_os"]).to_pandas()
        check(
            len(t) == n_silver, f"one feature row per application ({len(t):,} vs silver {n_silver:,})", "make features"
        )
        nan_months = sorted(t.loc[t["prior_rate_device_os"].isna(), "month"].unique().tolist())
        check(
            nan_months == [0, 1],
            f"prior rates empty only before labels arrive (months {nan_months})",
            "check prior_rate: month <= t - lag",
        )
    check(phase_done("p4"), "p4 in tests/PHASES_DONE", "make phase-done P=4")


def review_p5() -> None:
    check(tests_pass("p5"), "make check P=5 green", "make check P=5")
    check((ROOT / "mlflow.db").exists(), "MLflow runs recorded (mlflow.db)", "make train")
    mpath = ROOT / "reports" / "model" / "base_metrics.json"
    m = json.loads(mpath.read_text()) if mpath.exists() else {}
    cands = ROOT / "reports" / "model" / "base_candidates.csv"
    n_c = max(len(cands.read_text().splitlines()) - 1, 0) if cands.exists() else 0
    check(n_c >= 5, f"baseline and candidates compared on month 5 ({n_c} candidates)", "make train")
    check(
        bool(m.get("gate_passed")),
        "release gate passed"
        + ("" if m.get("gate_passed") or not m else f" (failed: {'; '.join(m.get('gate_reasons', []))})"),
        "read the gate reasons; never lower a limit after test",
    )
    meta_path = ROOT / "models" / "current" / "metadata.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    check(
        bool(meta) and meta.get("version") == m.get("version"),
        "models/current holds the gate-passed model",
        "make train (only a passing model is copied there)",
    )
    for adr in ("0002-temporal-split-label-lag-threshold.md", "0005-fairness-age-predictive-equality.md"):
        text = read(f"docs/adr/{adr}")
        check("## Decision" in text and not PLACEHOLDER.search(text), f"ADR {adr[:4]} written", f"docs/adr/{adr}")
    check(doc_filled("docs/MODEL_CARD.md", 600), "model card filled with run results", "docs/MODEL_CARD.md")
    check(phase_done("p5"), "p5 in tests/PHASES_DONE", "make phase-done P=5")


def review_p6() -> None:
    check(tests_pass("p6"), "make check P=6 green", "make check P=6")
    biz = yaml.safe_load(read("configs/business.yaml") or "{}") or {}
    costs = biz.get("costs") or {}
    filled = biz.get("max_review_rate") is not None and costs and all(v is not None for v in costs.values())
    check(bool(filled), "business assumptions filled (configs/business.yaml)", "fill every null with a reasoned value")
    pol = ROOT / "reports" / "policy"
    files = [pol / "champion_challenger_base.csv", pol / "sensitivity_base.csv", pol / "base_policy.json"]
    check(all(f.exists() for f in files), "champion/challenger replay and sensitivity saved", "make policy")
    check((ROOT / "models" / "current" / "policy.json").exists(), "bands stored next to the model", "make policy")
    text = read("docs/04_DECISION_POLICY.md")
    sections = ("## Chosen policy", "## Champion (rules) vs challenger", "## Sensitivity")
    empty = [s for s in sections if s in text and not re.search(re.escape(s) + r".*?\n\|[^\n]*\d", text, re.S)]
    check(
        not empty and not PLACEHOLDER.search(text),
        "decision policy tables filled with replay results",
        "docs/04_DECISION_POLICY.md",
    )
    adr = read("docs/adr/0006-decision-bands-cost-capacity.md")
    check("## Decision" in adr and not PLACEHOLDER.search(adr), "ADR 0006 written", "docs/adr/0006-...md")
    check(doc_filled("docs/05_BUSINESS_MEMO.md", 800), "business memo written", "docs/05_BUSINESS_MEMO.md")
    check(phase_done("p6"), "p6 in tests/PHASES_DONE", "make phase-done P=6")


def review_p7() -> None:
    check(tests_pass("p7"), "make check P=7 green", "make check P=7")
    cur = ROOT / "models" / "current"
    check((cur / "prior_rates.json").exists(), "serving lookup next to the model (prior_rates.json)", "make serve-prep")
    df = read("Dockerfile")
    ok = all(k in df for k in ("USER ", "HEALTHCHECK", "libgomp1", "requirements-serve.txt")) and "COPY data" not in df
    check(ok, "Dockerfile: non-root user, healthcheck, OpenMP, serve-only requirements", "Dockerfile")
    try:
        image = subprocess.run(["docker", "image", "inspect", "sigap-api:local"], capture_output=True)  # noqa: S607
        built = image.returncode == 0
    except FileNotFoundError:
        built = False
    check(built, "Docker image sigap-api:local built", "make docker-build")
    lat_path = ROOT / "reports" / "serve" / "latency.json"
    lat = json.loads(lat_path.read_text()) if lat_path.exists() else {}
    p95 = lat.get("round_trip_ms", {}).get("p95")
    check(
        bool(lat) and lat.get("errors") == 0 and p95 is not None and p95 < 100,
        f"load test: 0 errors and p95 < 100 ms (p95 {p95} ms)",
        "make serve (or make docker-run), then make load-test in a second terminal",
    )
    sys.path.insert(0, str(ROOT / "src"))
    err = ""
    try:
        import psycopg

        from sigap import config

        dsn = config.database_url().replace("postgresql+psycopg://", "postgresql://", 1)
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            n_log = conn.execute("SELECT count(*) FROM ops.decision_log").fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        n_log, err = 0, str(exc).splitlines()[0]
    check(n_log > 0, f"decisions logged in ops.decision_log ({n_log:,} rows)", err or "make load-test with the API on")
    runbook = read("docs/RUNBOOK.md")
    api = runbook.split("## Scoring API")[1].split("\n## ")[0] if "## Scoring API" in runbook else ""
    check(
        bool(re.search(r"p95[^\n]*\d", api)) and not PLACEHOLDER.search(api),
        "RUNBOOK: API section with measured latency",
        "docs/RUNBOOK.md",
    )
    check(phase_done("p7"), "p7 in tests/PHASES_DONE", "make phase-done P=7")


REVIEWS = {
    "0": review_p0,
    "1": review_p1,
    "2": review_p2,
    "3": review_p3,
    "4": review_p4,
    "5": review_p5,
    "6": review_p6,
    "7": review_p7,
}


def main(phase: str) -> int:
    phase = phase.lstrip("p")
    if phase not in REVIEWS:
        print(f"No review defined yet for phase {phase}. Defined: {', '.join(sorted(REVIEWS))}")
        return 0
    REVIEWS[phase]()
    print(f"\nSIGAP review · phase {phase}\n")
    for ok, what, fix in RESULTS:
        print(f"  {'OK     ' if ok else 'MISSING'}  {what}")
        if not ok and fix:
            print(f"           -> {fix}")
    missing = sum(not ok for ok, _, _ in RESULTS)
    print("\n" + ("Phase complete." if not missing else f"{missing} item(s) left."))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "0"))
