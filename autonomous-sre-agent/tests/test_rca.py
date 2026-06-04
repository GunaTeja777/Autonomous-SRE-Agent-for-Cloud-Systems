import pytest
from unittest.mock import AsyncMock, MagicMock
from app.rca.root_cause_engine import RootCauseEngine
from app.agents.consensus_agent import ConsensusAgent
from app.constants import RootCauseCategory


@pytest.mark.asyncio
async def test_root_cause_engine():
    # Mock clients
    mock_prom = MagicMock()
    mock_prom.get_all_metrics_for_namespace = AsyncMock(return_value={
        "cpu": [{"metric": {}, "value": [0, "0.95"]}],
        "memory": [],
        "error_rate": []
    })
    
    mock_loki = MagicMock()
    mock_loki.get_all_logs_for_incident = AsyncMock(return_value={})
    
    mock_tracing = MagicMock()
    mock_tracing.get_services = AsyncMock(return_value=["api"])
    mock_tracing.get_error_traces = AsyncMock(return_value=[])
    mock_tracing.get_slow_traces = AsyncMock(return_value=[])
    mock_tracing.analyze_latency_distribution = AsyncMock(return_value={})
    mock_tracing.get_dependency_errors = AsyncMock(return_value=[])

    mock_k8s = MagicMock()
    mock_k8s.get_pods = MagicMock(return_value=[])
    mock_k8s.get_events = MagicMock(return_value=[])

    # Consensus Agent
    consensus = ConsensusAgent(llm_client=None)

    engine = RootCauseEngine(
        prometheus=mock_prom,
        loki=mock_loki,
        tracing=mock_tracing,
        k8s=mock_k8s,
        consensus=consensus
    )

    res = await engine.analyze_incident(namespace="default", pod="api-12345")
    assert res["root_cause_category"] == RootCauseCategory.RESOURCE_EXHAUSTION.value
    assert res["confidence"] == 0.85
    assert "metric_agent" in res["agent_findings"]
