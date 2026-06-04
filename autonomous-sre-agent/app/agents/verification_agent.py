from typing import Any
from app.constants import AgentType
from app.config import get_settings
from app.utils.logger import get_logger
from app.llm.chains import VerificationChain
from app.llm.llm_client import LLMClient
from app.anomaly_detection.feature_engineering import extract_metric_value

logger = get_logger(__name__)


class VerificationAgent:
    def __init__(self, llm_client: LLMClient | None = None):
        self.agent_type = AgentType.VERIFICATION
        self.settings = get_settings()
        self.llm_client = llm_client
        self.verification_chain = VerificationChain(llm_client) if llm_client else None

    async def verify(self, incident: dict[str, Any], post_state: dict[str, Any]) -> dict[str, Any]:
        """
        Verify if the system recovered after remediation.
        Checks post-remediation metrics, Kubernetes pods health, and Loki logs.
        """
        logger.info("verification_agent_start", incident_id=incident.get("incident_id"))

        evidence = []
        remaining_issues = []
        resolved = True
        confidence = 1.0

        metrics = post_state.get("metrics", {})
        k8s_state = post_state.get("k8s_state", {})
        logs = post_state.get("logs", {})

        # 1. Verify Metrics
        cpu_val = extract_metric_value(metrics.get("cpu", []))
        cpu_pct = cpu_val * 100.0 if cpu_val <= 1.0 else cpu_val
        if cpu_pct > self.settings.threshold_cpu_percent:
            resolved = False
            remaining_issues.append(f"CPU Usage is still high: {cpu_pct:.1f}%")
            confidence -= 0.2
        else:
            evidence.append(f"CPU Usage recovered to {cpu_pct:.1f}%")

        node_mem = metrics.get("node_memory", [])
        mem_pct = 0.0
        if node_mem:
            mem_pct = extract_metric_value(node_mem) * 100.0
        else:
            mem_val = extract_metric_value(metrics.get("memory", []))
            if 0.0 < mem_val <= 1.0:
                mem_pct = mem_val * 100.0
            elif 1.0 < mem_val <= 100.0:
                mem_pct = mem_val
        
        if mem_pct > self.settings.threshold_memory_percent:
            resolved = False
            remaining_issues.append(f"Memory Usage is still high: {mem_pct:.1f}%")
            confidence -= 0.2
        elif mem_pct > 0:
            evidence.append(f"Memory Usage stabilized at {mem_pct:.1f}%")

        err_val = extract_metric_value(metrics.get("error_rate", []))
        if err_val > self.settings.threshold_error_rate:
            resolved = False
            remaining_issues.append(f"HTTP error rate is still high: {err_val:.1%}")
            confidence -= 0.3
        else:
            evidence.append(f"HTTP error rate is normal: {err_val:.1%}")

        # 2. Verify Kubernetes Pod State
        pods = k8s_state.get("pods", [])
        unhealthy_pods = []
        for pod in pods:
            if not pod.get("ready", False) or pod.get("phase") != "Running":
                unhealthy_pods.append(pod.get("name", "unknown"))

        if unhealthy_pods:
            resolved = False
            remaining_issues.append(f"Some pods are not ready/healthy: {', '.join(unhealthy_pods)}")
            confidence -= 0.3
        else:
            evidence.append("All Kubernetes pods are healthy and Ready.")

        # 3. Verify Logs
        error_logs = logs.get("errors", [])
        if len(error_logs) > 5:
            resolved = False
            remaining_issues.append(f"Error logs are still printing ({len(error_logs)} events).")
            confidence -= 0.15
        else:
            evidence.append("No critical error logs detected post-remediation.")

        # Normalize confidence
        confidence = max(0.0, min(1.0, confidence))

        # Call LLM if available and not a mock client
        if self.llm_client and self.llm_client._get_client() != "mock":
            try:
                llm_result = await self.verification_chain.run(incident, post_state)
                logger.info("verification_agent_llm_success", result=llm_result)
                return {
                    "agent_type": self.agent_type.value,
                    "resolved": llm_result.get("resolved", resolved),
                    "confidence": llm_result.get("confidence", confidence),
                    "evidence": llm_result.get("evidence", evidence),
                    "remaining_issues": llm_result.get("remaining_issues", remaining_issues),
                    "recommendation": llm_result.get("recommendation", "close" if resolved else "escalate"),
                }
            except Exception as e:
                logger.warning("verification_agent_llm_failed_falling_back", error=str(e))

        recommendation = "close" if resolved else "escalate"

        result = {
            "agent_type": self.agent_type.value,
            "resolved": resolved,
            "confidence": round(confidence, 2),
            "evidence": evidence,
            "remaining_issues": remaining_issues,
            "recommendation": recommendation,
        }
        logger.info("verification_agent_complete", result=result)
        return result
