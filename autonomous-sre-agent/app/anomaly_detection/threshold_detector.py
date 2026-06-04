from typing import Any
from app.config import get_settings
from app.utils.logger import get_logger
from app.anomaly_detection.feature_engineering import extract_metric_value

logger = get_logger(__name__)


class ThresholdDetector:
    def __init__(self):
        self.settings = get_settings()

    def check(self, metrics: dict[str, Any]) -> dict[str, Any]:
        violations = []

        # 1. CPU check
        cpu_val = extract_metric_value(metrics.get("cpu", []))
        # If cpu_val is a fraction (e.g. 0.90 for 90%), normalize to percentage
        cpu_pct = cpu_val * 100.0 if cpu_val <= 1.0 else cpu_val
        if cpu_pct > self.settings.threshold_cpu_percent:
            violations.append({
                "metric": "CPU Usage",
                "value": cpu_pct,
                "threshold": self.settings.threshold_cpu_percent,
                "severity": "critical" if cpu_pct > 95.0 else "high",
            })

        # 2. Memory check
        node_metrics = metrics.get("node_memory", [])
        mem_pct = 0.0
        if node_metrics:
            mem_pct = extract_metric_value(node_metrics) * 100.0
        else:
            mem_val = extract_metric_value(metrics.get("memory", []))
            if 0.0 < mem_val <= 1.0:
                mem_pct = mem_val * 100.0
            elif 1.0 < mem_val <= 100.0:
                mem_pct = mem_val

        if mem_pct > self.settings.threshold_memory_percent:
            violations.append({
                "metric": "Memory Usage",
                "value": mem_pct,
                "threshold": self.settings.threshold_memory_percent,
                "severity": "critical" if mem_pct > 95.0 else "high",
            })

        # 3. Error Rate check
        err_val = extract_metric_value(metrics.get("error_rate", []))
        if err_val > self.settings.threshold_error_rate:
            violations.append({
                "metric": "Error Rate",
                "value": err_val,
                "threshold": self.settings.threshold_error_rate,
                "severity": "critical" if err_val > 0.15 else "high",
            })

        # 4. Latency p99 check
        lat_val = extract_metric_value(metrics.get("latency_p99", []))
        # Latency in prometheus is typically in seconds. Convert to ms if needed.
        lat_ms = lat_val * 1000.0 if lat_val < 50.0 else lat_val
        if lat_ms > self.settings.threshold_latency_p99_ms:
            violations.append({
                "metric": "p99 Latency",
                "value": lat_ms,
                "threshold": self.settings.threshold_latency_p99_ms,
                "severity": "critical" if lat_ms > (self.settings.threshold_latency_p99_ms * 1.5) else "high",
            })

        anomaly = len(violations) > 0
        return {
            "anomaly": anomaly,
            "violations": violations,
        }