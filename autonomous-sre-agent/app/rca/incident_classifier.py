from typing import Any
from app.constants import IncidentSeverity

class IncidentClassifier:
    """Classifies anomalies and incidents into severity categories."""
    
    def __init__(self):
        pass

    def classify(self, anomaly_report: dict[str, Any]) -> dict[str, Any]:
        severity_str = anomaly_report.get("severity", "medium").upper()
        severity = getattr(IncidentSeverity, severity_str, IncidentSeverity.MEDIUM)
        
        # Extract target resource details from threshold/ml violations
        target_resource = "unknown"
        threshold_result = anomaly_report.get("threshold_result", {})
        
        # Check if we can identify target from violations
        violations = threshold_result.get("violations", [])
        if violations:
            target_resource = violations[0].get("metric", "unknown")
            
        signals = anomaly_report.get("signals", [])
        if target_resource == "unknown" and signals:
            target_resource = signals[0]

        return {
            "severity": severity,
            "target_resource": target_resource,
            "timestamp": anomaly_report.get("timestamp")
        }
