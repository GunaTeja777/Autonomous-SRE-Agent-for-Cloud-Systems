import os
from typing import Any
from app.config import get_settings
from app.runbooks.parser import parse_runbook_markdown
from app.memory.vector_store import VectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RunbookLoader:
    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        settings = get_settings()
        self.runbooks_dir = settings.runbooks_dir
        self._loaded: dict[str, dict[str, Any]] = {}

    def load_all(self) -> int:
        if not os.path.isdir(self.runbooks_dir):
            logger.warning("runbooks_dir_not_found", path=self.runbooks_dir)
            return 0

        count = 0
        for fname in os.listdir(self.runbooks_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(self.runbooks_dir, fname)
                try:
                    with open(fpath, "r") as f:
                        content = f.read()
                    runbook = parse_runbook_markdown(content, filename=fname)
                    runbook_id = fname.replace(".md", "")
                    self._loaded[runbook_id] = runbook
                    self.store.upsert_runbook(
                        runbook_id=runbook_id,
                        text=runbook["full_text"],
                        metadata={
                            "title": runbook["title"],
                            "filename": fname,
                            "tags": ",".join(runbook["tags"]),
                        },
                    )
                    count += 1
                    logger.info("runbook_loaded", file=fname)
                except Exception as e:
                    logger.error("runbook_load_failed", file=fname, error=str(e))
        logger.info("runbooks_loaded_total", count=count)
        return count

    def get(self, runbook_id: str) -> dict[str, Any] | None:
        return self._loaded.get(runbook_id)

    def list_all(self) -> list[str]:
        return list(self._loaded.keys())