import json
from typing import Any
from app.memory.vector_store import VectorStore
from app.utils.logger import get_logger
from app.utils.exceptions import IncidentMemoryError

logger = get_logger(__name__)


class IncidentMemory:
    def __init__(self, vector_store: VectorStore):
        self.store = vector_store

    def format_incident_for_storage(
        self,
        incident_id: str,
        incident_context: dict[str, Any],
        rca: dict[str, Any],
        remediation: dict[str, Any] | None = None,
        verification: dict[str, Any] | None = None,
    ) -> str:
        """
        Creates a structured, readable markdown summary of the incident, root cause,
        remediation, and verification outcome to be indexed in the vector database.
        """
        parts = [
            f"# Incident ID: {incident_id}",
            f"Namespace: {incident_context.get('namespace', 'unknown')}",
            f"Pod: {incident_context.get('pod', 'unknown')}",
            f"Detected At: {incident_context.get('detected_at', 'unknown')}",
            "",
            "## Root Cause Analysis",
            f"Category: {rca.get('root_cause_category', 'unknown')}",
            f"Description: {rca.get('root_cause_description', '')}",
            f"Confidence: {rca.get('confidence', 0.0):.2f}",
            f"Reasoning: {rca.get('reasoning', '')}",
            "",
        ]

        if remediation:
            parts.extend([
                "## Remediation",
                f"Plan ID: {remediation.get('plan_id', 'unknown')}",
                "Steps Applied:",
            ])
            for step in remediation.get("steps", []):
                parts.append(
                    f"- Step {step.get('step')}: {step.get('action')} on {step.get('target')} ({step.get('description')})"
                )
            parts.extend([
                f"Risk Level: {remediation.get('risk_level', 'unknown')}",
                f"Rationale: {remediation.get('rationale', '')}",
                "",
            ])

        if verification:
            parts.extend([
                "## Verification Outcome",
                f"Resolved: {verification.get('resolved', False)}",
                f"Confidence: {verification.get('confidence', 0.0):.2f}",
                "Evidence:",
            ])
            for ev in verification.get("evidence", []):
                parts.append(f"- {ev}")
            if verification.get("remaining_issues"):
                parts.append("Remaining Issues:")
                for iss in verification.get("remaining_issues", []):
                    parts.append(f"- {iss}")
            parts.extend([
                f"Recommendation: {verification.get('recommendation', '')}",
                "",
            ])

        return "\n".join(parts)

    def store_incident(
        self,
        incident_id: str,
        incident_context: dict[str, Any],
        rca: dict[str, Any],
        remediation: dict[str, Any] | None = None,
        verification: dict[str, Any] | None = None,
    ) -> None:
        try:
            text = self.format_incident_for_storage(
                incident_id, incident_context, rca, remediation, verification
            )
            metadata = {
                "incident_id": incident_id,
                "namespace": incident_context.get("namespace", "unknown"),
                "pod": incident_context.get("pod", "unknown"),
                "category": rca.get("root_cause_category", "unknown"),
                "resolved": str(verification.get("resolved", False)) if verification else "False",
            }
            self.store.upsert_incident(incident_id, text, metadata)
            logger.info("incident_stored_in_memory", incident_id=incident_id)
        except Exception as e:
            raise IncidentMemoryError(f"Failed to store incident memory: {e}") from e

    def query_similar_incidents(self, query_text: str, limit: int = 3) -> list[dict[str, Any]]:
        try:
            return self.store.query_similar_incidents(query_text, n_results=limit)
        except Exception as e:
            raise IncidentMemoryError(f"Failed to query similar incidents: {e}") from e