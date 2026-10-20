import time
from fastapi import FastAPI, Response
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Payment API Microservice (Chaos Target Workload)")

# In-memory simulated metrics state
state = {
    "pod_name": "payment-api-5c6d9bf84c-xyz89",
    "namespace": "default",
    "cpu_percent": 15.0,
    "memory_bytes": 450 * 1024 * 1024,  # 450 MB (healthy)
    "memory_limit_bytes": 1024 * 1024 * 1024,  # 1 GB
    "restarts": 0,
    "ready": 1,
    "requests_200": 1000,
    "requests_500": 5,
    "chaos_active": "none",
}


@app.get("/health")
def health():
    if state["ready"] == 1:
        return {"status": "healthy", "service": "payment-api", "chaos": state["chaos_active"]}
    return Response(content='{"status": "unhealthy", "reason": "CrashLoopBackOff"}', status_code=500, media_type="application/json")


@app.get("/status")
def status():
    mem_pct = (state["memory_bytes"] / state["memory_limit_bytes"]) * 100.0
    err_rate = state["requests_500"] / max(1, (state["requests_200"] + state["requests_500"]))
    return {
        "service": "payment-api",
        "pod": state["pod_name"],
        "namespace": state["namespace"],
        "chaos_active": state["chaos_active"],
        "metrics": {
            "cpu_percent": state["cpu_percent"],
            "memory_percent": round(mem_pct, 2),
            "restarts": state["restarts"],
            "ready": bool(state["ready"]),
            "error_rate": round(err_rate, 4),
        }
    }


@app.post("/chaos/memory-leak")
def trigger_memory_leak():
    state["chaos_active"] = "memory_leak"
    state["memory_bytes"] = int(0.96 * state["memory_limit_bytes"])  # 96%
    state["restarts"] += 4
    state["ready"] = 0
    print(f"[CHAOS] Triggered Memory Leak! Memory at 96%, OOMKilled cgroup signal emitted. Restarts: {state['restarts']}")
    return {"message": "Memory leak chaos injected. Memory at 96%, pod OOMKilled risk.", "state": state}


@app.post("/chaos/cpu-spike")
def trigger_cpu_spike():
    state["chaos_active"] = "cpu_spike"
    state["cpu_percent"] = 95.5
    print(f"[CHAOS] Triggered CPU Spike! CPU utilization at 95.5%")
    return {"message": "CPU spike chaos injected. CPU at 95.5%.", "state": state}


@app.post("/chaos/error-spike")
def trigger_error_spike():
    state["chaos_active"] = "error_spike"
    state["requests_500"] += 450  # causes error rate > 30%
    print(f"[CHAOS] Triggered HTTP 500 error spike! Error rate > 30%")
    return {"message": "Error spike chaos injected. HTTP error rate > 30%.", "state": state}


@app.post("/chaos/crashloop")
def trigger_crashloop():
    state["chaos_active"] = "crashloop"
    state["ready"] = 0
    state["restarts"] += 8
    print(f"[CHAOS] Triggered CrashLoopBackOff! Pod unready, restarts: {state['restarts']}")
    return {"message": "CrashLoopBackOff chaos injected. Container failing startup.", "state": state}


@app.post("/chaos/recover")
def recover():
    state["chaos_active"] = "none"
    state["cpu_percent"] = 14.5
    state["memory_bytes"] = 420 * 1024 * 1024
    state["ready"] = 1
    state["restarts"] = 0
    state["requests_500"] = 2
    state["requests_200"] = 1200
    print("[CHAOS] System recovered to normal baseline telemetry.")
    return {"message": "System recovered to healthy baseline.", "state": state}


@app.get("/metrics")
def metrics():
    """Exposes Prometheus text exposition format matching SRE PromQL queries."""
    mem_pct = state["memory_bytes"] / state["memory_limit_bytes"]
    cpu_rate = state["cpu_percent"] / 100.0
    lines = [
        "# HELP container_cpu_usage_seconds_total Total CPU time in seconds.",
        "# TYPE container_cpu_usage_seconds_total counter",
        f'container_cpu_usage_seconds_total{{namespace="{state["namespace"]}",pod="{state["pod_name"]}"}} {cpu_rate:.4f}',
        "",
        "# HELP container_memory_working_set_bytes Current memory working set.",
        "# TYPE container_memory_working_set_bytes gauge",
        f'container_memory_working_set_bytes{{namespace="{state["namespace"]}",pod="{state["pod_name"]}"}} {state["memory_bytes"]}',
        "",
        "# HELP node_memory_utilization Node memory utilization percentage.",
        "# TYPE node_memory_utilization gauge",
        f'node_memory_utilization{{node="node-2"}} {mem_pct:.4f}',
        "",
        "# HELP kube_pod_container_status_restarts_total Total restarts.",
        "# TYPE kube_pod_container_status_restarts_total counter",
        f'kube_pod_container_status_restarts_total{{namespace="{state["namespace"]}",pod="{state["pod_name"]}"}} {state["restarts"]}',
        "",
        "# HELP kube_pod_status_ready Pod ready status.",
        "# TYPE kube_pod_status_ready gauge",
        f'kube_pod_status_ready{{namespace="{state["namespace"]}",pod="{state["pod_name"]}"}} {state["ready"]}',
        "",
        "# HELP http_requests_total Total HTTP requests.",
        "# TYPE http_requests_total counter",
        f'http_requests_total{{namespace="{state["namespace"]}",status="200"}} {state["requests_200"]}',
        f'http_requests_total{{namespace="{state["namespace"]}",status="500"}} {state["requests_500"]}',
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4; charset=utf-8")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
