"""Phase 5 · Training job: baseline -> gradient boosting -> calibration -> threshold -> gate -> MLflow.

Run:  make train                       (variant from SIGAP_VARIANT, default Base)
      make mlflow                      (UI at http://127.0.0.1:5000)

This file is yours to write. The spec below is the order an interviewer will ask you to walk through.
"""

from __future__ import annotations


def main() -> None:
    """Phase 5 · TODO(Agatha): the training job.

    1. Load gold/features.parquet + gold/labels.parquet. Split by month with config.TRAIN/VALID/TEST_MONTHS.
       Training rows: only labels that are available (they all are in the historical months; say so in the model card).
    2. Baseline: LogisticRegression (scaled, class_weight="balanced"). Log its metrics too: the model must beat it
       AND the rule baseline from phase 4.
    3. Main model: XGBoost (or LightGBM) with early stopping on VALID. Try scale_pos_weight vs none and keep the
       comparison in MLflow (it is a classic interview question).
    4. Calibrate on VALID (isotonic or sigmoid, sklearn CalibratedClassifierCV with a prefit/frozen model).
    5. threshold = threshold_at_fpr(valid_y, valid_p, 0.05). Apply unchanged to TEST.
    6. Metrics on valid and test: confusion_at, tpr at 5% FPR, PR-AUC, ROC-AUC, ECE, fpr_by_group(age>=50), fpr_ratio.
    7. evaluate_gate(metrics, configs/gate.yaml). Log params, metrics, gate result, feature list, data manifest hash.
    8. Register the model in MLflow (sqlite backend). If the gate passes, set alias "champion"; save a copy to
       models/current/ (model + threshold + feature list + version) for the API and Docker image.
    9. SHAP: save global importance to reports/ and make sure explain.reasons.top_reasons works on one row.
    """
    raise NotImplementedError("TODO(Agatha) phase 5: train.train.main")


if __name__ == "__main__":
    main()
