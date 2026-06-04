import pytest
from app.agents.metric_agent import MetricAgent
from app.agents.log_agent import LogAgent
from app.agents.trace_agent import TraceAgent
from app.agents.kubernetes_agent import KubernetesAgent
from app.agents.consensus_agent import ConsensusAgent
from app.constants import RootCauseCategory


@pytest.mark.asyncio
async def test_metric_agent():
    agent = MetricAgent()
    # Test high cpu usage
    metrics = {
        "cpu": [{"metric": {}, "value": [0, "0.95"]}],
        "memory": [{"metric": {}, "value": [0, "0.40"]}],
        "error_rate": [{"metric": {}, "value": [0, "0.01"]}]
    }
    res = await agent.analyze(metrics)
    assert res["root_cause_category"] == RootCauseCategory.RESOURCE_EXHAUSTION.value
    assert res["confidence"] >= 0.80

    # Test high error rate
    metrics_err = {
        "cpu": [{"metric": {}, "value": [0, "0.10"]}],
        "memory": [{"metric": {}, "value": [0, "0.40"]}],
        "error_rate": [{"metric": {}, "value": [0, "0.20"]}]
    }
    res_err = await agent.analyze(metrics_err)
    assert res_err["root_cause_category"] == RootCauseCategory.DEPENDENCY_FAILURE.value


@pytest.mark.asyncio
async def test_log_agent():
    agent = LogAgent()
    # Test OOM logs
    logs = {
        "oom": ["container was OOMKilled"],
        "errors": []
    }
    res = await agent.analyze(logs)
    assert res["root_cause_category"] == RootCauseCategory.MEMORY_LEAK.value

    # Test crashloop logs
    logs_crash = {
        "crashloop": ["Back-off restarting failed container"],
        "errors": []
    }
    res_crash = await agent.analyze(logs_crash)
    assert res_crash["root_cause_category"] == RootCauseCategory.CRASHLOOP.value


@pytest.mark.asyncio
async def test_trace_agent():
    agent = TraceAgent()
    # Test dependency errors
    dep_errors = [{"service": "payment-api", "error_count": 5}]
    res = await agent.analyze(error_traces=[], slow_traces=[], latency_dist={}, dependency_errors=dep_errors)
    assert res["root_cause_category"] == RootCauseCategory.DEPENDENCY_FAILURE.value
    assert "payment-api" in res["root_cause_description"]


@pytest.mark.asyncio
async def test_kubernetes_agent():
    agent = KubernetesAgent()
    
    # Test Pod in CrashLoopBackOff waiting status
    pods = [{
        "name": "api-pod",
        "phase": "Running",
        "restart_count": 6,
        "ready": False,
        "containers": [{
            "name": "api",
            "ready": False,
            "restart_count": 6,
            "state": {"status": "waiting", "reason": "CrashLoopBackOff", "message": "back-off restarting failed container"}
        }]
    }]
    events = []
    res = await agent.analyze(pods, events)
    assert res["root_cause_category"] == RootCauseCategory.CRASHLOOP.value


@pytest.mark.asyncio
async def test_consensus_agent():
    agent = ConsensusAgent(llm_client=None)
    
    findings = [
        {"agent_type": "metric_agent", "root_cause_category": "memory_leak", "root_cause_description": "high mem", "confidence": 0.90},
        {"agent_type": "log_agent", "root_cause_category": "memory_leak", "root_cause_description": "oom logs", "confidence": 0.95},
        {"agent_type": "trace_agent", "root_cause_category": "memory_leak", "root_cause_description": "slow database", "confidence": 0.88}
    ]
    res = await agent.run(findings)
    assert res["root_cause_category"] == "memory_leak"
    assert res["confidence"] == 0.91  # average of 90%, 95%, 88% is 91%
    assert res["agreement_level"] == "full"
