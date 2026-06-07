import sys
import os
import asyncio

# Add the project directory to sys.path to resolve imports correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app.monitoring.prometheus_client import PrometheusClient

async def main():
    client = PrometheusClient()
    
    # 1. Verify connection
    try:
        up_results = await client.query("up")
        print("Connected to REAL Prometheus\n")
    except Exception as e:
        print(f"FAILED to connect to Prometheus: {e}")
        sys.exit(1)

    # 2. Wait for metrics to populate
    nginx_found = False
    cpu_available = False
    mem_available = False
    
    for attempt in range(1, 13):
        try:
            cpu_metrics = await client.get_cpu_usage(namespace="default", pod="nginx-test")
            mem_metrics = await client.get_memory_usage(namespace="default", pod="nginx-test")
            
            if cpu_metrics:
                nginx_found = True
                cpu_available = True
            if mem_metrics:
                mem_available = True
                
            if cpu_available and mem_available:
                break
        except Exception as e:
            pass
        
        await asyncio.sleep(5)

    if nginx_found:
        print("Found nginx-test metrics\n")
    else:
        print("FAILED to find nginx-test metrics in Prometheus.\n")

    if cpu_available:
        print("CPU Metrics Available\n")
    else:
        print("FAILED: CPU Metrics not available in Prometheus.\n")

    if mem_available:
        print("Memory Metrics Available\n")
    else:
        print("FAILED: Memory Metrics not available in Prometheus.\n")

if __name__ == "__main__":
    asyncio.run(main())
