import numpy as np
from sklearn.ensemble import IsolationForest as SKLearnIsolationForest
from typing import Any

from app.config import get_settings
from app.utils.logger import get_logger
from app.anomaly_detection.feature_engineering import build_feature_vector, build_feature_matrix

logger = get_logger(__name__)


class IsolationForestDetector:
    def __init__(self):
        settings = get_settings()
        self.contamination = settings.anomaly_contamination
        self._model: SKLearnIsolationForest | None = None
        self._fitted = False

    def fit(self, historical_metrics: list[dict[str, Any]]) -> None:
        X = build_feature_matrix(historical_metrics)
        if X.shape[0] < 10:
            logger.warning("isolation_forest_insufficient_data", samples=X.shape[0])
            return
        self._model = SKLearnIsolationForest(
            contamination=self.contamination,
            n_estimators=100,
            random_state=42,
        )
        self._model.fit(X)
        self._fitted = True
        logger.info("isolation_forest_fitted", samples=X.shape[0])

    def predict(self, metrics: dict[str, Any]) -> dict[str, Any]:
        if not self._fitted or self._model is None:
            return {"anomaly": False, "score": 0.0, "reason": "model_not_fitted"}

        vec = build_feature_vector(metrics).reshape(1, -1)
        prediction = self._model.predict(vec)[0]          # -1 = anomaly, 1 = normal
        score = float(self._model.score_samples(vec)[0])  # more negative = more anomalous

        is_anomaly = prediction == -1
        return {
            "anomaly": is_anomaly,
            "score": score,
            "raw_prediction": int(prediction),
        }

    def fit_predict(self, historical_metrics: list[dict[str, Any]], current_metrics: dict[str, Any]) -> dict[str, Any]:
        self.fit(historical_metrics)
        return self.predict(current_metrics)