"""Production replay: SIGAP runs as if it went live at month 5, one month at a time (5, then 6, then 7).

Each month t:
  1. Score the month's applications with models/current, through the API's own code (serving_frame) and the
     decision bands of the policy. The prior-rate lookup is rebuilt as of month t (labels up to t - 2), so the
     replay never uses a label that would not have existed yet.
  2. Write the decisions to ops.decision_log (idempotent: a month's earlier replay rows are replaced).
  3. Write the month's volumes and decision rates to ops.monitoring_monthly.
  4. Drift: PSI of the score and of the model's ten most important features, month t vs training months 0-4.
  5. Late labels: labels that became available at month t belong to month t - 2. Only months that were scored
     live (>= 5) are evaluated, so within months 5-7 performance exists for month 5 only, measured at month 7.
  6. Retraining rule (docs/RUNBOOK.md): score PSI >= 0.25, or recall at the threshold more than 10 points below
     validation, or FPR ratio by age below the gate limit -> retraining ticket.

Run:  make replay          (months 5, 6, 7)       make replay M=6   (one month, e.g. from Airflow)
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from sigap import config
from sigap.monitor.psi import drift_report, psi

PSI_ALERT = 0.25
RECALL_DROP = 0.10
TOP_FEATURES = 10


def load_month_raw(slug: str, month: int) -> pd.DataFrame:
    path = config.DATA / "landing_valid" / slug / f"month={month:02d}" / "part.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found: run `make quality` first")
    return pd.read_csv(path)


def top_features(model, slug: str, k: int = TOP_FEATURES) -> list[str]:
    """The model's k most important input features by mean |SHAP| (training report), else its first k features.

    prior_rate_* columns are left out: they are fraud rates looked up from a table that changes every month by
    design, so their PSI measures label movement, not input drift (the category mix is watched through the
    one-hot columns instead).
    """
    path = config.REPORTS / "model" / f"{slug}_shap_importance.csv"
    ranked = pd.read_csv(path, index_col=0).index.tolist() if path.exists() else model.features
    return [f for f in ranked if f in model.features and not f.startswith("prior_rate_")][:k]


def reference_frame(slug: str, model) -> tuple[pd.DataFrame, np.ndarray]:
    """Training months 0-4: the features as built point in time, and the calibrated scores."""
    feats = pd.read_parquet(config.GOLD / slug / "features.parquet")
    ref = feats[feats[config.MONTH].isin(config.TRAIN_MONTHS)].reset_index(drop=True)
    return ref, model.score(ref)


def score_month(raw: pd.DataFrame, state: dict, priors: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Decisions for one month of raw applications, with reason codes for review/decline only."""
    from sigap.explain.reasons import analyst_reasons
    from sigap.features.build import serving_frame
    from sigap.policy.cost import decide

    X = serving_frame(raw, state["numeric"], state["categories"], priors["tables"], state["sentinels"])
    model = state["model"]
    p = model.score(X)
    decision = decide(p, state["t_review"], state["t_decline"])
    out = pd.DataFrame({config.ID: raw[config.ID].to_numpy(), "score": p, "decision": decision})
    flagged = np.flatnonzero(decision != "approve")
    reasons = [[] for _ in range(len(out))]
    if len(flagged):
        contrib = model.contributions(X.iloc[flagged])
        for pos, (_, row) in zip(flagged, contrib.iterrows(), strict=True):
            reasons[pos] = analyst_reasons(row.to_dict())
    out["reasons"] = reasons
    return out, X


def write_decisions(conn, decisions: pd.DataFrame, version: str) -> None:
    ids = decisions[config.ID].tolist()
    conn.execute("DELETE FROM ops.decision_log WHERE model_version = %s AND application_id = ANY(%s)", (version, ids))
    with (
        conn.cursor() as cur,
        cur.copy("COPY ops.decision_log (application_id, model_version, score, decision, reasons) FROM STDIN") as cp,
    ):
        for app_id, score, decision, reasons in decisions[[config.ID, "score", "decision", "reasons"]].itertuples(
            index=False
        ):
            cp.write_row((app_id, version, float(score), decision, reasons))


def write_metrics(conn, month: int, rows: list[tuple[str, str, float]]) -> None:
    for metric, feature, value in rows:
        conn.execute(
            "INSERT INTO ops.monitoring_monthly (month, metric, feature, value) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (month, metric, feature) DO UPDATE SET value = EXCLUDED.value, computed_at = now()",
            (month, metric, feature, float(value)),
        )


def logged_decisions(conn, slug: str, month: int, version: str) -> pd.DataFrame:
    """Decisions the replay logged for a month (so a single-month run, e.g. from Airflow, can evaluate it)."""
    raw = load_month_raw(slug, month)[[config.ID, "customer_age"]]
    rows = conn.execute(
        "SELECT application_id, score, decision FROM ops.decision_log WHERE model_version = %s "
        "AND application_id = ANY(%s)",
        (version, raw[config.ID].tolist()),
    ).fetchall()
    logged = pd.DataFrame(rows, columns=[config.ID, "score", "decision"])
    return raw.merge(logged, on=config.ID, how="inner")


def performance(decisions: pd.DataFrame, labels: pd.DataFrame, threshold: float) -> dict | None:
    """Recall, FPR, precision and the age FPR ratio of a live month once its labels have arrived."""
    from sigap.train.fairness import age_group, fpr_by_group, fpr_ratio
    from sigap.train.metrics import confusion_at

    d = decisions.merge(labels[[config.ID, config.LABEL]], on=config.ID, how="inner")
    if d.empty:
        return None
    y, p = d[config.LABEL].to_numpy(), d["score"].to_numpy(dtype=float)
    c = confusion_at(y, p, threshold)
    held = d["decision"].to_numpy() != "approve"
    return {
        "tpr": c["tpr"],
        "fpr": c["fpr"],
        "precision": c["precision"],
        "fpr_ratio_age": fpr_ratio(fpr_by_group(y, p, threshold, age_group(d["customer_age"].to_numpy()))),
        "fraud_rate": float(y.mean()),
        "policy_fraud_held": float(held[y == 1].mean()) if (y == 1).any() else 0.0,
    }


def arrivals(conn, slug: str, t: int, version: str, threshold: float) -> dict | None:
    """Performance of month t - lag, from the labels that became available at month t."""
    path = config.LANDING / slug / "labels" / f"available_month={t:02d}" / "part.csv"
    if not path.exists():
        return None
    return performance(logged_decisions(conn, slug, t - config.LABEL_LAG_MONTHS, version), pd.read_csv(path), threshold)


def performance_reasons(perf: dict | None, valid_tpr: float, ratio_floor: float) -> list[str]:
    if not perf:
        return []
    reasons = []
    if perf["tpr"] < valid_tpr - RECALL_DROP:
        reasons.append(f"recall {perf['tpr']:.3f} < validation {valid_tpr:.3f} - {RECALL_DROP}")
    if perf["fpr_ratio_age"] < ratio_floor:
        reasons.append(f"age FPR ratio {perf['fpr_ratio_age']:.2f} < {ratio_floor}")
    return reasons


def main(months: tuple[int, ...] | None = None) -> None:
    import psycopg

    from sigap.serve.app import load_serving_state
    from sigap.serve.prepare import build_prior_tables

    slug = config.VARIANT.lower().replace(" ", "_")
    months = months or (*config.VALID_MONTHS, *config.TEST_MONTHS)
    state = load_serving_state(config.MODELS / "current")
    model = state["model"]
    version = model.version
    meta_metrics = model.metadata.get("metrics", {})
    valid_tpr = float(meta_metrics.get("valid_tpr_at_5fpr", np.nan))
    ratio_floor = float(config.load_yaml("gate").get("min", {}).get("test_fpr_ratio_age", 0.5))
    capacity = float(config.load_yaml("business").get("review_capacity_per_day") or np.nan)
    features = top_features(model, slug)
    ref, ref_scores = reference_frame(slug, model)
    first_live = min(config.VALID_MONTHS)  # SIGAP went live at the validation month
    dsn = config.database_url().replace("postgresql+psycopg://", "postgresql://", 1)

    print(
        f"model {version}; drift watched on the score + {len(features)} features; "
        f"retrain if score PSI >= {PSI_ALERT}, recall < validation - {RECALL_DROP:.0%}, age FPR ratio < {ratio_floor}"
    )
    summary = []
    for t in months:
        raw = load_month_raw(slug, t)
        priors = build_prior_tables(slug, as_of=t)
        decisions, X = score_month(raw, state, priors)
        rates = decisions["decision"].value_counts(normalize=True)
        score_psi = psi(ref_scores, decisions["score"].to_numpy())
        drift = drift_report(ref[features], X[features], features, alert=PSI_ALERT)
        reviews_per_day = rates.get("review", 0.0) * float(
            config.load_yaml("business").get("applications_per_day") or 0
        )

        perf_month = t - config.LABEL_LAG_MONTHS

        reasons = []
        if score_psi >= PSI_ALERT:
            reasons.append(f"score PSI {score_psi:.3f} >= {PSI_ALERT}")

        rows = [
            ("applications", "", len(decisions)),
            ("approve_rate", "", rates.get("approve", 0.0)),
            ("review_rate", "", rates.get("review", 0.0)),
            ("decline_rate", "", rates.get("decline", 0.0)),
            ("reviews_per_day", "", reviews_per_day),
            ("psi", "score", score_psi),
            *[("psi", r.feature, r.psi) for r in drift.itertuples()],
        ]
        with psycopg.connect(dsn) as conn:
            write_decisions(conn, decisions, version)
            perf = arrivals(conn, slug, t, version, model.threshold) if perf_month >= first_live else None
            reasons += performance_reasons(perf, valid_tpr, ratio_floor)
            rows.append(("retrain_flag", "", float(bool(reasons))))
            write_metrics(conn, t, rows)
            if perf:
                write_metrics(conn, perf_month, [(k, "", v) for k, v in perf.items()])

        top = drift.head(3)
        print(
            f"\nmonth {t}: {len(decisions):,} applications | approve {rates.get('approve', 0):.2%} | "
            f"review {rates.get('review', 0):.2%} (~{reviews_per_day:.0f}/day vs capacity {capacity:.0f}) | "
            f"decline {rates.get('decline', 0):.2%}"
        )
        print(
            f"  drift: score PSI {score_psi:.3f}; highest features "
            + ", ".join(f"{r.feature} {r.psi:.3f} ({r.status})" for r in top.itertuples())
        )
        if perf:
            print(
                f"  labels of month {perf_month} arrived: recall {perf['tpr']:.3f} (validation {valid_tpr:.3f}), "
                f"FPR {perf['fpr']:.3f}, precision {perf['precision']:.3f}, age FPR ratio {perf['fpr_ratio_age']:.2f}, "
                f"fraud rate {perf['fraud_rate']:.2%}"
            )
        else:
            print(f"  labels arriving now belong to month {perf_month}, which was not scored live: no performance yet")
        print("  retraining ticket: " + ("OPEN -> " + "; ".join(reasons) if reasons else "none"))
        summary.append(
            {
                "month": t,
                "applications": len(decisions),
                **{f"{k}_rate": rates.get(k, 0.0) for k in ("approve", "review", "decline")},
                "score_psi": score_psi,
                "max_feature_psi": float(drift["psi"].max()),
                "retrain": bool(reasons),
                "retrain_reasons": "; ".join(reasons),
                "performance_month": perf_month if perf else None,
                **({f"perf_{k}": v for k, v in perf.items()} if perf else {}),
            }
        )

    # Time goes on after the last drop: labels keep arriving for the months that were scored live.
    last = max(months)
    for t in range(last + 1, last + 1 + config.LABEL_LAG_MONTHS):
        perf_month = t - config.LABEL_LAG_MONTHS
        if perf_month not in months:
            continue
        with psycopg.connect(dsn) as conn:
            perf = arrivals(conn, slug, t, version, model.threshold)
            if perf is None:
                continue
            reasons = performance_reasons(perf, valid_tpr, ratio_floor)
            write_metrics(conn, perf_month, [(k, "", v) for k, v in perf.items()])
            write_metrics(conn, perf_month, [("retrain_flag_on_labels", "", float(bool(reasons)))])
        print(
            f"\nmonth {t} (no new applications, labels only): labels of month {perf_month} arrived: "
            f"recall {perf['tpr']:.3f} (validation {valid_tpr:.3f}), FPR {perf['fpr']:.3f}, "
            f"precision {perf['precision']:.3f}, age FPR ratio {perf['fpr_ratio_age']:.2f}, "
            f"fraud rate {perf['fraud_rate']:.2%}"
        )
        print("  retraining ticket: " + ("OPEN -> " + "; ".join(reasons) if reasons else "none"))
        summary.append(
            {
                "month": t,
                "applications": 0,
                "performance_month": perf_month,
                "retrain": bool(reasons),
                "retrain_reasons": "; ".join(reasons),
                **{f"perf_{k}": v for k, v in perf.items()},
            }
        )

    out = config.REPORTS / "monitor"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary).to_csv(out / f"replay_{slug}.csv", index=False)
    (out / f"replay_{slug}.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"-> ops.decision_log, ops.monitoring_monthly, {out / f'replay_{slug}.csv'}")


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:] if a.strip()]
    main(tuple(args) if args else None)
