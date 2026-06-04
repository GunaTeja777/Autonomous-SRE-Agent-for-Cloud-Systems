from typing import Any
from app.monitoring.kubernetes_client import KubernetesClient
from app.constants import RemediationAction
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SandboxValidator:
    def __init__(self, k8s_client: KubernetesClient):
        self.k8s = k8s_client

    async def validate(self, action: str, target: str, params: dict[str, Any] | None = None) -> tuple[bool, str]:
        """
        Validates whether a proposed remediation step is safe and executable against the Kubernetes cluster.
        Returns (is_valid, reason)
        """
        logger.info("sandbox_validating_action", action=action, target=target)
        params = params or {}
        namespace = params.get("namespace", "default")

        try:
            if action in [RemediationAction.RESTART_POD.value, RemediationAction.DELETE_POD.value]:
                pods = self.k8s.get_pods(namespace=namespace)
                pod_names = [p["name"] for p in pods]
                # Look for exact match or matching prefix
                matching = [p for p in pod_names if p == target or p.startswith(target)]
                if not matching:
                    return False, f"Target pod '{target}' not found in namespace '{namespace}'."
                return True, "Valid pod target."

            elif action in [RemediationAction.SCALE_DEPLOYMENT.value, RemediationAction.ROLLBACK_DEPLOYMENT.value, RemediationAction.PATCH_DEPLOYMENT.value, RemediationAction.UPDATE_CONFIG.value]:
                try:
                    deploy = self.k8s.get_deployment(name=target, namespace=namespace)
                    if action == RemediationAction.SCALE_DEPLOYMENT.value:
                        replicas = params.get("replicas")
                        if replicas is None:
                            return False, "Scale deployment requires 'replicas' parameter."
                        if not isinstance(replicas, int) or replicas < 0 or replicas > 20:
                            return False, f"Invalid replicas value: {replicas}. Must be between 0 and 20."
                    return True, "Valid deployment target."
                except Exception:
                    return False, f"Target deployment '{target}' not found in namespace '{namespace}'."

            elif action in [RemediationAction.CORDON_NODE.value, RemediationAction.DRAIN_NODE.value]:
                nodes = self.k8s.get_nodes()
                node_names = [n["name"] for n in nodes]
                if target not in node_names:
                    return False, f"Target node '{target}' not found in the cluster."
                return True, "Valid node target."

            elif action == RemediationAction.NO_ACTION.value:
                return True, "No action required."

            else:
                return False, f"Unknown action type: {action}"
        except Exception as e:
            logger.error("sandbox_validation_error", action=action, target=target, error=str(e))
            return False, f"Failed to perform sandbox validation: {e}"
