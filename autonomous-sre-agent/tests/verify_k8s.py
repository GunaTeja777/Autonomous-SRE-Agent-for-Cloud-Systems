import sys
import os

# Add the project directory to sys.path to resolve imports correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app.monitoring.kubernetes_client import KubernetesClient
from app.config import get_settings

def main():
    print("=" * 60)
    print("KUBERNETES CONNECTIVITY VERIFICATION TEST")
    print("=" * 60)
    
    settings = get_settings()
    print(f"Configured Kubeconfig Path : {settings.kubeconfig_path}")
    print(f"Configured Namespace       : {settings.k8s_namespace}")
    print(f"Configured In-Cluster Mode : {settings.k8s_in_cluster}")
    print("-" * 60)

    print("Initializing KubernetesClient...")
    client = KubernetesClient()
    
    # Try to load configuration
    client._load()
    
    print(f"Loaded status: {client._loaded}")
    
    if client._loaded == "mock":
        print("\n[FAIL] KubernetesClient is running in MOCK mode.")
        print("Please ensure your local Kubernetes cluster is running and your .env matches the configuration.")
        sys.exit(1)
        
    print("\n[SUCCESS] Connected to a REAL Kubernetes cluster!")
    
    try:
        print(f"Listing pods in namespace '{client._default_namespace}'...")
        pods = client.get_pods()
        print(f"Total pods found: {len(pods)}")
        for i, pod in enumerate(pods, 1):
            print(f"\nPod #{i}:")
            print(f"  Name:         {pod['name']}")
            print(f"  Namespace:    {pod['namespace']}")
            print(f"  Phase:        {pod['phase']}")
            print(f"  Node:         {pod['node']}")
            print(f"  Ready Status: {pod['ready']}")
            print("  Containers:")
            for c in pod['containers']:
                print(f"    - Name: {c['name']}, Image: {c['image']}, Status: {c['state'].get('status')}")
    except Exception as e:
        print(f"\n[ERROR] Failed to communicate with the cluster: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
