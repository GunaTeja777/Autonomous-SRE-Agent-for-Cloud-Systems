import json
from typing import Any
from app.llm.llm_client import LLMClient
from app.llm.prompts import (
    RCA_SYSTEM_PROMPT, RCA_USER_PROMPT,
    REMEDIATION_PLAN_SYSTEM, REMEDIATION_PLAN_USER,
    RISK_ASSESSMENT_SYSTEM, RISK_ASSESSMENT_USER,
    VERIFICATION_SYSTEM, VERIFICATION_USER,
    CONSENSUS_SYSTEM, CONSENSUS_USER,
)
from app.llm.output_parser import (
    parse_rca_response, parse_remediation_plan,
    parse_risk_assessment, parse_verification_result,
    parse_consensus_result,
)
from app.utils.helpers import truncate_text, utcnow_iso
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RCAChain:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        user = RCA_USER_PROMPT.format(
            namespace=context.get("namespace", "unknown"),
            pod=context.get("pod", "unknown"),
            incident_id=context.get("incident_id", ""),
            detected_at=context.get("detected_at", utcnow_iso()),
            metrics_summary=truncate_text(json.dumps(context.get("metrics", {}), indent=2), 1500),
            k8s_summary=truncate_text(json.dumps(context.get("k8s_state", {}), indent=2), 1000),
            log_summary=truncate_text("\n".join(context.get("logs", {}).get("errors", [])[:20]), 800),
            trace_summary=truncate_text(json.dumps(context.get("traces", {}), indent=2), 500),
            anomaly_signals="\n".join(context.get("anomaly_signals", [])),
        )
        raw = await self.llm.acomplete(RCA_SYSTEM_PROMPT, user)
        return parse_rca_response(raw)


class RemediationPlanChain:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, rca: dict[str, Any], context: dict[str, Any], runbook: str = "") -> dict[str, Any]:
        from app.constants import RemediationAction
        available = [a.value for a in RemediationAction]
        user = REMEDIATION_PLAN_USER.format(
            root_cause_category=rca.get("root_cause_category", "unknown"),
            root_cause_description=rca.get("root_cause_description", ""),
            confidence=rca.get("confidence", 0.0),
            namespace=context.get("namespace", "default"),
            resource_name=context.get("pod", "unknown"),
            available_actions=", ".join(available),
            runbook_content=truncate_text(runbook, 1000),
        )
        raw = await self.llm.acomplete(REMEDIATION_PLAN_SYSTEM, user)
        return parse_remediation_plan(raw)


class RiskAssessmentChain:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        from app.config import get_settings
        settings = get_settings()
        user = RISK_ASSESSMENT_USER.format(
            plan_json=json.dumps(plan, indent=2),
            environment=settings.environment,
            auto_remediate=settings.auto_remediate,
            current_time=utcnow_iso(),
            recent_incident_count=context.get("recent_incident_count", 0),
            service_criticality=context.get("service_criticality", "unknown"),
        )
        raw = await self.llm.acomplete(RISK_ASSESSMENT_SYSTEM, user)
        return parse_risk_assessment(raw)


class VerificationChain:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, incident: dict[str, Any], post_state: dict[str, Any]) -> dict[str, Any]:
        user = VERIFICATION_USER.format(
            incident_id=incident.get("incident_id", ""),
            root_cause=incident.get("root_cause_description", ""),
            remediation_summary=incident.get("remediation_summary", ""),
            post_metrics=truncate_text(json.dumps(post_state.get("metrics", {}), indent=2), 800),
            post_k8s=truncate_text(json.dumps(post_state.get("k8s_state", {}), indent=2), 600),
            post_logs=truncate_text("\n".join(post_state.get("logs", [])[:10]), 400),
        )
        raw = await self.llm.acomplete(VERIFICATION_SYSTEM, user)
        return parse_verification_result(raw)


class ConsensusChain:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, agent_findings: list[dict[str, Any]]) -> dict[str, Any]:
        # Detect conflicts
        categories = [f.get("root_cause_category", "unknown") for f in agent_findings]
        conflicts = []
        if len(set(categories)) > 1:
            conflicts.append(f"Agents disagree on root cause category: {set(categories)}")

        user = CONSENSUS_USER.format(
            agent_findings=json.dumps(agent_findings, indent=2),
            conflicts="\n".join(conflicts) if conflicts else "No conflicts detected.",
        )
        raw = await self.llm.acomplete(CONSENSUS_SYSTEM, user)
        return parse_consensus_result(raw)