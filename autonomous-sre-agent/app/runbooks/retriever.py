from typing import Any
from app.memory.vector_store import VectorStore
from app.runbooks.runbook_loader import RunbookLoader
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RunbookRetriever:
    def __init__(self, vector_store: VectorStore, loader: RunbookLoader):
        self.store = vector_store
        self.loader = loader

    def retrieve(self, query: str, n: int = 2) -> list[dict[str, Any]]:
        results = self.store.query_runbooks(query, n_results=n)
        enriched = []
        for r in results:
            runbook_id = r["metadata"].get("filename", "").replace(".md", "")
            full = self.loader.get(runbook_id)
            enriched.append({
                "runbook_id": runbook_id,
                "title": r["metadata"].get("title", runbook_id),
                "similarity": r["similarity"],
                "full_text": full["full_text"] if full else r["document"],
                "sections": full["sections"] if full else {},
            })
        return enriched

    def retrieve_for_incident(self, incident: dict[str, Any], n: int = 2) -> list[dict[str, Any]]:
        query = " ".join([
            incident.get("root_cause_category", ""),
            incident.get("root_cause_description", ""),
            " ".join(incident.get("anomaly_signals", [])),
        ])
        return self.retrieve(query, n=n)

    def get_best_runbook_text(self, incident: dict[str, Any]) -> str:
        results = self.retrieve_for_incident(incident, n=1)
        if not results:
            return ""
        return results[0].get("full_text", "")