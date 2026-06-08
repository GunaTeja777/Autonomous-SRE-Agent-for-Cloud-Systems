from typing import Any
from app.constants import RootCauseCategory, AgentType
from app.utils.logger import get_logger

logger = get_logger(__name__)


class KubernetesAgent:
    def __init__(self):
        self.agent_type = AgentType.KUBERNETES

    async def analyze(self, pods: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze Kubernetes pods and events to identify infrastructure/platform root causes.
        """
        logger.info("kubernetes_agent_analysis_start")

        category = RootCauseCategory.UNKNOWN
        description = "Kubernetes pods and events appear healthy."
        confidence = 0.0
        evidence = []

        # 1. Inspect Pods and Container states
        for pod in pods:
            pod_name = pod.get("name", "unknown")
            restart_count = pod.get("restart_count", 0)

            # Check if restart count is abnormally high
            if restart_count > 5:
                evidence.append(f"Pod {pod_name} has restarted {restart_count} times.")

            for container in pod.get("containers", []):
                state = container.get("state", {})
                status = state.get("status")
                c_name = container.get("name", "unknown")

                # Check waiting reasons
                if status == "waiting":
                    reason = state.get("reason") or ""
                    message = state.get("message") or ""
                    evidence.append(f"Container {c_name} in pod {pod_name} is waiting (reason: {reason}, msg: {message})")

                    if "crashloop" in reason.lower() or "crashloopbackoff" in reason.lower():
                        category = RootCauseCategory.CRASHLOOP
                        description = f"Pod {pod_name} container {c_name} is in CrashLoopBackOff. It is failing repeatedly."
                        confidence = 0.95
                    elif "imagepull" in reason.lower() or "errimagepull" in reason.lower():
                        category = RootCauseCategory.IMAGE_PULL
                        description = f"Pod {pod_name} container {c_name} is failing to pull image: {container.get('image')}. Reason: {reason}."
                        confidence = 0.95
                    elif "configerror" in reason.lower() or "createcontainerconfigerror" in reason.lower():
                        category = RootCauseCategory.CONFIG_ERROR
                        description = f"Pod {pod_name} container {c_name} has configuration errors. Reason: {reason}."
                        confidence = 0.90

                # Check terminated reasons (OOM)
                elif status == "terminated":
                    reason = state.get("reason") or ""
                    exit_code = state.get("exit_code")
                    evidence.append(f"Container {c_name} in pod {pod_name} terminated (reason: {reason}, exit_code: {exit_code})")

                    if "oomkilled" in reason.lower() or exit_code == 137:
                        category = RootCauseCategory.MEMORY_LEAK
                        description = f"Pod {pod_name} container {c_name} was terminated with OOMKilled (Exit Code 137)."
                        confidence = 0.95

        # 2. Inspect Events (Failed scheduling, node issues, etc.)
        for event in events:
            reason = event.get("reason") or ""
            message = event.get("message") or ""
            event_type = event.get("type") or ""
            involved_obj = event.get("involved_object") or ""

            # Schedule failures / Node capacity issues
            if "failedscheduling" in reason.lower() or "insufficient" in message.lower():
                evidence.append(f"Scheduling event warning: {message} (object: {involved_obj})")
                if category == RootCauseCategory.UNKNOWN or confidence < 0.85:
                    category = RootCauseCategory.NODE_FAILURE
                    description = f"Failed to schedule pods on nodes. Reason: {message}."
                    confidence = 0.85

            elif "noderady" in reason.lower() or "notready" in message.lower() or "nodeoutofdisk" in reason.lower():
                evidence.append(f"Node condition event warning: {message} (object: {involved_obj})")
                if category == RootCauseCategory.UNKNOWN or confidence < 0.90:
                    category = RootCauseCategory.NODE_FAILURE
                    description = f"Kubernetes node failure detected: {message}."
                    confidence = 0.90

            elif "backoff" in reason.lower() and event_type.lower() == "warning":
                evidence.append(f"Warning backoff event: {message} (object: {involved_obj})")
                if category == RootCauseCategory.UNKNOWN or confidence < 0.80:
                    category = RootCauseCategory.CRASHLOOP
                    description = f"Pod restarting warning event: {message}."
                    confidence = 0.80

        # Fallback if high restart count but no clear container state
        if category == RootCauseCategory.UNKNOWN:
            high_restart_pods = [p for p in pods if p.get("restart_count", 0) > 3]
            if high_restart_pods:
                category = RootCauseCategory.CRASHLOOP
                description = f"Pods {', '.join(p['name'] for p in high_restart_pods)} have elevated restart counts."
                confidence = 0.75

        result = {
            "agent_type": self.agent_type.value,
            "root_cause_category": category.value,
            "root_cause_description": description,
            "confidence": confidence,
            "evidence": list(set(evidence))[:15], # Deduplicate and cap evidence
        }
        logger.info("kubernetes_agent_analysis_complete", result=result)
        return result
