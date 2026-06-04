from typing import Any
from app.constants import IncidentStatus, IncidentSeverity
from app.utils.logger import get_logger
from app.utils.helpers import utcnow_iso, generate_incident_id

logger = get_logger(__name__)


class IncidentState:
    def __init__(self, incident_id: str, namespace: str, pod: str, severity: IncidentSeverity = IncidentSeverity.MEDIUM):
        self.incident_id = incident_id
        self.namespace = namespace
        self.pod = pod
        self.severity = severity
        self.status = IncidentStatus.DETECTING
        self.detected_at = utcnow_iso()
        self.updated_at = self.detected_at
        
        self.anomaly_report: dict[str, Any] = {}
        self.rca_result: dict[str, Any] = {}
        self.remediation_plan: dict[str, Any] = {}
        self.risk_assessment: dict[str, Any] = {}
        self.execution_result: dict[str, Any] = {}
        self.verification_result: dict[str, Any] = {}
        self.remediation_summary: str = ""
        self.error_message: str = ""

    def transition(self, new_status: IncidentStatus) -> None:
        old_status = self.status
        self.status = new_status
        self.updated_at = utcnow_iso()
        logger.info(
            "incident_status_transitioned",
            id=self.incident_id,
            from_status=old_status.value,
            to_status=new_status.value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "namespace": self.namespace,
            "pod": self.pod,
            "severity": self.severity.value,
            "status": self.status.value,
            "detected_at": self.detected_at,
            "updated_at": self.updated_at,
            "anomaly_report": self.anomaly_report,
            "rca_result": self.rca_result,
            "remediation_plan": self.remediation_plan,
            "risk_assessment": self.risk_assessment,
            "execution_result": self.execution_result,
            "verification_result": self.verification_result,
            "remediation_summary": self.remediation_summary,
            "error_message": self.error_message,
        }


class StateManager:
    def __init__(self):
        self._incidents: dict[str, IncidentState] = {}

    def create_incident(self, namespace: str, pod: str, severity: IncidentSeverity = IncidentSeverity.MEDIUM) -> IncidentState:
        incident_id = generate_incident_id()
        state = IncidentState(incident_id, namespace, pod, severity)
        self._incidents[incident_id] = state
        logger.info("incident_created", id=incident_id, namespace=namespace, pod=pod)
        return state

    def get_incident(self, incident_id: str) -> IncidentState | None:
        return self._incidents.get(incident_id)

    def list_incidents(self) -> list[dict[str, Any]]:
        return [state.to_dict() for state in self._incidents.values()]

    def get_recent_incidents_count(self) -> int:
        # Simple count for mock rules
        return len(self._incidents)
