from typing import Any
from app.constants import RootCauseCategory, AgentType
from app.utils.logger import get_logger
from app.anomaly_detection.feature_engineering import extract_metric_value

logger = get_logger(__name__)


class MetricAgent:
    def __init__(self):
        self.agent_type = AgentType.METRIC

    async def analyze(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze Prometheus metrics to identify root cause.
        Looks at CPU, Memory, Error Rate, and Latency.
        """
        logger.info("metric_agent_analysis_start")
        
        cpu_val = extract_metric_value(metrics.get("cpu", []))
        cpu_pct = cpu_val * 100.0 if cpu_val <= 1.0 else cpu_val
        
        mem_val = extract_metric_value(metrics.get("memory", []))
        # If memory is in bytes, it is a very large number. If it is <= 1.0, it is a percentage.
        mem_pct = mem_val * 100.0 if 0.0 < mem_val <= 1.0 else 0.0
        
        node_mem = metrics.get("node_memory", [])
        if node_mem:
            mem_pct = extract_metric_value(node_mem) * 100.0

        error_rate = extract_metric_value(metrics.get("error_rate", []))
        latency_val = extract_metric_value(metrics.get("latency_p99", []))
        latency_ms = latency_val * 1000.0 if latency_val < 50.0 else latency_val

        category = RootCauseCategory.UNKNOWN
        description = "No clear metric abnormalities detected."
        confidence = 0.0
        evidence = []

        if error_rate > 0.15:
            category = RootCauseCategory.DEPENDENCY_FAILURE
            description = f"Critical HTTP error rate detected: {error_rate:.1%}. Likely dependency or upstream service failure."
            confidence = 0.85
            evidence.append(f"HTTP error rate is at {error_rate:.1%}")
        elif error_rate > 0.05:
            category = RootCauseCategory.CONFIG_ERROR
            description = f"Elevated HTTP error rate detected: {error_rate:.1%}. Potential configuration error or partial outage."
            confidence = 0.70
            evidence.append(f"HTTP error rate is at {error_rate:.1%}")

        if mem_pct > 90.0:
            # Memory exhaustion
            if category == RootCauseCategory.UNKNOWN or confidence < 0.90:
                category = RootCauseCategory.MEMORY_LEAK
                description = f"Extreme memory utilization detected: {mem_pct:.1f}%. Strong indicator of memory leak or insufficient memory limit."
                confidence = 0.90
                evidence.append(f"Memory usage is at {mem_pct:.1f}%")
        elif cpu_pct > 90.0:
            # CPU exhaustion
            if category == RootCauseCategory.UNKNOWN or confidence < 0.85:
                category = RootCauseCategory.RESOURCE_EXHAUSTION
                description = f"CPU usage is critically high: {cpu_pct:.1f}%. CPU starvation is impacting performance."
                confidence = 0.85
                evidence.append(f"CPU usage is at {cpu_pct:.1f}%")

        if latency_ms > 2000.0:
            evidence.append(f"p99 latency is high: {latency_ms:.1f}ms")
            if category == RootCauseCategory.UNKNOWN:
                category = RootCauseCategory.NETWORK_ISSUE
                description = f"High p99 response latency: {latency_ms:.1f}ms. Possible network bottleneck or database slow queries."
                confidence = 0.65

        # If nothing was found, but there are some minor signals
        if category == RootCauseCategory.UNKNOWN:
            if cpu_pct > 70.0 or mem_pct > 70.0:
                category = RootCauseCategory.RESOURCE_EXHAUSTION
                description = f"Moderate resource usage: CPU {cpu_pct:.1f}%, Mem {mem_pct:.1f}%."
                confidence = 0.50
                evidence.append(f"CPU={cpu_pct:.1f}%, Memory={mem_pct:.1f}%")

        result = {
            "agent_type": self.agent_type.value,
            "root_cause_category": category.value,
            "root_cause_description": description,
            "confidence": confidence,
            "evidence": evidence,
        }
        logger.info("metric_agent_analysis_complete", result=result)
        return result
