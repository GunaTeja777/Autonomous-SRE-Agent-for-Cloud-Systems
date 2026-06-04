import asyncio
from typing import Any

from app.constants import IncidentStatus, IncidentSeverity
from app.orchestrator.state_manager import IncidentState
from app.rca.root_cause_engine import RootCauseEngine
from app.agents.reasoning_agent import ReasoningAgent
from app.remediation.planner import Planner
from app.agents.risk_agent import RiskAgent
from app.remediation.executor import RemediationExecutor
from app.agents.verification_agent import VerificationAgent
from app.memory.incident_memory import IncidentMemory
from app.runbooks.retriever import RunbookRetriever
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowManager:
    def __init__(
        self,
        rca_engine: RootCauseEngine,
        reasoning_agent: ReasoningAgent,
        planner: Planner,
        risk_agent: RiskAgent,
        executor: RemediationExecutor,
        verification_agent: VerificationAgent,
        memory: IncidentMemory,
        runbook_retriever: RunbookRetriever,
    ):
        self.rca_engine = rca_engine
        self.reasoning_agent = reasoning_agent
        self.planner = planner
        self.risk_agent = risk_agent
        self.executor = executor
        self.verification_agent = verification_agent
        self.memory = memory
        self.runbook_retriever = runbook_retriever

    async def execute_incident_workflow(self, incident: IncidentState) -> None:
        """
        Executes the autonomous SRE lifecycle workflow for an active incident:
        Investigation -> RCA -> Retrieval -> Reasoning -> Remediation Planning -> Risk Assessment -> Execution -> Verification.
        """
        logger.info("workflow_workflow_manager_started", id=incident.incident_id)

        try:
            # 1. RCA Stage (Specialist agents + consensus)
            incident.transition(IncidentStatus.INVESTIGATING)
            rca_result = await self.rca_engine.analyze_incident(incident.namespace, incident.pod)
            incident.rca_result = rca_result

            # 2. Retrieval Stage (Past incidents + runbooks)
            category = rca_result.get("root_cause_category", "unknown")
            query = f"{category} {rca_result.get('root_cause_description', '')}"

            past_incidents = self.memory.query_similar_incidents(query, limit=3)
            logger.info("workflow_past_incidents_retrieved", count=len(past_incidents))

            runbooks = self.runbook_retriever.retrieve_for_incident({
                "root_cause_category": category,
                "root_cause_description": rca_result.get("root_cause_description"),
                "anomaly_signals": incident.anomaly_report.get("signals", [])
            })
            runbook_content = runbooks[0].get("full_text", "") if runbooks else ""
            logger.info("workflow_runbooks_retrieved", count=len(runbooks))

            # 3. LLM Deep Reasoning Stage
            incident.transition(IncidentStatus.RCA_IN_PROGRESS)
            context = {
                "namespace": incident.namespace,
                "pod": incident.pod,
                "incident_id": incident.incident_id,
                "detected_at": incident.detected_at,
                "metrics": rca_result.get("collected_data", {}).get("metrics_summary", {}),
                "k8s_state": {"pods": rca_result.get("collected_data", {}).get("pods_count", 0)},
                "logs": rca_result.get("collected_data", {}).get("logs_summary", {}),
                "traces": {"traces_count": rca_result.get("collected_data", {}).get("traces_count", 0)},
                "anomaly_signals": incident.anomaly_report.get("signals", []),
                "past_incidents": past_incidents,
            }

            llm_rca = await self.reasoning_agent.run_rca(context)
            # Reconcile consensus with LLM reasoning (LLM takes precedence if high confidence)
            final_rca = rca_result
            if llm_rca.get("confidence", 0.0) >= rca_result.get("confidence", 0.0):
                final_rca = {
                    "root_cause_category": llm_rca.get("root_cause_category"),
                    "root_cause_description": llm_rca.get("root_cause_description"),
                    "confidence": llm_rca.get("confidence"),
                    "reasoning": llm_rca.get("reasoning"),
                    "agent_findings": rca_result.get("agent_findings"),
                }
                incident.rca_result = final_rca
                logger.info("workflow_llm_rca_selected_over_consensus")

            # 4. Remediation Planning
            remediation_plan = await self.planner.generate_plan(final_rca, context, runbook_content=runbook_content)
            incident.remediation_plan = remediation_plan

            # 5. Risk Assessment (Programmatic + LLM if available)
            if not incident.risk_assessment.get("approved", False):
                risk_context = {
                    "confidence": final_rca.get("confidence", 0.0),
                    "recent_incident_count": 0, # Could retrieve from state_manager
                    "service_criticality": "medium"
                }
                risk_assessment = await self.risk_agent.assess_risk(remediation_plan, risk_context)
                incident.risk_assessment = risk_assessment

            if not incident.risk_assessment.get("approved", False):
                incident.error_message = f"Risk assessment rejected remediation action. Reason: {', '.join(incident.risk_assessment.get('concerns', []))}"
                incident.transition(IncidentStatus.NEEDS_HUMAN)
                logger.warning("workflow_remediation_aborted_by_risk_assessment", reason=incident.error_message)
                return

            # 6. Remediation Execution
            incident.transition(IncidentStatus.REMEDIATING)
            execution_out = await self.executor.execute_plan(remediation_plan)
            incident.execution_result = execution_out

            if not execution_out.get("success", False):
                incident.error_message = f"Remediation steps execution failed: {execution_out.get('message')}"
                incident.transition(IncidentStatus.FAILED)
                logger.error("workflow_execution_failed", error=incident.error_message)
                return

            # Summarize action applied
            steps_desc = [s.get("description") for s in execution_out.get("executed_steps", [])]
            incident.remediation_summary = "; ".join(steps_desc)

            # 7. Verification Stage (wait a brief cooldown period for systems to recover)
            incident.transition(IncidentStatus.VERIFYING)
            cooldown_seconds = remediation_plan.get("estimated_recovery_time_seconds", 30)
            logger.info("workflow_waiting_cooldown", seconds=cooldown_seconds)
            await asyncio.sleep(min(cooldown_seconds, 15)) # limit sleep in test execution

            # Gather post-remediation data
            post_metrics = await self.rca_engine.prometheus.get_all_metrics_for_namespace(incident.namespace, incident.pod)
            post_pods = await asyncio.to_thread(self.rca_engine.k8s.get_pods, incident.namespace)
            post_logs = await self.rca_engine.loki.get_all_logs_for_incident(incident.namespace, incident.pod)

            post_state = {
                "metrics": post_metrics,
                "k8s_state": {"pods": post_pods},
                "logs": post_logs,
            }

            verification_out = await self.verification_agent.verify(incident.to_dict(), post_state)
            incident.verification_result = verification_out

            # 8. Resolution Decision
            if verification_out.get("resolved", False):
                incident.transition(IncidentStatus.RESOLVED)
                logger.info("workflow_incident_resolved_successfully")
                
                # Save incident to vector memory for future ChatGPT-style recall
                self.memory.store_incident(
                    incident.incident_id,
                    incident.to_dict(),
                    final_rca,
                    remediation_plan,
                    verification_out
                )
            else:
                incident.error_message = f"Post-remediation verification failed. Concerns: {', '.join(verification_out.get('remaining_issues', []))}"
                logger.warning("workflow_verification_failed_triggering_rollback", reason=incident.error_message)
                
                # Undo actions
                rollback_ok = await self.executor.trigger_rollback()
                if rollback_ok:
                    incident.transition(IncidentStatus.NEEDS_HUMAN)
                else:
                    incident.transition(IncidentStatus.FAILED)

        except Exception as e:
            incident.error_message = f"Workflow execution unhandled exception: {e}"
            incident.transition(IncidentStatus.FAILED)
            logger.error("workflow_execution_failed_exception", error=str(e))
            raise e
