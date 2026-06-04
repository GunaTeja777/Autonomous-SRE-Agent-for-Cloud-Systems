import pytest
from unittest.mock import MagicMock, AsyncMock
from app.remediation.planner import Planner
from app.remediation.sandbox_validator import SandboxValidator
from app.remediation.kubectl_actions import KubectlActions
from app.remediation.executor import RemediationExecutor
from app.constants import RootCauseCategory, RemediationAction, RiskLevel


@pytest.mark.asyncio
async def test_remediation_planner():
    planner = Planner(reasoning_agent=None)
    consensus = {"root_cause_category": RootCauseCategory.CRASHLOOP.value}
    context = {"pod": "api-12345-xyz", "namespace": "default"}
    
    plan = await planner.generate_plan(consensus, context)
    assert plan["risk_level"] == RiskLevel.LOW.value
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["action"] == RemediationAction.RESTART_POD.value
    assert plan["steps"][0]["target"] == "api-12345-xyz"


@pytest.mark.asyncio
async def test_sandbox_validator():
    mock_k8s = MagicMock()
    mock_k8s.get_pods = MagicMock(return_value=[{"name": "api-123"}])
    
    validator = SandboxValidator(mock_k8s)
    
    # Valid pod target
    valid, reason = await validator.validate(RemediationAction.RESTART_POD.value, "api-123", {"namespace": "default"})
    assert valid is True

    # Invalid pod target
    valid_invalid, reason_invalid = await validator.validate(RemediationAction.RESTART_POD.value, "other-pod", {"namespace": "default"})
    assert valid_invalid is False
    assert "not found" in reason_invalid


@pytest.mark.asyncio
async def test_remediation_executor():
    mock_k8s = MagicMock()
    mock_k8s.restart_pod = MagicMock(return_value=True)
    mock_k8s.get_pods = MagicMock(return_value=[{"name": "api-123"}])
    
    actions = KubectlActions(mock_k8s)
    validator = SandboxValidator(mock_k8s)
    executor = RemediationExecutor(actions, validator)

    plan = {
        "plan_id": "PLAN-1",
        "steps": [
            {
                "step": 1,
                "action": RemediationAction.RESTART_POD.value,
                "target": "api-123",
                "params": {"namespace": "default"},
                "rollback_action": RemediationAction.NO_ACTION.value
            }
        ]
    }

    res = await executor.execute_plan(plan)
    assert res["success"] is True
    assert len(res["executed_steps"]) == 1
    mock_k8s.restart_pod.assert_called_once_with("api-123", namespace="default")
