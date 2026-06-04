import asyncio
from typing import Any

from app.monitoring.prometheus_client import PrometheusClient
from app.monitoring.loki_client import LokiClient
from app.monitoring.tracing_client import TracingClient
from app.monitoring.kubernetes_client import KubernetesClient

from app.agents.metric_agent import MetricAgent
from app.agents.log_agent import LogAgent
from app.agents.trace_agent import TraceAgent
from app.agents.kubernetes_agent import KubernetesAgent
from app.agents.consensus_agent import ConsensusAgent

from app.utils.logger import get_logger

logger = get_logger(__name__)


class RootCauseEngine:
    def __init__(
        self,
        prometheus: PrometheusClient,
        loki: LokiClient,
        tracing: TracingClient,
        k8s: KubernetesClient,
        consensus: ConsensusAgent,
    ):
        self.prometheus = prometheus
        self.loki = loki
        self.tracing = tracing
        self.k8s = k8s
        self.consensus = consensus

        self.metric_agent = MetricAgent()
        self.log_agent = LogAgent()
        self.trace_agent = TraceAgent()
        self.kubernetes_agent = KubernetesAgent()

    async def analyze_incident(self, namespace: str, pod: str) -> dict[str, Any]:
        """
        Gathers logs, metrics, traces, and Kubernetes event data and coordinates
        execution of metric, log, trace, and kubernetes agents, resolving to consensus.
        """
        logger.info("root_cause_engine_analysis_started", namespace=namespace, pod=pod)

        # 1. Fetch data concurrently
        metrics_task = self.prometheus.get_all_metrics_for_namespace(namespace, pod)
        logs_task = self.loki.get_all_logs_for_incident(namespace, pod)
        pods_task = asyncio.to_thread(self.k8s.get_pods, namespace)
        events_task = asyncio.to_thread(self.k8s.get_events, namespace)

        metrics, logs, pods, events = await asyncio.gather(
            metrics_task, logs_task, pods_task, events_task, return_exceptions=True
        )

        # Handle exceptions gracefully
        if isinstance(metrics, Exception):
            logger.error("rca_fetch_metrics_failed", error=str(metrics))
            metrics = {}
        if isinstance(logs, Exception):
            logger.error("rca_fetch_logs_failed", error=str(logs))
            logs = {}
        if isinstance(pods, Exception):
            logger.error("rca_fetch_pods_failed", error=str(pods))
            pods = []
        if isinstance(events, Exception):
            logger.error("rca_fetch_events_failed", error=str(events))
            events = []

        # Find specific service in Jaeger
        service_name = pod.split("-")[0] if "-" in pod else pod
        try:
            available_services = await self.tracing.get_services()
            if service_name not in available_services and available_services:
                # Fallback to first available service or namespace match
                service_name = available_services[0]
        except Exception as e:
            logger.warning("failed_to_fetch_tracing_services", error=str(e))
            available_services = []

        # Fetch tracing details
        error_traces = []
        slow_traces = []
        latency_dist = {}
        dependency_errors = []

        if service_name in available_services:
            try:
                error_traces_task = self.tracing.get_error_traces(service_name)
                slow_traces_task = self.tracing.get_slow_traces(service_name)
                latency_task = self.tracing.analyze_latency_distribution(service_name)
                dep_errors_task = self.tracing.get_dependency_errors(service_name)

                error_traces, slow_traces, latency_dist, dependency_errors = await asyncio.gather(
                    error_traces_task, slow_traces_task, latency_task, dep_errors_task, return_exceptions=True
                )

                if isinstance(error_traces, Exception): error_traces = []
                if isinstance(slow_traces, Exception): slow_traces = []
                if isinstance(latency_dist, Exception): latency_dist = {}
                if isinstance(dependency_errors, Exception): dependency_errors = []
            except Exception as e:
                logger.error("failed_to_fetch_traces", service=service_name, error=str(e))

        # 2. Run specialist agent analyses concurrently
        metric_agent_task = self.metric_agent.analyze(metrics)
        log_agent_task = self.log_agent.analyze(logs)
        trace_agent_task = self.trace_agent.analyze(
            error_traces, slow_traces, latency_dist, dependency_errors
        )
        kubernetes_agent_task = self.kubernetes_agent.analyze(pods, events)

        metric_out, log_out, trace_out, k8s_out = await asyncio.gather(
            metric_agent_task, log_agent_task, trace_agent_task, kubernetes_agent_task
        )

        agent_findings = [metric_out, log_out, trace_out, k8s_out]

        # 3. Run Consensus Agent to reconcile findings
        consensus_out = await self.consensus.run(agent_findings)

        # 4. Compile final summary
        combined_result = {
            "root_cause_category": consensus_out.get("root_cause_category"),
            "root_cause_description": consensus_out.get("root_cause_description"),
            "confidence": consensus_out.get("confidence"),
            "agreement_level": consensus_out.get("agreement_level"),
            "dissenting_views": consensus_out.get("dissenting_views"),
            "agent_findings": {
                "metric_agent": metric_out,
                "log_agent": log_out,
                "trace_agent": trace_out,
                "kubernetes_agent": k8s_out,
            },
            "collected_data": {
                "metrics_summary": metrics,
                "logs_summary": logs,
                "pods_count": len(pods),
                "events_count": len(events),
                "traces_count": len(error_traces) + len(slow_traces),
            },
        }

        logger.info("root_cause_engine_analysis_complete", root_cause=combined_result["root_cause_category"])
        return combined_result
