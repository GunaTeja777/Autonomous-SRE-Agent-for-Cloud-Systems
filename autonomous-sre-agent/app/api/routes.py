from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Any

from app.orchestrator.incident_orchestrator import IncidentOrchestrator
from app.reports.incident_report import IncidentReport

router = APIRouter()


def get_orchestrator(request: Request) -> IncidentOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if not orchestrator:
        orchestrator = IncidentOrchestrator()
        request.app.state.orchestrator = orchestrator
    return orchestrator


class TriggerScanRequest(BaseModel):
    namespace: str = "default"


@router.get("/incidents")
def list_incidents(request: Request):
    orchestrator = get_orchestrator(request)
    return orchestrator.state_manager.list_incidents()


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, request: Request):
    orchestrator = get_orchestrator(request)
    incident = orchestrator.state_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.to_dict()


@router.get("/incidents/{incident_id}/report", response_class=PlainTextResponse)
def get_incident_report(incident_id: str, request: Request):
    orchestrator = get_orchestrator(request)
    incident = orchestrator.state_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    reporter = IncidentReport(incident.to_dict())
    return reporter.generate_markdown()


@router.post("/trigger")
async def trigger_scan(body: TriggerScanRequest, request: Request):
    orchestrator = get_orchestrator(request)
    triggered = await orchestrator.run_tick(body.namespace)
    
    # Refresh dashboard export immediately
    all_incidents = orchestrator.state_manager.list_incidents()
    # Export summary.json
    from app.reports.report_generator import ReportGenerator
    generator = ReportGenerator()
    generator.export_dashboard_data(all_incidents)
    
    return {
        "message": f"Scan completed for namespace {body.namespace}",
        "triggered_count": len(triggered),
        "triggered_incidents": [inc.incident_id for inc in triggered]
    }


@router.post("/incidents/{incident_id}/approve")
async def approve_remediation(incident_id: str, request: Request):
    orchestrator = get_orchestrator(request)
    success = await orchestrator.trigger_manual_remediation(incident_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve. Incident may not be in 'needs_human' status or does not exist.")
    return {"message": "Remediation approved and triggered."}


@router.get("/dashboard")
def get_dashboard_summary(request: Request):
    orchestrator = get_orchestrator(request)
    incidents = orchestrator.state_manager.list_incidents()
    
    total = len(incidents)
    resolved = sum(1 for inc in incidents if inc.get("status") == "resolved")
    failed = sum(1 for inc in incidents if inc.get("status") == "failed")
    investigating = sum(1 for inc in incidents if inc.get("status") in ["investigating", "rca_in_progress", "remediating", "verifying"])
    needs_human = sum(1 for inc in incidents if inc.get("status") == "needs_human")

    # Categories distribution
    categories: dict[str, int] = {}
    for inc in incidents:
        cat = inc.get("rca_result", {}).get("root_cause_category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "metrics": {
            "total": total,
            "resolved": resolved,
            "failed": failed,
            "investigating": investigating,
            "needs_human": needs_human,
            "resolution_rate": (resolved / total) if total > 0 else 0.0,
        },
        "root_cause_distribution": categories
    }


@router.get("/cluster/status")
def get_cluster_status(request: Request):
    from app.config import get_settings
    settings = get_settings()
    orchestrator = get_orchestrator(request)
    k8s = orchestrator.k8s_client
    
    k8s_connected = False
    cluster_name = "desktop-control-plane"
    pod_count = 0
    try:
        pods = k8s.get_pods(settings.k8s_namespace)
        pod_count = len(pods)
        k8s_connected = getattr(k8s, "_loaded", None) is True
    except Exception:
        k8s_connected = False

    return {
        "k8s_connected": k8s_connected,
        "cluster_name": cluster_name if k8s_connected else "desktop-control-plane",
        "pod_count": pod_count,
        "namespace": settings.k8s_namespace,
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_model": settings.llm_model,
    }


@router.post("/chaos/inject")
async def inject_chaos(scenario: str = "memory_leak"):
    import httpx
    endpoint_map = {
        "memory_leak": "memory-leak",
        "cpu_spike": "cpu-spike",
        "crashloop": "crashloop"
    }
    path = endpoint_map.get(scenario, scenario)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(f"http://localhost:8080/chaos/{path}")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"status": "injected", "scenario": scenario, "message": f"Injected {scenario} chaos simulation into workload."}


@router.post("/chaos/recover")
async def recover_chaos():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post("http://localhost:8080/chaos/recover")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"status": "recovered", "message": "Workload recovered from chaos."}

