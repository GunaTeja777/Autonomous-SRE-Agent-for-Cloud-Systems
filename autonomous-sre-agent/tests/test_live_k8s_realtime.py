import asyncio
from app.monitoring.kubernetes_client import KubernetesClient
from app.remediation.kubectl_actions import KubectlActions
from app.remediation.sandbox_validator import SandboxValidator
from app.remediation.executor import RemediationExecutor


async def run():
    print("=== LIVE KUBERNETES REAL-TIME EXECUTION TEST ===")
    client = KubernetesClient()
    actions = KubectlActions(client)
    validator = SandboxValidator(client)
    executor = RemediationExecutor(actions, validator)

    # 1. Inspect Initial State
    d_before = client.get_deployment("nginx-test")
    print(f"1. Current Deployment in Kubernetes: {d_before['name']}, Replicas: {d_before['replicas']}")

    # 2. Define Remediation Plan
    target_replicas = 5 if d_before["replicas"] != 5 else 2
    plan = {
        "plan_id": "REALTIME-LIVE-TEST",
        "steps": [
            {
                "step": 1,
                "action": "scale_deployment",
                "target": "nginx-test",
                "params": {"replicas": target_replicas, "namespace": "default"},
                "rollback_action": "no_action",
            }
        ],
    }

    print(f"2. Triggering RemediationExecutor -> Scale 'nginx-test' to {target_replicas} replicas...")
    res = await executor.execute_plan(plan)
    print(f"   Execution Result: {res['message']} (Success: {res['success']})")

    # 3. Read back from real Kubernetes API
    d_after = client.get_deployment("nginx-test")
    print(f"3. Real Kubernetes API State after scaling: {d_after['name']}, Replicas: {d_after['replicas']}")
    print(f"   Pods listed by KubernetesClient: {len([p for p in client.get_pods() if 'nginx-test' in p['name']])} pods")


if __name__ == "__main__":
    asyncio.run(run())
