import httpx
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.exceptions import LokiQueryError
from app.constants import LOKI_QUERIES

logger = get_logger(__name__)

NS_IN_SEC = 1_000_000_000


class LokiClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.loki_url.rstrip("/")
        self.timeout = settings.loki_timeout

    def _to_ns(self, dt: datetime) -> str:
        return str(int(dt.timestamp() * NS_IN_SEC))

    async def query_range(
        self,
        logql: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        end = end or now
        start = start or (now - timedelta(hours=1))

        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {
            "query": logql,
            "start": self._to_ns(start),
            "end": self._to_ns(end),
            "limit": limit,
            "direction": "backward",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", {}).get("result", [])
        except httpx.HTTPError as e:
            raise LokiQueryError(f"Loki query failed: {e}") from e

    def _parse_log_lines(self, results: list[dict]) -> list[str]:
        lines = []
        for stream in results:
            for ts, line in stream.get("values", []):
                lines.append(line)
        return lines

    async def get_error_logs(self, namespace: str, pod: str, hours: int = 1) -> list[str]:
        q = LOKI_QUERIES["error_logs"].format(namespace=namespace, pod=pod)
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = await self.query_range(q, start=start)
        return self._parse_log_lines(results)

    async def get_oom_logs(self, namespace: str, hours: int = 2) -> list[str]:
        q = LOKI_QUERIES["oom_logs"].format(namespace=namespace)
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = await self.query_range(q, start=start)
        return self._parse_log_lines(results)

    async def get_crashloop_logs(self, namespace: str, pod: str, hours: int = 2) -> list[str]:
        q = LOKI_QUERIES["crashloop_logs"].format(namespace=namespace, pod=pod)
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = await self.query_range(q, start=start)
        return self._parse_log_lines(results)

    async def get_image_pull_logs(self, namespace: str, hours: int = 1) -> list[str]:
        q = LOKI_QUERIES["image_pull_logs"].format(namespace=namespace)
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = await self.query_range(q, start=start)
        return self._parse_log_lines(results)

    async def get_recent_logs(
        self, namespace: str, pod: str, hours: int = 1, limit: int = 100
    ) -> list[str]:
        q = LOKI_QUERIES["recent_logs"].format(namespace=namespace, pod=pod)
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = await self.query_range(q, start=start, limit=limit)
        return self._parse_log_lines(results)

    async def get_all_logs_for_incident(
        self, namespace: str, pod: str
    ) -> dict[str, list[str]]:
        output = {}
        for key, fetcher in [
            ("errors", lambda: self.get_error_logs(namespace, pod)),
            ("oom", lambda: self.get_oom_logs(namespace)),
            ("crashloop", lambda: self.get_crashloop_logs(namespace, pod)),
            ("image_pull", lambda: self.get_image_pull_logs(namespace)),
            ("recent", lambda: self.get_recent_logs(namespace, pod)),
        ]:
            try:
                output[key] = await fetcher()
            except LokiQueryError as e:
                logger.warning("loki_log_fetch_failed", log_type=key, error=str(e))
                output[key] = []
        return output