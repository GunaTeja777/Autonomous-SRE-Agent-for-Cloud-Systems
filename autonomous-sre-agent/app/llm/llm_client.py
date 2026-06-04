from typing import Any
from app.anomaly_detection.isolation_forest import IsolationForestDetector
from app.anomaly_detection.threshold_detector import ThresholdDetector
from app.anomaly_detection.feature_engineering import compute_log_anomaly_features
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnomalyDetector:
    """
    Combines threshold-based and ML-based detection.
    Returns a unified anomaly report with severity and signals.
    """

    def __init__(self):
        self.threshold_detector = ThresholdDetector()
        self.isolation_forest = IsolationForestDetector()

    async def detect(
        self,
        metrics: dict[str, Any],
        logs: dict[str, list[str]] | None = None,
        historical_metrics: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:

        threshold_result = self.threshold_detector.check(metrics)

        ml_result: dict[str, Any] = {"anomaly": False, "score": 0.0}
        if historical_metrics and len(historical_metrics) >= 10:
            ml_result = self.isolation_forest.fit_predict(historical_metrics, metrics)

        log_features: dict[str, float] = {}
        log_anomaly = False
        if logs:
            all_lines = []
            for lines in logs.values():
                all_lines.extend(lines)
            log_features = compute_log_anomaly_features(all_lines)
            log_anomaly = log_features.get("error_ratio", 0) > 0.3

        is_anomaly = threshold_result["anomaly"] or ml_result["anomaly"] or log_anomaly

        severity = self._determine_severity(threshold_result, ml_result, log_features)

        signals: list[str] = []
        if threshold_result["anomaly"]:
            for v in threshold_result["violations"]:
                signals.append(f"{v['metric']} exceeded threshold ({v['value']:.3f} > {v['threshold']})")
        if ml_result["anomaly"]:
            signals.append(f"Isolation Forest flagged anomaly (score={ml_result['score']:.3f})")
        if log_anomaly:
            signals.append(f"High log error ratio: {log_features.get('error_ratio', 0):.1%}")

        return {
            "anomaly": is_anomaly,
            "severity": severity,
            "signals": signals,
            "threshold_result": threshold_result,
            "ml_result": ml_result,
            "log_features": log_features,
        }

    def _determine_severity(
        self,
        threshold: dict[str, Any],
        ml: dict[str, Any],
        log_features: dict[str, float],
    ) -> str:
        if not threshold["anomaly"] and not ml["anomaly"]:
            return "low"

        critical_violations = [
            v for v in threshold.get("violations", []) if v.get("severity") == "critical"
        ]
        if critical_violations:
            return "critical"

        high_violations = [
            v for v in threshold.get("violations", []) if v.get("severity") == "high"
        ]
        if high_violations or (ml["anomaly"] and ml.get("score", 0) < -0.3):
            return "high"

        return "medium"