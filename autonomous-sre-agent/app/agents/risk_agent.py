from typing import Any
from app.constants import RiskLevel, AgentType, RemediationAction
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RiskAgent:
    def __init__(self):
        self.agent_type = AgentType.RISK
        self.settings = get_settings()

    async def assess_risk(self, plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """
        Assess risk levels programmatically and determine if the plan is safe for automatic execution.
        """
        logger.info("risk_agent_assessment_start", plan_id=plan.get("plan_id"))

        risk_level = RiskLevel.LOW
        approved = True
        risk_factors = []
        concerns = []

        steps = plan.get("steps", [])
        if not steps:
            return {
                "agent_type": self.agent_type.value,
                "approved": False,
                "risk_level": RiskLevel.CRITICAL.value,
                "risk_factors": ["Empty remediation plan"],
                "concerns": ["No steps defined in the proposed plan."],
                "recommendation": "abort",
            }

        # 1. Evaluate steps risk
        for step in steps:
            action = step.get("action")
            target = step.get("target")

            if action in [RemediationAction.DRAIN_NODE.value, RemediationAction.CORDON_NODE.value]:
                risk_level = RiskLevel.CRITICAL
                risk_factors.append(f"Action '{action}' on node '{target}' affects infrastructure layer.")
                concerns.append("Draining/Cordoning nodes may impact other application workloads.")
            elif action in [RemediationAction.ROLLBACK_DEPLOYMENT.value, RemediationAction.UPDATE_CONFIG.value]:
                if risk_level != RiskLevel.CRITICAL:
                    risk_level = RiskLevel.HIGH
                risk_factors.append(f"Action '{action}' modifies application release version or configuration.")
            elif action in [RemediationAction.SCALE_DEPLOYMENT.value, RemediationAction.PATCH_DEPLOYMENT.value]:
                if risk_level not in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    risk_level = RiskLevel.MEDIUM
                risk_factors.append(f"Action '{action}' modifies pod count or attributes.")
            elif action in [RemediationAction.RESTART_POD.value, RemediationAction.DELETE_POD.value]:
                if risk_level not in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    risk_level = RiskLevel.LOW
                risk_factors.append(f"Action '{action}' on pod '{target}' is low impact (pod lifecycle).")

        # 2. Check risk against config threshold
        risk_thresholds = {
            RiskLevel.LOW.value: 1,
            RiskLevel.MEDIUM.value: 2,
            RiskLevel.HIGH.value: 3,
            RiskLevel.CRITICAL.value: 4,
        }

        configured_limit = risk_thresholds.get(self.settings.risk_threshold, 2)
        current_risk_val = risk_thresholds.get(risk_level.value, 1)

        # 3. Check environment safety
        if self.settings.environment.lower() == "production" and current_risk_val >= 3:
            approved = False
            concerns.append("Cannot auto-remediate High/Critical risks in Production environments.")

        # 4. Check settings auto_remediate / dry_run
        if self.settings.dry_run:
            approved = False
            concerns.append("Dry Run mode is enabled. No remediation actions will be actually executed.")
        elif not self.settings.auto_remediate:
            approved = False
            concerns.append("Auto-remediate is disabled. Awaiting SRE manual confirmation.")

        # 5. Check confidence levels if passed in context
        confidence = context.get("confidence", 1.0)
        if confidence < self.settings.remediation_confidence_threshold:
            approved = False
            concerns.append(
                f"Consensus confidence {confidence:.2f} is below safety threshold {self.settings.remediation_confidence_threshold:.2f}."
            )

        if current_risk_val > configured_limit:
            approved = False
            concerns.append(
                f"Proposed risk level '{risk_level.value}' exceeds configured safety threshold limit '{self.settings.risk_threshold}'."
            )

        recommendation = "proceed" if approved else ("human_review" if not self.settings.dry_run else "abort")

        result = {
            "agent_type": self.agent_type.value,
            "approved": approved,
            "risk_level": risk_level.value,
            "risk_factors": risk_factors,
            "concerns": concerns,
            "recommendation": recommendation,
        }
        logger.info("risk_agent_assessment_complete", result=result)
        return result
