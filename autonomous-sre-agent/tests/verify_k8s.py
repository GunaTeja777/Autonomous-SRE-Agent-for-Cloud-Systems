import sys
import os

# Add the project directory to sys.path to resolve imports correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app.monitoring.kubernetes_client import KubernetesClient

def main():
    client = KubernetesClient()
    
    # Try to load configuration
    client._load()
    
    print(f"Loaded status: {client._loaded == True}")
    
    if client._loaded == "mock":
        print("Connected to REAL Kubernetes cluster: False (Running in MOCK mode)")
        sys.exit(1)
        
    print("Connected to REAL Kubernetes cluster")
    
    try:
        # 1. Verify Node (desktop-control-plane)
        nodes = client.get_nodes()
        node_names = [n["name"] for n in nodes]
        if "desktop-control-plane" in node_names:
            pass
        else:
            print("WARNING: desktop-control-plane node not found in listed nodes")

        # 2. Verify Deployment (nginx-test)
        try:
            deploy = client.get_deployment("nginx-test")
            print("Found nginx-test deployment")
        except Exception as e:
            print(f"FAILED to find nginx-test deployment: {e}")

        # 3. Verify Pod (nginx-test)
        pods = client.get_pods()
        nginx_pods = [p for p in pods if "nginx-test" in p["name"]]
        if nginx_pods:
            print("Found nginx-test pod")
        else:
            print("FAILED to find nginx-test pod")

    except Exception as e:
        print(f"\n[ERROR] Failed to communicate with the cluster: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
