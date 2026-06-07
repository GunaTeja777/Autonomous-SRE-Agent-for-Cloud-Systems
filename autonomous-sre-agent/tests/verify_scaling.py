import sys
import os
import asyncio

# Add the project directory to sys.path to resolve imports correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app.monitoring.kubernetes_client import KubernetesClient
from app.remediation.kubectl_actions import KubectlActions
from app.remediation.sandbox_validator import SandboxValidator
from app.remediation.executor import RemediationExecutor

async def main():
    # 1. Initialize client
    client = KubernetesClient()
    client._load()
    
    if client._loaded == "mock":
        print("Error: Kubernetes client is running in MOCK mode. Please configure real cluster connection first.")
        sys.exit(1)
        
    # 2. Get current deployment status
    try:
        init_deploy = client.get_deployment("nginx-test")
        print(f"Current Deployment: {init_deploy['name']}")
        print(f"Current Replicas: {init_deploy['replicas']}")
    except Exception as e:
        print(f"Error fetching deployment nginx-test: {e}")
        sys.exit(1)

    # 3. Setup Executor
    actions = KubectlActions(client)
    validator = SandboxValidator(client)
    executor = RemediationExecutor(actions, validator)

    # 4. Define remediation plan to scale to 3 replicas
    plan = {
        "plan_id": "PLAN-SCALE-VERIFY",
        "steps": [
            {
                "step": 1,
                "action": "scale_deployment",
                "target": "nginx-test",
                "params": {"replicas": 3, "namespace": "default"},
                "rollback_action": "no_action"
            }
        ]
    }

    # 5. Execute plan
    print("Executing remediation plan to scale nginx-test deployment to 3 replicas...")
    res = await executor.execute_plan(plan)
    if not res["success"]:
        print(f"Remediation plan execution failed: {res['message']}")
        sys.exit(1)

    # 6. Verify new replica count
    try:
        final_deploy = client.get_deployment("nginx-test")
        print("\nDeployment nginx-test")
        print(f"Replicas: {final_deploy['replicas']}")
    except Exception as e:
        print(f"Error verifying deployment replica count: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
