"""The scoring artefact shared by training, batch scoring and the API.

One object holds everything a scorer needs: the calibrated estimator, the exact feature order, the decision
threshold and a version string. The API and the monthly replay load the same file, so they cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class SigapModel:
    estimator: object  # calibrated classifier with predict_proba
    booster: object  # the uncalibrated tree model, used for SHAP contributions (None for linear models)
    features: list[str]
    threshold: float
    version: str
    metadata: dict = field(default_factory=dict)

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """Calibrated fraud probability per row."""
        return self.estimator.predict_proba(X[self.features])[:, 1]

    def contributions(self, X: pd.DataFrame) -> pd.DataFrame:
        """Per-row SHAP contributions (log-odds scale) from the tree model; columns = features."""
        import xgboost as xgb

        if self.booster is None:
            raise ValueError("contributions need a tree model")
        dm = xgb.DMatrix(X[self.features], feature_names=self.features)
        values = self.booster.get_booster().predict(dm, pred_contribs=True)
        return pd.DataFrame(values[:, :-1], columns=self.features, index=X.index)  # last column = bias

    def save(self, folder: Path) -> Path:
        import json

        import joblib

        folder.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, folder / "model.joblib")
        meta = {"version": self.version, "threshold": self.threshold, "features": self.features, **self.metadata}
        (folder / "metadata.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        return folder / "model.joblib"


def load_model(folder: Path) -> SigapModel:
    import joblib

    return joblib.load(folder / "model.joblib")
