import httpx
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.exceptions import TracingQueryError

logger = get_logger(__name__)


class TracingClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.jaeger_url.rstrip("/")
        self.timeout = settings.tracing_timeout

    async def get_services(self) -> list[str]:
        url = f"{self.base_url}/api/services"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json().get("data", [])
        except httpx.HTTPError as e:
            raise TracingQueryError(f"Failed to fetch services: {e}") from e

    async def get_traces(
        self,
        service: str,
        operation: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20,
        min_duration_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        end = end or now
        start = start or (now - timedelta(hours=1))

        url = f"{self.base_url}/api/traces"
        params: dict[str, Any] = {
            "service": service,
            "limit": limit,
            "start": int(start.timestamp() * 1_000_000),
            "end": int(end.timestamp() * 1_000_000),
        }
        if operation:
            params["operation"] = operation
        if min_duration_ms:
            params["minDuration"] = f"{min_duration_ms}ms"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json().get("data", [])
        except httpx.HTTPError as e:
            raise TracingQueryError(f"Failed to fetch traces for {service}: {e}") from e

    async def get_slow_traces(self, service: str, min_duration_ms: int = 1000) -> list[dict]:
        return await self.get_traces(service, min_duration_ms=min_duration_ms)

    async def get_error_traces(self, service: str) -> list[dict]:
        traces = await self.get_traces(service, limit=50)
        error_traces = []
        for trace in traces:
            for span in trace.get("spans", []):
                tags = {t["key"]: t["value"] for t in span.get("tags", [])}
                if tags.get("error") is True or tags.get("http.status_code", 0) >= 500:
                    error_traces.append(trace)
                    break
        return error_traces

    async def analyze_latency_distribution(self, service: str) -> dict[str, float]:
        traces = await self.get_traces(service, limit=100)
        if not traces:
            return {}
        durations_ms = []
        for trace in traces:
            spans = trace.get("spans", [])
            if spans:
                root = min(spans, key=lambda s: s.get("startTime", float("inf")))
                durations_ms.append(root.get("duration", 0) / 1000.0)

        if not durations_ms:
            return {}

        durations_ms.sort()
        n = len(durations_ms)
        return {
            "p50": durations_ms[int(n * 0.50)],
            "p90": durations_ms[int(n * 0.90)],
            "p95": durations_ms[int(n * 0.95)],
            "p99": durations_ms[min(int(n * 0.99), n - 1)],
            "max": durations_ms[-1],
            "mean": sum(durations_ms) / n,
            "count": float(n),
        }

    async def get_dependency_errors(self, service: str) -> list[dict[str, Any]]:
        """Find upstream/downstream services with errors in traces."""
        error_traces = await self.get_error_traces(service)
        deps: dict[str, int] = {}
        for trace in error_traces:
            for span in trace.get("spans", []):
                svc = span.get("process", {}).get("serviceName", "")
                if svc and svc != service:
                    deps[svc] = deps.get(svc, 0) + 1
        return [{"service": svc, "error_count": cnt} for svc, cnt in deps.items()]