import numpy as np
from typing import Any
from app.utils.helpers import safe_divide


def extract_metric_value(prom_result: list[dict]) -> float:
    """Extract a scalar value from a Prometheus instant query result."""
    if not prom_result:
        return 0.0
    try:
        return float(prom_result[0]["value"][1])
    except (IndexError, KeyError, ValueError):
        return 0.0


def extract_metric_values_by_pod(prom_result: list[dict]) -> dict[str, float]:
    out = {}
    for item in prom_result:
        pod = item.get("metric", {}).get("pod", "unknown")
        try:
            out[pod] = float(item["value"][1])
        except (KeyError, ValueError):
            out[pod] = 0.0
    return out


def extract_range_series(prom_result: list[dict]) -> np.ndarray:
    """Extract a flat array of float values from a Prometheus range query result."""
    values = []
    for series in prom_result:
        for _ts, val in series.get("values", []):
            try:
                values.append(float(val))
            except ValueError:
                pass
    return np.array(values, dtype=float)


def build_feature_vector(metrics: dict[str, Any]) -> np.ndarray:
    """
    Build a flat feature vector from a metrics dict for anomaly detection.
    Expected keys: cpu, memory, error_rate, restart_count, latency_p99
    """
    cpu_val = extract_metric_value(metrics.get("cpu", []))
    mem_val = extract_metric_value(metrics.get("memory", [])) / (1024 ** 3)  # GB
    error_rate = extract_metric_value(metrics.get("error_rate", []))
    restart_count = sum(extract_metric_values_by_pod(metrics.get("restart_count", [])).values())
    latency = extract_metric_value(metrics.get("latency_p99", [])) * 1000  # ms

    return np.array([cpu_val, mem_val, error_rate, restart_count, latency], dtype=float)


def build_feature_matrix(historical_metrics: list[dict[str, Any]]) -> np.ndarray:
    """Build a 2D feature matrix from a list of metric snapshots."""
    rows = [build_feature_vector(m) for m in historical_metrics]
    return np.vstack(rows) if rows else np.empty((0, 5))


def normalize_features(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Min-max normalize. Returns (X_norm, min_vals, max_vals)."""
    min_vals = X.min(axis=0)
    max_vals = X.max(axis=0)
    range_vals = max_vals - min_vals
    range_vals[range_vals == 0] = 1.0  # avoid divide-by-zero
    return (X - min_vals) / range_vals, min_vals, max_vals


def compute_log_anomaly_features(log_lines: list[str]) -> dict[str, float]:
    error_keywords = ["error", "exception", "fatal", "panic", "oom", "killed"]
    warn_keywords = ["warn", "warning", "timeout", "retry"]

    total = len(log_lines)
    errors = sum(1 for l in log_lines if any(k in l.lower() for k in error_keywords))
    warns = sum(1 for l in log_lines if any(k in l.lower() for k in warn_keywords))

    return {
        "total_lines": float(total),
        "error_count": float(errors),
        "warn_count": float(warns),
        "error_ratio": safe_divide(errors, total),
        "warn_ratio": safe_divide(warns, total),
    }