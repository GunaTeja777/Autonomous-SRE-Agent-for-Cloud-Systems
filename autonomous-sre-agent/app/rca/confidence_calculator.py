from typing import Any

class ConfidenceCalculator:
    """Calculates weighted consensus confidence scores from SRE agent analyses."""

    def __init__(self):
        # Weights can represent agent reliability for specific categories
        # e.g., KubernetesAgent has highest reliability for image_pull
        pass

    def calculate(self, agent_outputs: list[dict[str, Any]]) -> float:
        if not agent_outputs:
            return 0.0
        
        confidences = [f.get("confidence", 0.0) for f in agent_outputs if f.get("confidence") is not None]
        if not confidences:
            return 0.0
            
        return sum(confidences) / len(confidences)
