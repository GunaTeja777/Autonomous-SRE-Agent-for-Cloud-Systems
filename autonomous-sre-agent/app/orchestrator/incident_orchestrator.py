import asyncio
from typing import Any

from app.monitoring.kubernetes_client import KubernetesClient
from app.monitoring.prometheus_client import PrometheusClient
from app.monitoring.loki_client import LokiClient
from app.monitoring.tracing_client import TracingClient

from app.anomaly_detection.detector import AnomalyDetector
from app.rca.root_cause_engine import RootCauseEngine
from app.rca.incident_classifier import IncidentClassifier

from app.llm.llm_client import LLMClient
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.consensus_agent import ConsensusAgent
from app.agents.risk_agent import RiskAgent
from app.agents.verification_agent import VerificationAgent

from app.remediation.planner import Planner
from app.remediation.kubectl_actions import KubectlActions
from app.remediation.sandbox_validator import SandboxValidator
from app.remediation.executor import RemediationExecutor

from app.memory.vector_store import VectorStore
from app.memory.incident_memory import IncidentMemory
from app.runbooks.runbook_loader import RunbookLoader
from app.runbooks.retriever import RunbookRetriever

from app.orchestrator.state_manager import StateManager, IncidentState
from app.orchestrator.workflow_manager import WorkflowManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IncidentOrchestrator:
    def __init__(self):
        logger.info("orchestrator_initializing")
        
        # 1. Core Clients
        self.k8s_client = KubernetesClient()
        self.prometheus_client = PrometheusClient()
        self.loki_client = LokiClient()
        self.tracing_client = TracingClient()
        self.llm_client = LLMClient()
        
        # 2. Memory & Runbooks
        self.vector_store = VectorStore()
        self.incident_memory = IncidentMemory(self.vector_store)
        self.runbook_loader = RunbookLoader(self.vector_store)
        self.runbook_retriever = RunbookRetriever(self.vector_store, self.runbook_loader)
        
        # Load all runbooks into VectorStore on startup
        self.runbook_loader.load_all()

        # 3. Anomaly & RCA
        self.anomaly_detector = AnomalyDetector()
        self.incident_classifier = IncidentClassifier()
        
        self.consensus_agent = ConsensusAgent(self.llm_client)
        self.rca_engine = RootCauseEngine(
            prometheus=self.prometheus_client,
            loki=self.loki_client,
            tracing=self.tracing_client,
            k8s=self.k8s_client,
            consensus=self.consensus_agent
        )

        # 4. Remediation & Verification
        self.reasoning_agent = ReasoningAgent(self.llm_client)
        self.planner = Planner(self.reasoning_agent)
        self.risk_agent = RiskAgent()
        
        self.kubectl_actions = KubectlActions(self.k8s_client)
        self.sandbox_validator = SandboxValidator(self.k8s_client)
        self.executor = RemediationExecutor(self.kubectl_actions, self.sandbox_validator)
        
        self.verification_agent = VerificationAgent(self.llm_client)
        
        # 5. Workflow & State
        self.state_manager = StateManager()
        self.workflow_manager = WorkflowManager(
            rca_engine=self.rca_engine,
            reasoning_agent=self.reasoning_agent,
            planner=self.planner,
            risk_agent=self.risk_agent,
            executor=self.executor,
            verification_agent=self.verification_agent,
            memory=self.incident_memory,
            runbook_retriever=self.runbook_retriever
        )
        
        # Keep track of active background workflow tasks
        self._active_tasks: dict[str, asyncio.Task] = {}
        logger.info("orchestrator_initialized_successfully")

    async def run_tick(self, namespace: str) -> list[IncidentState]:
        """
        Runs a single SRE monitoring loop tick in a namespace.
        Collects metrics/logs, detects anomalies, and triggers SRE workflows.
        """
        logger.info("orchestrator_tick_start", namespace=namespace)
        triggered_incidents = []

        try:
            # Get all pods in namespace to scan
            pods = self.k8s_client.get_pods(namespace=namespace)
        except Exception as e:
            logger.error("orchestrator_failed_to_list_pods", namespace=namespace, error=str(e))
            return []

        for p in pods:
            pod_name = p["name"]
            
            # Check if there is already an unresolved incident running for this pod
            active_incident_exists = False
            for inc in self.state_manager.list_incidents():
                if inc["pod"] == pod_name and inc["status"] not in ["resolved", "failed", "needs_human"]:
                    active_incident_exists = True
                    break
            
            if active_incident_exists:
                continue

            try:
                # 1. Fetch metrics & logs for anomaly detector check
                metrics = await self.prometheus_client.get_all_metrics_for_namespace(namespace, pod_name)
                logs = await self.loki_client.get_all_logs_for_incident(namespace, pod_name)

                # 2. Run Anomaly Detection
                report = await self.anomaly_detector.detect(metrics, logs)
                if report.get("anomaly", False):
                    logger.warning("orchestrator_anomaly_detected", pod=pod_name, signals=report.get("signals"))
                    
                    # Classify incident severity and target
                    classification = self.incident_classifier.classify(report)
                    
                    # Create new incident state
                    incident = self.state_manager.create_incident(
                        namespace=namespace,
                        pod=pod_name,
                        severity=classification["severity"]
                    )
                    incident.anomaly_report = report
                    
                    # Trigger workflow in the background asynchronously
                    task = asyncio.create_task(self.workflow_manager.execute_incident_workflow(incident))
                    self._active_tasks[incident.incident_id] = task
                    
                    # Cleanup task from active list when done
                    task.add_done_callback(lambda t, i_id=incident.incident_id: self._active_tasks.pop(i_id, None))
                    
                    triggered_incidents.append(incident)
            except Exception as e:
                logger.error("orchestrator_pod_scan_failed", pod=pod_name, error=str(e))

        logger.info("orchestrator_tick_completed", triggered_count=len(triggered_incidents))
        return triggered_incidents

    async def trigger_manual_remediation(self, incident_id: str) -> bool:
        """
        API to allow human SRE to manually approve and trigger remediation steps.
        Used when the risk assessment is rejected/marked as needs_human.
        """
        incident = self.state_manager.get_incident(incident_id)
        if not incident:
            logger.warning("orchestrator_manual_remediation_incident_not_found", id=incident_id)
            return False

        if incident.status != "needs_human":
            logger.warning("orchestrator_manual_remediation_invalid_status", id=incident_id, status=incident.status)
            return False

        logger.info("orchestrator_manual_remediation_approved", id=incident_id)
        
        # Override risk assessment approval and rerun the remediation + verification pipeline in background
        incident.risk_assessment["approved"] = True
        task = asyncio.create_task(self.workflow_manager.execute_incident_workflow(incident))
        self._active_tasks[incident.incident_id] = task
        task.add_done_callback(lambda t, i_id=incident.incident_id: self._active_tasks.pop(i_id, None))
        
        return True
