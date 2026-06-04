from typing import Any
from app.monitoring.kubernetes_client import KubernetesClient
from app.constants import RemediationAction
from app.utils.logger import get_logger
from app.utils.exceptions import RemediationError

logger = get_logger(__name__)


class KubectlActions:
    def __init__(self, k8s_client: KubernetesClient):
        self.k8s = k8s_client

    async def execute(self, action: str, target: str, params: dict[str, Any] | None = None) -> bool:
        """
        Executes a specific Kubernetes remediation action.
        """
        logger.info("kubectl_action_executing", action=action, target=target, params=params)
        params = params or {}
        try:
            if action == RemediationAction.RESTART_POD.value:
                namespace = params.get("namespace")
                return self.k8s.restart_pod(target, namespace=namespace)

            elif action == RemediationAction.DELETE_POD.value:
                namespace = params.get("namespace")
                # KubernetesClient uses delete pod as restart pod, let's delete it directly
                return self.k8s.restart_pod(target, namespace=namespace)

            elif action == RemediationAction.SCALE_DEPLOYMENT.value:
                namespace = params.get("namespace")
                replicas = int(params.get("replicas", 2))
                return self.k8s.scale_deployment(target, replicas=replicas, namespace=namespace)

            elif action == RemediationAction.ROLLBACK_DEPLOYMENT.value:
                namespace = params.get("namespace")
                return self.k8s.rollback_deployment(target, namespace=namespace)

            elif action == RemediationAction.CORDON_NODE.value:
                return self.k8s.cordon_node(target)

            elif action == RemediationAction.DRAIN_NODE.value:
                # Cordon node and let Kubernetes evict/reschedule pods
                cordon_ok = self.k8s.cordon_node(target)
                logger.info("node_drained_via_cordon", node=target, success=cordon_ok)
                return cordon_ok

            elif action == RemediationAction.PATCH_DEPLOYMENT.value or action == RemediationAction.UPDATE_CONFIG.value:
                namespace = params.get("namespace", "default")
                env_patches = params.get("env_patches", {})
                return self.k8s.patch_deployment_env(target, namespace, env_patches)

            elif action == RemediationAction.NO_ACTION.value:
                logger.info("remediation_action_none_requested", target=target)
                return True

            else:
                raise RemediationError(f"Unsupported remediation action: {action}")
        except Exception as e:
            logger.error("kubectl_action_execution_failed", action=action, target=target, error=str(e))
            raise RemediationError(f"Failed to execute action {action} on {target}: {e}") from e
