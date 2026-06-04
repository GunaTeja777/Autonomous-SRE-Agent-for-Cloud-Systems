import uuid
from typing import Any
from app.constants import RootCauseCategory, RemediationAction, RiskLevel
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Planner:
    def __init__(self, reasoning_agent=None):
        self.reasoning_agent = reasoning_agent

    async def generate_plan(
        self, consensus: dict[str, Any], context: dict[str, Any], runbook_content: str = ""
    ) -> dict[str, Any]:
        """
        Generates a remediation plan. Prefers LLM reasoning agent if available,
        otherwise falls back to rule-based generation.
        """
        logger.info("remediation_planner_started", category=consensus.get("root_cause_category"))

        # 1. Try LLM Planning if reasoning agent is available and not using mock LLM client
        if self.reasoning_agent and self.reasoning_agent.llm_client._get_client() != "mock":
            try:
                llm_plan = await self.reasoning_agent.run_remediation_planning(
                    consensus, context, runbook=runbook_content
                )
                if llm_plan.get("steps"):
                    logger.info("remediation_planner_llm_success", plan_id=llm_plan.get("plan_id"))
                    return llm_plan
            except Exception as e:
                logger.warning("remediation_planner_llm_failed_falling_back", error=str(e))

        # 2. Rule-based Fallback Planner
        category = consensus.get("root_cause_category", RootCauseCategory.UNKNOWN.value)
        pod = context.get("pod", "unknown")
        namespace = context.get("namespace", "default")
        
        # Derive deployment name from pod (e.g. api-85b4f65d-x2k4y -> api)
        deployment_name = pod.split("-")[0] if "-" in pod else pod
        if "-" in pod:
            parts = pod.split("-")
            # If standard deployment naming (e.g. name-replicaset-podhash), drop last two segments
            if len(parts) >= 3 and len(parts[-1]) == 5 and len(parts[-2]) > 5:
                deployment_name = "-".join(parts[:-2])
            elif len(parts) >= 2:
                deployment_name = "-".join(parts[:-1])

        plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
        steps = []
        estimated_time = 60
        risk_level = RiskLevel.LOW
        rationale = f"Rule-based plan for root cause '{category}'"

        if category in [RootCauseCategory.MEMORY_LEAK.value, RootCauseCategory.RESOURCE_EXHAUSTION.value]:
            steps.append({
                "step": 1,
                "action": RemediationAction.SCALE_DEPLOYMENT.value,
                "target": deployment_name,
                "params": {"replicas": 5, "namespace": namespace, "previous_replicas": 2},
                "description": f"Scale up deployment '{deployment_name}' to 5 replicas to distribute resource load.",
                "rollback_action": RemediationAction.SCALE_DEPLOYMENT.value,
            })
            estimated_time = 120
            risk_level = RiskLevel.MEDIUM
            rationale = "Scaling deployment adds horizontal capacity to handle spikes and alleviate memory leaks temporarily."

        elif category == RootCauseCategory.CRASHLOOP.value:
            steps.append({
                "step": 1,
                "action": RemediationAction.RESTART_POD.value,
                "target": pod,
                "params": {"namespace": namespace},
                "description": f"Restart pod '{pod}' to attempt recovery from crash loop state.",
                "rollback_action": RemediationAction.NO_ACTION.value,
            })
            estimated_time = 60
            risk_level = RiskLevel.LOW
            rationale = "Restarting the pod is the first line of defense for crash looping container issues."

        elif category == RootCauseCategory.IMAGE_PULL.value:
            steps.append({
                "step": 1,
                "action": RemediationAction.ROLLBACK_DEPLOYMENT.value,
                "target": deployment_name,
                "params": {"namespace": namespace},
                "description": f"Rollback deployment '{deployment_name}' to the previous stable image revision.",
                "rollback_action": RemediationAction.NO_ACTION.value,
            })
            estimated_time = 90
            risk_level = RiskLevel.HIGH
            rationale = "Rolling back deployment recovers service from invalid or missing container image tags."

        elif category == RootCauseCategory.CONFIG_ERROR.value:
            steps.append({
                "step": 1,
                "action": RemediationAction.ROLLBACK_DEPLOYMENT.value,
                "target": deployment_name,
                "params": {"namespace": namespace},
                "description": f"Rollback deployment '{deployment_name}' to undo recent config change.",
                "rollback_action": RemediationAction.NO_ACTION.value,
            })
            estimated_time = 90
            risk_level = RiskLevel.HIGH
            rationale = "Rollback is the safest recovery step for deployment configuration failures."

        elif category == RootCauseCategory.NODE_FAILURE.value:
            # We need to find the node name from context
            node_name = context.get("node", "unknown")
            steps.append({
                "step": 1,
                "action": RemediationAction.CORDON_NODE.value,
                "target": node_name,
                "params": {},
                "description": f"Cordon failing node '{node_name}' to prevent scheduling new workloads.",
                "rollback_action": RemediationAction.NO_ACTION.value, # Uncordon is complex, do manually
            })
            estimated_time = 30
            risk_level = RiskLevel.CRITICAL
            rationale = "Cordoning nodes keeps critical containers away from hardware or host kernel faults."

        else:
            # Unknown or Network/Dependency issues
            steps.append({
                "step": 1,
                "action": RemediationAction.NO_ACTION.value,
                "target": pod,
                "params": {},
                "description": "No safe automated action can be generated. Monitor state and await human analysis.",
                "rollback_action": RemediationAction.NO_ACTION.value,
            })
            estimated_time = 0
            risk_level = RiskLevel.LOW
            rationale = "No automatic remedy exists for unknown or dependency issues; human SRE needs to inspect logs."

        plan = {
            "plan_id": plan_id,
            "steps": steps,
            "estimated_recovery_time_seconds": estimated_time,
            "risk_level": risk_level.value,
            "rationale": rationale,
        }
        logger.info("remediation_planner_completed", plan_id=plan_id)
        return plan
