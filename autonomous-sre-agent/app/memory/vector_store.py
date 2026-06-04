import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Any
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.exceptions import VectorStoreError

logger = get_logger(__name__)

INCIDENT_COLLECTION = "incidents"
RUNBOOK_COLLECTION = "runbooks"


class VectorStore:
    def __init__(self):
        settings = get_settings()
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._incident_col = self._get_or_create(INCIDENT_COLLECTION)
        self._runbook_col = self._get_or_create(RUNBOOK_COLLECTION)

    def _get_or_create(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_incident(self, incident_id: str, text: str, metadata: dict[str, Any]) -> None:
        from app.memory.embeddings import embed_text
        try:
            embedding = embed_text(text)
            self._incident_col.upsert(
                ids=[incident_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
            )
            logger.info("incident_upserted_to_vector_store", id=incident_id)
        except Exception as e:
            raise VectorStoreError(f"Failed to upsert incident: {e}") from e

    def query_similar_incidents(self, text: str, n_results: int = 5) -> list[dict[str, Any]]:
        from app.memory.embeddings import embed_text
        try:
            embedding = embed_text(text)
            results = self._incident_col.query(
                query_embeddings=[embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            out = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                out.append({"document": doc, "metadata": meta, "distance": dist, "similarity": 1 - dist})
            return out
        except Exception as e:
            raise VectorStoreError(f"Failed to query incidents: {e}") from e

    def upsert_runbook(self, runbook_id: str, text: str, metadata: dict[str, Any]) -> None:
        from app.memory.embeddings import embed_text
        try:
            embedding = embed_text(text)
            self._runbook_col.upsert(
                ids=[runbook_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
            )
            logger.info("runbook_upserted", id=runbook_id)
        except Exception as e:
            raise VectorStoreError(f"Failed to upsert runbook: {e}") from e

    def query_runbooks(self, text: str, n_results: int = 3) -> list[dict[str, Any]]:
        from app.memory.embeddings import embed_text
        try:
            embedding = embed_text(text)
            results = self._runbook_col.query(
                query_embeddings=[embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            out = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                out.append({"document": doc, "metadata": meta, "distance": dist, "similarity": 1 - dist})
            return out
        except Exception as e:
            raise VectorStoreError(f"Failed to query runbooks: {e}") from e