import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.orchestrator.state_manager import StateManager
from app.orchestrator.workflow_manager import WorkflowManager
from app.orchestrator.incident_orchestrator import IncidentOrchestrator
from app.constants import IncidentStatus, IncidentSeverity


@pytest.mark.asyncio
async def test_workflow_execution():
    # Mock all necessary components
    mock_rca = MagicMock()
    mock_rca.analyze_incident = AsyncMock(return_value={
        "root_cause_category": "memory_leak",
        "root_cause_description": "pod memory leak",
        "confidence": 0.90,
        "collected_data": {"metrics_summary": {}, "logs_summary": {}, "pods_count": 1, "events_count": 0, "traces_count": 0}
    })

    mock_reasoning = MagicMock()
    # Mock client and return value
    mock_reasoning.llm_client._get_client = MagicMock(return_value="mock")
    mock_reasoning.run_rca = AsyncMock(return_value={
        "root_cause_category": "memory_leak",
        "root_cause_description": "pod memory leak",
        "confidence": 0.91,
        "reasoning": "OOM detected"
    })

    mock_planner = MagicMock()
    mock_planner.generate_plan = AsyncMock(return_value={
        "plan_id": "PLAN-1",
        "steps": [{"step": 1, "action": "scale_deployment", "target": "api", "params": {"replicas": 3}}],
        "estimated_recovery_time_seconds": 10,
        "risk_level": "medium"
    })

    mock_risk = MagicMock()
    mock_risk.assess_risk = AsyncMock(return_value={"approved": True, "risk_level": "medium"})

    mock_executor = MagicMock()
    mock_executor.execute_plan = AsyncMock(return_value={"success": True, "executed_steps": [{"description": "Scaled deployment api to 3"}]})
    mock_executor.trigger_rollback = AsyncMock(return_value=True)

    mock_verification = MagicMock()
    mock_verification.verify = AsyncMock(return_value={"resolved": True, "confidence": 0.95, "evidence": ["metrics recovered"]})

    mock_memory = MagicMock()
    mock_memory.query_similar_incidents = MagicMock(return_value=[])
    mock_memory.store_incident = MagicMock()

    mock_retriever = MagicMock()
    mock_retriever.retrieve_for_incident = MagicMock(return_value=[])

    workflow = WorkflowManager(
        rca_engine=mock_rca,
        reasoning_agent=mock_reasoning,
        planner=mock_planner,
        risk_agent=mock_risk,
        executor=mock_executor,
        verification_agent=mock_verification,
        memory=mock_memory,
        runbook_retriever=mock_retriever
    )

    state_mgr = StateManager()
    incident = state_mgr.create_incident("default", "api-pod", IncidentSeverity.HIGH)
    incident.anomaly_report = {"signals": ["CPU threshold exceeded"]}

    await workflow.execute_incident_workflow(incident)
    
    assert incident.status == IncidentStatus.RESOLVED
    assert incident.remediation_summary == "Scaled deployment api to 3"
    mock_memory.store_incident.assert_called_once()
