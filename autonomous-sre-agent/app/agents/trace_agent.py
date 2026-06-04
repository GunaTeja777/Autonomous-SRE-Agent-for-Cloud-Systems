from typing import Any
from app.constants import RootCauseCategory, AgentType
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TraceAgent:
    def __init__(self):
        self.agent_type = AgentType.TRACE

    async def analyze(
        self,
        error_traces: list[dict[str, Any]],
        slow_traces: list[dict[str, Any]],
        latency_dist: dict[str, float],
        dependency_errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze Jaeger traces, latency distribution, and dependency errors to identify root cause.
        """
        logger.info("trace_agent_analysis_start")

        category = RootCauseCategory.UNKNOWN
        description = "No anomalous patterns or errors found in traces."
        confidence = 0.0
        evidence = []

        # 1. Dependency Error check (Explicit external calls failing)
        if dependency_errors:
            failed_svcs = [d.get("service", "unknown") for d in dependency_errors if d.get("error_count", 0) > 0]
            if failed_svcs:
                category = RootCauseCategory.DEPENDENCY_FAILURE
                description = f"Traces show failed downstream requests to services: {', '.join(failed_svcs)}. Root cause is likely a downstream dependency failure."
                confidence = 0.88
                evidence.append(f"Dependency errors found in Jaeger: {dependency_errors}")

        # 2. Critical Latency degradation
        elif latency_dist and latency_dist.get("p99", 0.0) > 2.0:
            p99 = latency_dist["p99"]
            mean = latency_dist.get("mean", 0.0)
            category = RootCauseCategory.NETWORK_ISSUE
            description = f"Critical latency increase detected. p99: {p99:.2f}s, mean: {mean:.2f}s. Traces show long-running spans indicating network delays or slow database queries."
            confidence = 0.80
            evidence.append(f"Latency P99 is {p99:.2f}s (mean={mean:.2f}s)")
            if slow_traces:
                evidence.append(f"Found {len(slow_traces)} slow traces exceeding threshold.")

        # 3. High Error Trace count without dependency errors (Internal error)
        elif len(error_traces) > 5:
            category = RootCauseCategory.CONFIG_ERROR
            description = f"Frequent HTTP/gRPC span errors ({len(error_traces)}) detected inside the service. Likely due to application internal exceptions or configuration errors."
            confidence = 0.70
            evidence.append(f"Found {len(error_traces)} internal error spans in traces.")

        result = {
            "agent_type": self.agent_type.value,
            "root_cause_category": category.value,
            "root_cause_description": description,
            "confidence": confidence,
            "evidence": evidence,
        }
        logger.info("trace_agent_analysis_complete", result=result)
        return result
