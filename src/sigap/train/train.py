"""Training job: baseline -> gradient boosting -> calibration -> threshold -> fairness -> gate -> MLflow.

Protocol (ADR 0002): temporal split, never random. Train on months 0-4, choose and calibrate on month 5, then
measure once on months 6-7. Labels of months 6-7 arrive at months 8-9; the test is a backtest of that future.

Candidates (each one an MLflow run, compared on month 5 only):
  logreg_balanced     scaled logistic regression with class weights: the simple baseline
  xgb                 gradient-boosted trees, all features, no class weighting
  xgb_weighted        the same with scale_pos_weight = negatives / positives
  xgb_no_protected    the better of the two, without customer_age, income, employment_status
  xgb_reweighed_<w>   xgb_no_protected with genuine applicants aged 50+ weighted w times in training
                      (reweighing, Kamiran & Calders 2012): age is used to set training weights, never as a feature

Selection (ADR 0005): the tree candidate with the highest month-5 recall at 5% FPR among those whose month-5
FPR ratio between age groups is at least the gate floor plus a margin (test months drift); if none qualifies,
the candidate with the best ratio, and the gate reports the failure.
The chosen model is calibrated on month 5 (Platt/sigmoid: monotone, so the ranking and the threshold stay
exact), the threshold is set at 5% FPR on month 5 and applied unchanged to months 6-7.

Outputs: MLflow runs (sqlite:///mlflow.db), reports/model/<variant>_*.csv/json, and models/current/ only when the
release gate passes (otherwise models/rejected/<version>/ with the reasons).

Run:  make train   then   make mlflow  (http://127.0.0.1:5050)
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from sigap import config
from sigap.explain.reasons import PROTECTED, analyst_reasons
from sigap.monitor.psi import psi
from sigap.train.fairness import age_group, fpr_by_group, fpr_ratio
from sigap.train.gate import evaluate_gate
from sigap.train.metrics import confusion_at, expected_calibration_error, threshold_at_fpr
from sigap.train.model import SigapModel

TARGET_FPR = 0.05
SEED = 42
REWEIGH_FACTORS = (2.0, 4.0)
SKOPS_TRUSTED = [
    "sklearn.calibration._CalibratedClassifier",
    "sklearn.calibration._SigmoidCalibration",
    "sklearn.frozen._frozen.FrozenEstimator",
    "xgboost.core.Booster",
    "xgboost.sklearn.XGBClassifier",
]
FAIRNESS_MARGIN = 0.10  # selection asks month 5 for floor + margin, so a small drift in months 6-7 still passes
XGB_PARAMS = {
    "n_estimators": 2000,
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "tree_method": "hist",
    "eval_metric": "aucpr",
    "early_stopping_rounds": 100,
    "random_state": SEED,
    "n_jobs": -1,
}


# ---------------------------------------------------------------- data
def load_matrix(slug: str) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    """Features (float32), label, month and customer_age, aligned by application_id."""
    gold = config.GOLD / slug
    feats = pd.read_parquet(gold / "features.parquet")
    labels = pd.read_parquet(gold / "labels.parquet", columns=[config.ID, config.LABEL])
    df = feats.merge(labels, on=config.ID, how="left", validate="one_to_one")
    if df[config.LABEL].isna().any():
        raise SystemExit("labels.parquet does not cover every application: run `make features`")
    X = df.drop(columns=[config.ID, config.MONTH, config.LABEL]).astype("float32")
    return X, df[config.LABEL].to_numpy(int), df[config.MONTH].to_numpy(int), df["customer_age"].to_numpy()


def without_protected(columns: list[str]) -> list[str]:
    return [c for c in columns if not c.startswith(PROTECTED)]


# ---------------------------------------------------------------- models
def fit_logreg(X: pd.DataFrame, y: np.ndarray):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=2000),
    )
    return model.fit(X, y)


def fit_xgb(
    X: pd.DataFrame,
    y: np.ndarray,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    scale_pos_weight: float = 1.0,
    sample_weight: np.ndarray | None = None,
):
    """Early stopping on month 5 (PR-AUC): the number of trees is chosen on data the model did not train on."""
    import xgboost as xgb

    model = xgb.XGBClassifier(**XGB_PARAMS, scale_pos_weight=scale_pos_weight)
    return model.fit(X, y, sample_weight=sample_weight, eval_set=[(X_val, y_val)], verbose=False)


def reweigh(y: np.ndarray, age: np.ndarray, factor: float) -> np.ndarray:
    """Training weights: genuine applicants aged 50+ count `factor` times, everyone else 1."""
    return np.where((y == 0) & (np.asarray(age) >= 50), factor, 1.0)


def calibrate(model, X_val: pd.DataFrame, y_val: np.ndarray):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator

    return CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid").fit(X_val, y_val)


# ---------------------------------------------------------------- evaluation
def evaluate(y: np.ndarray, p: np.ndarray, threshold: float, age: np.ndarray, prefix: str) -> dict[str, float]:
    """Everything the gate, the model card and the memo need, for one period."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    c = confusion_at(y, p, threshold)
    fprs = fpr_by_group(y, p, threshold, age_group(age))
    out = {
        "tpr_at_5fpr": c["tpr"],
        "fpr": c["fpr"],
        "precision": c["precision"],
        "alert_rate": c["alert_rate"],
        "pr_auc": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "ece": expected_calibration_error(y, p),
        "fpr_lt50": fprs.get("<50", float("nan")),
        "fpr_ge50": fprs.get(">=50", float("nan")),
        "fpr_ratio_age": fpr_ratio(fprs),
    }
    return {f"{prefix}_{k}": v for k, v in out.items()}


def recall_at_alert_rate(y: np.ndarray, p: np.ndarray, alert_rate: float) -> float:
    """Recall when the model flags the same share of applications as another policy (e.g. the rules)."""
    if alert_rate <= 0:
        return 0.0
    cut = np.quantile(p, 1 - alert_rate)
    return float((p[y == 1] >= cut).mean())


def rules_valid_alert_rate(slug: str) -> tuple[float, float] | None:
    path = config.REPORTS / "rules" / f"{slug}_valid.csv"
    if not path.exists():
        return None
    row = pd.read_csv(path).set_index("rule").loc["any_rule"]
    return float(row["alert_rate"]), float(row["recall"])


def file_sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


# ---------------------------------------------------------------- job
def main() -> None:
    import mlflow

    slug = config.VARIANT.lower().replace(" ", "_")
    gate = config.load_yaml("gate")
    fairness_floor = float(gate.get("min", {}).get("test_fpr_ratio_age", 0.0))
    X, y, month, age = load_matrix(slug)
    tr, va, te = (np.isin(month, ms) for ms in (config.TRAIN_MONTHS, config.VALID_MONTHS, config.TEST_MONTHS))
    all_cols = list(X.columns)
    print(f"train {tr.sum():,} | valid {va.sum():,} | test {te.sum():,} applications; {len(all_cols)} features")
    print(f"fraud rate train {y[tr].mean():.2%} | valid {y[va].mean():.2%} | test {y[te].mean():.2%}")

    mlflow.set_tracking_uri(f"sqlite:///{config.ROOT / 'mlflow.db'}")
    exp_name = f"sigap-{slug}"
    if mlflow.get_experiment_by_name(exp_name) is None:
        mlflow.create_experiment(exp_name, artifact_location=(config.ROOT / "mlruns").as_uri())
    mlflow.set_experiment(exp_name)
    spw = float((y[tr] == 0).sum() / max((y[tr] == 1).sum(), 1))
    rules = rules_valid_alert_rate(slug)

    candidates: dict[str, dict] = {}

    def run_candidate(name: str, cols: list[str], fit) -> None:
        t0 = time.time()
        with mlflow.start_run(run_name=name, nested=True):
            model = fit(cols)
            p_va = model.predict_proba(X.loc[va, cols])[:, 1]
            thr = threshold_at_fpr(y[va], p_va, TARGET_FPR)
            m = evaluate(y[va], p_va, thr, age[va], "valid")
            if rules:
                m["valid_recall_at_rules_alert_rate"] = recall_at_alert_rate(y[va], p_va, rules[0])
            m["fit_seconds"] = round(time.time() - t0, 1)
            params = {"features": len(cols), "protected_used": len(cols) == len(all_cols)}
            if hasattr(model, "best_iteration"):
                params.update({k: v for k, v in XGB_PARAMS.items() if k != "n_jobs"})
                params["best_iteration"] = model.best_iteration
                params["scale_pos_weight"] = model.get_params()["scale_pos_weight"]
            mlflow.log_params(params)
            mlflow.log_metrics(m)
        candidates[name] = {"model": model, "cols": cols, **m}
        print(
            f"  {name:19s} valid recall@5%FPR {m['valid_tpr_at_5fpr']:.3f}  PR-AUC {m['valid_pr_auc']:.3f}  "
            f"FPR ratio age {m['valid_fpr_ratio_age']:.2f}  ({m['fit_seconds']:.0f}s)"
        )

    started = datetime.now(UTC)
    with mlflow.start_run(run_name=f"train-{started:%Y%m%d-%H%M}") as parent:
        print("\ncandidates (month 5):")
        run_candidate("logreg_balanced", all_cols, lambda c: fit_logreg(X.loc[tr, c], y[tr]))
        run_candidate("xgb", all_cols, lambda c: fit_xgb(X.loc[tr, c], y[tr], X.loc[va, c], y[va]))
        run_candidate("xgb_weighted", all_cols, lambda c: fit_xgb(X.loc[tr, c], y[tr], X.loc[va, c], y[va], spw))
        best_w = (
            spw if candidates["xgb_weighted"]["valid_tpr_at_5fpr"] > candidates["xgb"]["valid_tpr_at_5fpr"] else 1.0
        )
        cols_np = without_protected(all_cols)
        run_candidate("xgb_no_protected", cols_np, lambda c: fit_xgb(X.loc[tr, c], y[tr], X.loc[va, c], y[va], best_w))
        for f in REWEIGH_FACTORS:
            w = reweigh(y[tr], age[tr], f)
            run_candidate(
                f"xgb_reweighed_{f:g}",
                cols_np,
                lambda c, w=w: fit_xgb(X.loc[tr, c], y[tr], X.loc[va, c], y[va], best_w, sample_weight=w),
            )

        trees = {k: v for k, v in candidates.items() if k.startswith("xgb")}
        fair = {k: v for k, v in trees.items() if v["valid_fpr_ratio_age"] >= fairness_floor + FAIRNESS_MARGIN}
        pool = fair or {max(trees, key=lambda k: trees[k]["valid_fpr_ratio_age"]): None}
        chosen = max(pool, key=lambda k: trees[k]["valid_tpr_at_5fpr"])
        model, cols = candidates[chosen]["model"], candidates[chosen]["cols"]
        print(f"\nchosen: {chosen} (month 5 needs FPR ratio >= {fairness_floor + FAIRNESS_MARGIN:.2f})")

        calibrated = calibrate(model, X.loc[va, cols], y[va])
        p = {k: calibrated.predict_proba(X.loc[mask, cols])[:, 1] for k, mask in (("tr", tr), ("va", va), ("te", te))}
        threshold = threshold_at_fpr(y[va], p["va"], TARGET_FPR)
        metrics = {
            **evaluate(y[va], p["va"], threshold, age[va], "valid"),
            **evaluate(y[te], p["te"], threshold, age[te], "test"),
            "score_psi_test_vs_train": psi(p["tr"], p["te"]),
            "threshold": threshold,
        }
        if rules:
            metrics["test_recall_at_rules_alert_rate"] = recall_at_alert_rate(y[te], p["te"], rules[0])
        passed, reasons = evaluate_gate(metrics, gate)

        version = f"{slug}-{started:%Y%m%d-%H%M}-{parent.info.run_id[:6]}"
        sigap_model = SigapModel(
            estimator=calibrated,
            booster=model,
            features=cols,
            threshold=threshold,
            version=version,
            metadata={
                "candidate": chosen,
                "trained_at": started.isoformat(),
                "gate_passed": passed,
                "gate_reasons": reasons,
                "data_manifest_sha256": file_sha256(config.DATA / "raw" / "MANIFEST.json"),
                "metrics": metrics,
            },
        )

        # SHAP: global importance on a test sample, and reason codes for the highest-scored test applications
        sample = X.loc[te, cols].sample(n=min(20_000, int(te.sum())), random_state=SEED)
        contrib = sigap_model.contributions(sample)
        importance = contrib.abs().mean().sort_values(ascending=False).rename("mean_abs_shap")
        top_idx = sample.index[np.argsort(-sigap_model.score(sample))[:3]]
        examples = [analyst_reasons(contrib.loc[i].to_dict()) for i in top_idx]

        out = config.REPORTS / "model"
        out.mkdir(parents=True, exist_ok=True)
        cand_table = pd.DataFrame(
            [
                {"candidate": k, **{m: v for m, v in c.items() if m not in ("model", "cols")}}
                for k, c in candidates.items()
            ]
        )
        cand_table.to_csv(out / f"{slug}_candidates.csv", index=False)
        importance.to_csv(out / f"{slug}_shap_importance.csv")
        (out / f"{slug}_metrics.json").write_text(
            json.dumps(
                {"version": version, "candidate": chosen, "gate_passed": passed, "gate_reasons": reasons, **metrics},
                indent=2,
            ),
            encoding="utf-8",
        )

        mlflow.log_params(
            {
                "chosen": chosen,
                "features": len(cols),
                "target_fpr": TARGET_FPR,
                "calibration": "sigmoid",
                "fairness_floor": fairness_floor,
                "data_manifest_sha256": sigap_model.metadata["data_manifest_sha256"],
            }
        )
        mlflow.log_metrics({k: v for k, v in metrics.items() if np.isfinite(v)})
        mlflow.log_metric("gate_passed", int(passed))
        mlflow.set_tag("gate_reasons", "; ".join(reasons) or "none")
        mlflow.log_dict({"features": cols}, "features.json")
        mlflow.log_artifact(str(out / f"{slug}_shap_importance.csv"))
        mlflow.log_artifact(str(out / f"{slug}_candidates.csv"))
        import mlflow.sklearn

        info = mlflow.sklearn.log_model(
            calibrated,
            name="model",
            registered_model_name=f"sigap-{slug}",
            skops_trusted_types=SKOPS_TRUSTED,  # skops refuses unknown classes on load unless listed here
        )
        if passed:
            from mlflow import MlflowClient

            MlflowClient().set_registered_model_alias(f"sigap-{slug}", "champion", info.registered_model_version)
            folder = config.MODELS / "current"
        else:
            folder = config.MODELS / "rejected" / version
        sigap_model.save(folder)

    print(f"\nthreshold (calibrated score, 5% FPR on month 5): {threshold:.4f}")
    rows = [
        ("recall at threshold", "tpr_at_5fpr"),
        ("FPR", "fpr"),
        ("precision", "precision"),
        ("alert rate", "alert_rate"),
        ("PR-AUC", "pr_auc"),
        ("ROC-AUC", "roc_auc"),
        ("ECE", "ece"),
        ("FPR age <50", "fpr_lt50"),
        ("FPR age >=50", "fpr_ge50"),
        ("FPR ratio age", "fpr_ratio_age"),
    ]
    print(f"\n{'':22s}{'valid (5)':>12s}{'test (6-7)':>12s}")
    for label, key in rows:
        print(f"{label:22s}{metrics['valid_' + key]:12.4f}{metrics['test_' + key]:12.4f}")
    print(f"{'score PSI test/train':22s}{'':12s}{metrics['score_psi_test_vs_train']:12.4f}")
    if rules:
        print(f"\nrules (month 5): alert rate {rules[0]:.2%}, recall {rules[1]:.1%}")
        print(
            f"model at the same alert rate: recall {candidates[chosen]['valid_recall_at_rules_alert_rate']:.1%} "
            f"(month 5), {metrics['test_recall_at_rules_alert_rate']:.1%} (months 6-7)"
        )
    print("\ntop SHAP features (test sample):")
    print(importance.head(10).round(4).to_string())
    print("\nreason codes, 3 highest-scored test applications:")
    for r in examples:
        print("  - " + "; ".join(r))
    print(f"\nrelease gate: {'PASSED' if passed else 'FAILED'}" + ("" if passed else " -> " + "; ".join(reasons)))
    print(f"model {version} -> {folder}")


if __name__ == "__main__":
    main()
