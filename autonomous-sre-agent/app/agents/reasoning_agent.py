from typing import Any
from app.constants import AgentType
from app.utils.logger import get_logger
from app.llm.llm_client import LLMClient
from app.llm.chains import RCAChain, RemediationPlanChain, RiskAssessmentChain

logger = get_logger(__name__)


class ReasoningAgent:
    def __init__(self, llm_client: LLMClient):
        self.agent_type = AgentType.REASONING
        self.llm_client = llm_client
        self.rca_chain = RCAChain(llm_client)
        self.remediation_chain = RemediationPlanChain(llm_client)
        self.risk_chain = RiskAssessmentChain(llm_client)

    async def run_rca(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Runs LLM-based root cause analysis using metrics, logs, traces, and events context.
        """
        logger.info("reasoning_agent_rca_start")
        try:
            result = await self.rca_chain.run(context)
            logger.info("reasoning_agent_rca_complete", result=result)
            return result
        except Exception as e:
            logger.error("reasoning_agent_rca_failed", error=str(e))
            return {
                "root_cause_category": "unknown",
                "root_cause_description": f"Failed to analyze root cause via LLM reasoning: {e}",
                "confidence": 0.0,
                "contributing_factors": [],
                "recommended_actions": [],
                "requires_human": True,
                "reasoning": str(e),
            }

    async def run_remediation_planning(
        self, rca: dict[str, Any], context: dict[str, Any], runbook: str = ""
    ) -> dict[str, Any]:
        """
        Runs LLM-based remediation planning using root cause, context, and matching runbooks.
        """
        logger.info("reasoning_agent_remediation_planning_start")
        try:
            result = await self.remediation_chain.run(rca, context, runbook=runbook)
            logger.info("reasoning_agent_remediation_planning_complete", result=result)
            return result
        except Exception as e:
            logger.error("reasoning_agent_remediation_planning_failed", error=str(e))
            return {
                "plan_id": "FAILED-PLAN",
                "steps": [],
                "estimated_recovery_time_seconds": 0,
                "risk_level": "critical",
                "rationale": f"LLM remediation planner failed: {e}",
            }

    async def run_risk_assessment(self, plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """
        Runs LLM-based risk assessment on a proposed remediation plan.
        """
        logger.info("reasoning_agent_risk_assessment_start")
        try:
            result = await self.risk_chain.run(plan, context)
            logger.info("reasoning_agent_risk_assessment_complete", result=result)
            return result
        except Exception as e:
            logger.error("reasoning_agent_risk_assessment_failed", error=str(e))
            return {
                "approved": False,
                "risk_level": "critical",
                "risk_factors": [f"Risk assessment agent error: {e}"],
                "concerns": [str(e)],
                "recommendation": "abort",
            }
