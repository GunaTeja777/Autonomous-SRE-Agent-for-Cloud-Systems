from typing import Any
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.exceptions import KubernetesClientError

logger = get_logger(__name__)


class KubernetesClient:
    def __init__(self):
        settings = get_settings()
        self._in_cluster = settings.k8s_in_cluster
        self._kubeconfig = settings.kubeconfig_path
        self._default_namespace = settings.k8s_namespace
        self._v1 = None
        self._apps_v1 = None
        self._core_v1 = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            from kubernetes import client, config as k8s_config
            if self._in_cluster:
                k8s_config.load_incluster_config()
            else:
                k8s_config.load_kube_config(config_file=self._kubeconfig)
            self._v1 = client.CoreV1Api()
            self._apps_v1 = client.AppsV1Api()
            self._loaded = True
            logger.info("kubernetes_client_loaded")
        except Exception as e:
            raise KubernetesClientError(f"Failed to load Kubernetes config: {e}") from e

    @property
    def v1(self):
        self._load()
        return self._v1

    @property
    def apps_v1(self):
        self._load()
        return self._apps_v1

    def get_pods(self, namespace: str | None = None) -> list[dict[str, Any]]:
        ns = namespace or self._default_namespace
        try:
            pods = self.v1.list_namespaced_pod(namespace=ns)
            return [self._pod_summary(p) for p in pods.items]
        except Exception as e:
            raise KubernetesClientError(f"Failed to list pods: {e}") from e

    def _pod_summary(self, pod) -> dict[str, Any]:
        containers = pod.status.container_statuses or []
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "restart_count": sum(c.restart_count for c in containers),
            "ready": all(c.ready for c in containers) if containers else False,
            "containers": [
                {
                    "name": c.name,
                    "ready": c.ready,
                    "restart_count": c.restart_count,
                    "state": self._container_state(c.state),
                    "image": c.image,
                }
                for c in containers
            ],
            "conditions": [
                {"type": cond.type, "status": cond.status, "reason": cond.reason}
                for cond in (pod.status.conditions or [])
            ],
        }

    def _container_state(self, state) -> dict[str, Any]:
        if state.running:
            return {"status": "running", "started_at": str(state.running.started_at)}
        elif state.waiting:
            return {"status": "waiting", "reason": state.waiting.reason, "message": state.waiting.message}
        elif state.terminated:
            return {
                "status": "terminated",
                "reason": state.terminated.reason,
                "exit_code": state.terminated.exit_code,
            }
        return {"status": "unknown"}

    def get_deployment(self, name: str, namespace: str | None = None) -> dict[str, Any]:
        ns = namespace or self._default_namespace
        try:
            d = self.apps_v1.read_namespaced_deployment(name=name, namespace=ns)
            return {
                "name": d.metadata.name,
                "namespace": d.metadata.namespace,
                "replicas": d.spec.replicas,
                "ready_replicas": d.status.ready_replicas or 0,
                "available_replicas": d.status.available_replicas or 0,
                "image": d.spec.template.spec.containers[0].image if d.spec.template.spec.containers else None,
                "labels": d.metadata.labels or {},
            }
        except Exception as e:
            raise KubernetesClientError(f"Failed to get deployment {name}: {e}") from e

    def get_nodes(self) -> list[dict[str, Any]]:
        try:
            nodes = self.v1.list_node()
            return [
                {
                    "name": n.metadata.name,
                    "ready": any(
                        c.type == "Ready" and c.status == "True"
                        for c in (n.status.conditions or [])
                    ),
                    "unschedulable": n.spec.unschedulable or False,
                    "labels": n.metadata.labels or {},
                    "capacity": {
                        "cpu": n.status.capacity.get("cpu"),
                        "memory": n.status.capacity.get("memory"),
                    },
                }
                for n in nodes.items
            ]
        except Exception as e:
            raise KubernetesClientError(f"Failed to list nodes: {e}") from e

    def get_events(self, namespace: str | None = None, field_selector: str | None = None) -> list[dict[str, Any]]:
        ns = namespace or self._default_namespace
        kwargs: dict[str, Any] = {"namespace": ns}
        if field_selector:
            kwargs["field_selector"] = field_selector
        try:
            events = self.v1.list_namespaced_event(**kwargs)
            return [
                {
                    "name": e.metadata.name,
                    "reason": e.reason,
                    "message": e.message,
                    "type": e.type,
                    "count": e.count,
                    "involved_object": e.involved_object.name,
                    "first_time": str(e.first_timestamp),
                    "last_time": str(e.last_timestamp),
                }
                for e in events.items
            ]
        except Exception as e:
            raise KubernetesClientError(f"Failed to list events: {e}") from e

    def restart_pod(self, pod_name: str, namespace: str | None = None) -> bool:
        ns = namespace or self._default_namespace
        try:
            self.v1.delete_namespaced_pod(name=pod_name, namespace=ns)
            logger.info("pod_restarted", pod=pod_name, namespace=ns)
            return True
        except Exception as e:
            raise KubernetesClientError(f"Failed to restart pod {pod_name}: {e}") from e

    def scale_deployment(self, name: str, replicas: int, namespace: str | None = None) -> bool:
        ns = namespace or self._default_namespace
        try:
            body = {"spec": {"replicas": replicas}}
            self.apps_v1.patch_namespaced_deployment_scale(name=name, namespace=ns, body=body)
            logger.info("deployment_scaled", deployment=name, replicas=replicas, namespace=ns)
            return True
        except Exception as e:
            raise KubernetesClientError(f"Failed to scale deployment {name}: {e}") from e

    def rollback_deployment(self, name: str, namespace: str | None = None) -> bool:
        ns = namespace or self._default_namespace
        try:
            # 1. Read deployment to get current revision and selector
            deploy = self.apps_v1.read_namespaced_deployment(name=name, namespace=ns)
            current_revision = deploy.metadata.annotations.get("deployment.kubernetes.io/revision")
            if not current_revision:
                raise KubernetesClientError("No revision annotation found on deployment.")

            target_revision = str(int(current_revision) - 1)
            if int(target_revision) <= 0:
                raise KubernetesClientError(f"Cannot rollback: target revision {target_revision} is invalid.")

            # 2. Get list of ReplicaSets in the namespace to find the previous one
            replica_sets = self.apps_v1.list_namespaced_replica_set(namespace=ns)
            target_rs = None
            for rs in replica_sets.items:
                owners = rs.metadata.owner_references or []
                belongs_to_deploy = any(o.kind == "Deployment" and o.name == name for o in owners)
                if belongs_to_deploy:
                    rs_revision = rs.metadata.annotations.get("deployment.kubernetes.io/revision")
                    if rs_revision == target_revision:
                        target_rs = rs
                        break

            if not target_rs:
                raise KubernetesClientError(f"Could not find ReplicaSet for deployment '{name}' with revision '{target_revision}'.")

            # 3. Patch the deployment's spec.template with the target ReplicaSet's spec.template
            template_dict = self.apps_v1.api_client.sanitize_for_serialization(target_rs.spec.template)
            body = {
                "spec": {
                    "template": template_dict
                }
            }
            self.apps_v1.patch_namespaced_deployment(name=name, namespace=ns, body=body)
            logger.info("deployment_rolled_back", deployment=name, target_revision=target_revision, namespace=ns)
            return True
        except Exception as e:
            raise KubernetesClientError(f"Failed to rollback deployment {name}: {e}") from e

    def cordon_node(self, node_name: str) -> bool:
        try:
            body = {"spec": {"unschedulable": True}}
            self.v1.patch_node(name=node_name, body=body)
            logger.info("node_cordoned", node=node_name)
            return True
        except Exception as e:
            raise KubernetesClientError(f"Failed to cordon node {node_name}: {e}") from e

    def patch_deployment_env(self, name: str, namespace: str, env_patches: dict[str, str]) -> bool:
        try:
            from kubernetes.client.models import V1EnvVar
            deploy = self.apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            containers = deploy.spec.template.spec.containers
            for container in containers:
                existing = {e.name: e for e in (container.env or [])}
                for k, v in env_patches.items():
                    existing[k] = V1EnvVar(name=k, value=v)
                container.env = list(existing.values())
            self.apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=deploy)
            logger.info("deployment_env_patched", deployment=name, keys=list(env_patches.keys()))
            return True
        except Exception as e:
            raise KubernetesClientError(f"Failed to patch deployment env: {e}") from e