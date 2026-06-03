import httpx
import asyncio
from typing import Any
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.exceptions import PrometheusQueryError
from app.constants import PROM_QUERIES

logger = get_logger(__name__)


class PrometheusClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.prometheus_url.rstrip("/")
        self.timeout = settings.prometheus_timeout

    async def query(self, promql: str) -> list[dict]:
        """Instant query."""
        url = f"{self.base_url}/api/v1/query"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params={"query": promql})
                resp.raise_for_status()
                data = resp.json()
                if data["status"] != "success":
                    raise PrometheusQueryError(f"Prometheus returned non-success: {data}")
                return data["data"]["result"]
        except httpx.HTTPError as e:
            raise PrometheusQueryError(f"HTTP error querying Prometheus: {e}") from e

    async def query_range(
        self,
        promql: str,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str = "60s",
    ) -> list[dict]:
        """Range query."""
        now = datetime.now(timezone.utc)
        end = end or now
        start = start or (now - timedelta(hours=1))
        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": promql,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data["status"] != "success":
                    raise PrometheusQueryError(f"Prometheus range query failed: {data}")
                return data["data"]["result"]
        except httpx.HTTPError as e:
            raise PrometheusQueryError(f"HTTP error in range query: {e}") from e

    async def get_cpu_usage(self, namespace: str, pod: str) -> list[dict]:
        q = PROM_QUERIES["cpu_usage"].format(namespace=namespace, pod=pod)
        return await self.query(q)

    async def get_memory_usage(self, namespace: str, pod: str) -> list[dict]:
        q = PROM_QUERIES["memory_usage"].format(namespace=namespace, pod=pod)
        return await self.query(q)

    async def get_error_rate(self, namespace: str) -> list[dict]:
        q = PROM_QUERIES["error_rate"].format(namespace=namespace)
        return await self.query(q)

    async def get_restart_count(self, namespace: str, pod: str) -> list[dict]:
        q = PROM_QUERIES["restart_count"].format(namespace=namespace, pod=pod)
        return await self.query(q)

    async def get_latency_p99(self, namespace: str) -> list[dict]:
        q = PROM_QUERIES["latency_p99"].format(namespace=namespace)
        return await self.query(q)

    async def get_node_metrics(self) -> dict[str, list[dict]]:
        cpu_task = self.query(PROM_QUERIES["node_cpu"])
        mem_task = self.query(PROM_QUERIES["node_memory"])
        cpu, mem = await asyncio.gather(cpu_task, mem_task, return_exceptions=True)
        return {
            "node_cpu": cpu if not isinstance(cpu, Exception) else [],
            "node_memory": mem if not isinstance(mem, Exception) else [],
        }

    async def get_all_metrics_for_namespace(self, namespace: str, pod: str = ".*") -> dict[str, Any]:
        """Gather all relevant metrics for an incident context."""
        tasks = {
            "cpu": self.get_cpu_usage(namespace, pod),
            "memory": self.get_memory_usage(namespace, pod),
            "error_rate": self.get_error_rate(namespace),
            "restart_count": self.get_restart_count(namespace, pod),
            "latency_p99": self.get_latency_p99(namespace),
        }
        results = {}
        for key, coro in tasks.items():
            try:
                results[key] = await coro
            except PrometheusQueryError as e:
                logger.warning("prometheus_metric_failed", metric=key, error=str(e))
                results[key] = []
        return results